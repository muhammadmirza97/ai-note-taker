from __future__ import annotations

import json
import logging
from pathlib import Path
import sqlite3
import subprocess
import uuid

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import advanced_outputs
import config
import db
import exporter
import file_store
import security
import study_intelligence
import summariser
import transcriber


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = BASE_DIR / "data" / "uploads"

TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
AUDIO_VIDEO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".aac", ".mov"}
ALL_UPLOAD_EXTENSIONS = TEXT_EXTENSIONS | AUDIO_VIDEO_EXTENSIONS
REGENERATE_KINDS = {"short_summary", "detailed_summary", "key_points", "terms", "quiz", "all"}

auth_limiter = security.RateLimiter()
ai_limiter = security.RateLimiter()

app = FastAPI(title="Personal Lecture Notes")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def startup() -> None:
    config.require_production_secret()
    db.init_db()
    file_store.ensure_output_dirs()
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
def _startup_event() -> None:
    startup()


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    logging.exception("Unhandled API error")
    return JSONResponse(status_code=500, content={"error": "Something went wrong. Please try again."})


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
        if not request.url.path.startswith("/api/auth/"):
            cookie_token = request.cookies.get(config.CSRF_COOKIE_NAME, "")
            header_token = request.headers.get("X-CSRF-Token", "")
            if cookie_token and header_token and cookie_token != header_token:
                return JSONResponse(status_code=403, content={"error": "Refresh the page and try again."})
    return await call_next(request)


def _client_key(request: Request, bucket: str) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    host = forwarded.split(",", 1)[0].strip() if forwarded else (request.client.host if request.client else "local")
    return f"{bucket}:{host}"


def _check_rate(request: Request, limiter: security.RateLimiter, limit: int, bucket: str) -> None:
    if not limiter.allow(_client_key(request, bucket), limit):
        raise HTTPException(status_code=429, detail="Slow down for a moment and try again.")


def _set_auth_cookies(response: JSONResponse, session: dict) -> None:
    cookie_kwargs = {
        "httponly": True,
        "samesite": "lax",
        "secure": config.APP_ENV == "production",
        "max_age": config.SESSION_DAYS * 24 * 60 * 60,
    }
    response.set_cookie(config.SESSION_COOKIE_NAME, session["token"], **cookie_kwargs)
    response.set_cookie(
        config.CSRF_COOKIE_NAME,
        session["csrf_token"],
        httponly=False,
        samesite="lax",
        secure=config.APP_ENV == "production",
        max_age=config.SESSION_DAYS * 24 * 60 * 60,
    )


def _clear_auth_cookies(response: JSONResponse) -> None:
    response.delete_cookie(config.SESSION_COOKIE_NAME)
    response.delete_cookie(config.CSRF_COOKIE_NAME)


def _public_user(user: dict) -> dict:
    return {"id": int(user["id"]), "email": user["email"]}


def _validate_email_password(payload: dict) -> tuple[str, str]:
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise HTTPException(status_code=400, detail="Use a valid email address.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="That password is too short - use at least 8 characters.")
    return email, password


def _current_user(request: Request) -> dict:
    token = request.cookies.get(config.SESSION_COOKIE_NAME, "")
    auth_session = db.get_auth_session(token)
    if not auth_session:
        raise HTTPException(status_code=401, detail="Please sign in again before continuing.")
    return {"id": int(auth_session["user_id"]), "email": auth_session["email"]}


def _owned_session(session_id: int, user_id: int) -> dict:
    session = db.get_session(session_id, user_id=user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _clean_title(value: str) -> str:
    title = " ".join(str(value or "").replace("_", " ").split()).strip()
    return title[:120] or "Lecture"


def _source_type_for_upload(path: Path) -> str:
    return "text" if path.suffix.lower() in TEXT_EXTENSIONS else "uploaded audio"


async def _read_upload_chunks(upload: UploadFile, allowed_extensions: set[str]) -> Path:
    original_name = Path(upload.filename or "lecture-upload").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Try one of: {allowed}.")

    target = UPLOADS_DIR / f"{uuid.uuid4().hex}{suffix}"
    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    total = 0
    with target.open("wb") as output:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"File is too large. The current limit is {config.MAX_UPLOAD_MB} MB.")
            output.write(chunk)
    if total == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The uploaded file was empty.")
    return target


def _read_text_upload(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return data.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace").strip()


def _plain_job_message(status: str) -> str:
    return {
        "queued": "Waiting for its turn.",
        "transcribing": "Listening to your lecture.",
        "generating": "Turning your lecture into study notes.",
        "completed": "Your study notes are ready.",
        "failed": "Something went wrong.",
    }.get(status, "Working on your lecture.")


def _set_job(job_id: str, user_id: int, status: str, step: int, message: str = "", **extra) -> None:
    existing = db.get_job(job_id, user_id=user_id) or {}
    db.upsert_job(
        {
            **existing,
            "id": job_id,
            "user_id": user_id,
            "kind": "lecture",
            "status": status,
            "step": step,
            "message": message or _plain_job_message(status),
            "error": extra.get("error", existing.get("error", "")),
            "session_id": extra.get("session_id", existing.get("session_id")),
            "attempts": extra.get("attempts", existing.get("attempts", 0)),
            "max_attempts": existing.get("max_attempts", 3),
            "created_at": existing.get("created_at"),
        }
    )


def _get_job(job_id: str, user_id: int) -> dict:
    job = db.get_job(job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _job_response(job: dict) -> dict:
    response = {
        "job_id": job["id"],
        "id": job["id"],
        "session_id": job.get("session_id"),
        "status": job.get("status"),
        "step": job.get("step"),
        "message": job.get("message"),
        "error": job.get("error"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
    }
    if job.get("status") == "completed" and job.get("session_id"):
        session = _session_with_intelligence(int(job["session_id"]), int(job["user_id"]))
        response.update(session)
        response["job_id"] = job["id"]
    return response


def _update_outputs_for_session(session_id: int, user_id: int, options: dict | None = None) -> dict:
    session = _session_with_intelligence(session_id, user_id)
    paths = file_store.write_outputs(session, options=options)
    db.update_session_outputs(session_id, **paths)
    session.update(paths)
    return session


def _attach_advanced_session_data(session: dict) -> dict:
    enriched = dict(session)
    if enriched.get("mind_map_json"):
        try:
            enriched["mind_map"] = advanced_outputs.validate_mind_map(json.loads(enriched["mind_map_json"]))
        except Exception:
            logging.info("Invalid stored mind map for session %s", enriched.get("id"), exc_info=True)
            enriched["mind_map"] = None
    else:
        enriched["mind_map"] = None
    if not enriched.get("lesson_breakdown") and enriched.get("mind_map"):
        enriched["lesson_breakdown"] = advanced_outputs.mind_map_to_outline(enriched["mind_map"])
    enriched["revision_plan"] = advanced_outputs.revision_plan_text(
        enriched.get("weak_topics") or [],
        enriched.get("recommendations") or [],
    )
    return enriched


def _session_with_intelligence(session_id: int, user_id: int) -> dict:
    session = _owned_session(session_id, user_id)
    session.setdefault("filename", session.get("title", ""))
    attempts = db.get_quiz_attempts(session_id)
    cards = db.get_flashcards(session_id)
    weak_topics = study_intelligence.compute_weak_topics(attempts, cards)
    recommendations = study_intelligence.build_recommendations([session], {session_id: attempts}, {session_id: weak_topics}, {session_id: cards})
    session["flashcards"] = cards
    session["quiz_attempts"] = attempts
    session["weak_topics"] = weak_topics
    session["recommendations"] = recommendations
    session["key_point_citations"] = advanced_outputs.key_point_citations(session.get("key_points", ""), session.get("transcript", ""))
    return _attach_advanced_session_data(session)


def _export_options_from_query(include_transcript: bool, include_quiz: bool, include_flashcards: bool, include_mind_map: bool) -> dict:
    return {
        "include_transcript": include_transcript,
        "include_quiz": include_quiz,
        "include_flashcards": include_flashcards,
        "include_mind_map": include_mind_map,
    }


def _quiz_questions_from_session(session: dict) -> list[dict]:
    raw = session.get("quiz_json") or ""
    if raw:
        try:
            return study_intelligence.validate_quiz_questions(json.loads(raw))
        except Exception:
            logging.info("Stored quiz JSON was invalid for session %s", session.get("id"), exc_info=True)
    return []


def _ensure_quiz_questions(session: dict, focus_topic: str = "", count: int = 8) -> list[dict]:
    if not focus_topic:
        existing = _quiz_questions_from_session(session)
        if existing:
            return existing
    questions = summariser.generate_quiz_questions(session.get("transcript", ""), focus_topic=focus_topic, count=count)
    if not focus_topic:
        db.set_session_quiz(int(session["id"]), summariser.quiz_to_markdown(questions), questions)
    return questions


def _materialize_existing_outputs(session_id: int, user_id: int) -> dict:
    session = _session_with_intelligence(session_id, user_id)
    if session.get("transcript_path") and session.get("combined_path") and session.get("pdf_path"):
        return session
    return _update_outputs_for_session(session_id, user_id)


def _generate_and_save_study_outputs(session_id: int, transcript: str) -> dict:
    materials = summariser.generate_study_materials(transcript)
    db.update_session_study_outputs(
        session_id,
        short_summary=materials["short_summary"],
        detailed_summary=materials["detailed_summary"],
        key_points=materials["key_points"],
        terms=materials["terms"],
        quiz=materials["quiz"],
        status="completed",
    )
    return materials


def _run_job_with_retries(job_id: str, user_id: int, work) -> None:
    try:
        work()
    except Exception as exc:
        logging.exception("Job %s failed", job_id)
        _set_job(job_id, user_id, "failed", 0, "Upload failed. Try a smaller audio/text file.", error=str(exc))


def _process_text_upload(job_id: str, user_id: int, upload_path: str, title: str, source_type: str, duration_seconds: int = 0) -> None:
    def work() -> None:
        _set_job(job_id, user_id, "generating", 3, "Turning your text into study notes.")
        transcript = _read_text_upload(Path(upload_path))
        if not transcript.strip():
            raise ValueError("No readable text was detected in that file.")
        session_id = db.save_session(title, transcript, "", duration_seconds, source_type=source_type, status="processing", user_id=user_id)
        _set_job(job_id, user_id, "generating", 3, "Generating study notes.", session_id=session_id)
        _generate_and_save_study_outputs(session_id, transcript)
        _update_outputs_for_session(session_id, user_id)
        _set_job(job_id, user_id, "completed", 3, "Your study notes are ready.", session_id=session_id)

    _run_job_with_retries(job_id, user_id, work)


def _process_media_upload(job_id: str, user_id: int, upload_path: str, title: str, source_type: str, duration_seconds: int = 0) -> None:
    def work() -> None:
        _set_job(job_id, user_id, "transcribing", 2, "Transcribing your lecture audio.")
        transcript = transcriber.transcribe(upload_path)
        if not transcript.strip():
            raise ValueError("No speech was detected in that file.")
        session_id = db.save_session(title, transcript, "", duration_seconds, source_type=source_type, status="processing", user_id=user_id)
        _set_job(job_id, user_id, "generating", 3, "Generating study notes.", session_id=session_id)
        _generate_and_save_study_outputs(session_id, transcript)
        _update_outputs_for_session(session_id, user_id)
        _set_job(job_id, user_id, "completed", 3, "Your study notes are ready.", session_id=session_id)

    _run_job_with_retries(job_id, user_id, work)


def _save_mind_map(session_id: int, mind_map: dict, user_id: int) -> dict:
    validated = advanced_outputs.validate_mind_map(mind_map)
    db.update_advanced_outputs(session_id, mind_map_json=json.dumps(validated), lesson_breakdown=advanced_outputs.mind_map_to_outline(validated))
    _update_outputs_for_session(session_id, user_id)
    return validated


def _rename_node(node: dict, node_id: str, label: str) -> bool:
    if node.get("id") == node_id:
        node["label"] = label
        return True
    for child in node.get("children", []):
        if _rename_node(child, node_id, label):
            return True
    return False


def _delete_node(node: dict, node_id: str) -> bool:
    children = node.get("children", [])
    for index, child in enumerate(list(children)):
        if child.get("id") == node_id:
            del children[index]
            return True
        if _delete_node(child, node_id):
            return True
    return False


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/auth/signup")
def signup(payload: dict, request: Request) -> JSONResponse:
    _check_rate(request, auth_limiter, config.RATE_LIMIT_AUTH_PER_MINUTE, "auth")
    email, password = _validate_email_password(payload)
    first_account = db.count_users() == 0
    if db.get_user_by_email(email):
        raise HTTPException(status_code=400, detail="An account with that email already exists.")
    user = db.create_user(email, security.hash_password(password))
    claimed = db.assign_legacy_sessions_to_user(int(user["id"])) if first_account else 0
    auth_session = db.create_auth_session(int(user["id"]), security.new_token(), security.new_token(), days=config.SESSION_DAYS)
    response = JSONResponse({"user": _public_user(user), "claimed_lectures": claimed})
    _set_auth_cookies(response, auth_session)
    return response


@app.post("/api/auth/login")
def login(payload: dict, request: Request) -> JSONResponse:
    _check_rate(request, auth_limiter, config.RATE_LIMIT_AUTH_PER_MINUTE, "auth")
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    user = db.get_user_by_email(email)
    if user is None or not security.verify_password(password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="That email or password did not match.")
    auth_session = db.create_auth_session(int(user["id"]), security.new_token(), security.new_token(), days=config.SESSION_DAYS)
    response = JSONResponse({"user": _public_user(user)})
    _set_auth_cookies(response, auth_session)
    return response


@app.post("/api/auth/logout")
def logout(request: Request) -> JSONResponse:
    token = request.cookies.get(config.SESSION_COOKIE_NAME, "")
    if token:
        db.delete_auth_session(token)
    response = JSONResponse({"logged_out": True})
    _clear_auth_cookies(response)
    return response


@app.get("/api/auth/me")
def me(request: Request) -> dict:
    return {"user": _current_user(request)}


@app.post("/api/auth/reset-password")
def reset_password(payload: dict, request: Request) -> dict:
    _check_rate(request, auth_limiter, config.RATE_LIMIT_AUTH_PER_MINUTE, "auth")
    if config.APP_ENV == "production" or not config.ALLOW_DEV_PASSWORD_RESET:
        raise HTTPException(status_code=501, detail="Password reset email is not configured yet.")
    email, password = _validate_email_password(payload)
    user = db.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="No account found for that email.")
    db.update_user_password(int(user["id"]), security.hash_password(password))
    return {"message": "Password updated for local development."}


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "env": config.APP_ENV}


@app.get("/api/health")
def api_health() -> dict:
    return healthz()


@app.get("/readyz")
def readyz() -> dict:
    startup()
    return {"ready": True}


@app.get("/metrics")
def metrics() -> dict:
    return db.job_metrics()


@app.post("/api/transcribe")
async def transcribe_audio(
    request: Request,
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    duration_seconds: int = Form(0),
) -> dict:
    user = _current_user(request)
    original_name = Path(audio.filename or "lecture.webm").name
    saved_path = await _read_upload_chunks(audio, AUDIO_VIDEO_EXTENSIONS)
    job_id = uuid.uuid4().hex
    _set_job(job_id, int(user["id"]), "queued", 1, "Recording uploaded. Waiting to process.")
    background_tasks.add_task(
        _process_media_upload,
        job_id,
        int(user["id"]),
        str(saved_path),
        "Recorded lecture",
        "recorded",
        max(0, int(duration_seconds or 0)),
    )
    return _job_response(_get_job(job_id, int(user["id"])))


@app.post("/api/upload")
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(""),
) -> dict:
    user = _current_user(request)
    original_name = Path(file.filename or "lecture-upload").name
    saved_path = await _read_upload_chunks(file, ALL_UPLOAD_EXTENSIONS)
    job_id = uuid.uuid4().hex
    clean_title = _clean_title(title or Path(original_name).stem)
    source_type = _source_type_for_upload(saved_path)
    _set_job(job_id, int(user["id"]), "queued", 1, "Upload accepted. Waiting to process.")
    task = _process_text_upload if saved_path.suffix.lower() in TEXT_EXTENSIONS else _process_media_upload
    background_tasks.add_task(task, job_id, int(user["id"]), str(saved_path), clean_title, source_type, 0)
    return _job_response(_get_job(job_id, int(user["id"])))


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str, request: Request) -> dict:
    user = _current_user(request)
    return _job_response(_get_job(job_id, int(user["id"])))


@app.get("/api/jobs")
def list_jobs(request: Request) -> dict:
    user = _current_user(request)
    return {"jobs": [_job_response(job) for job in db.list_jobs(user_id=int(user["id"]))]}


@app.get("/api/outputs")
def output_locations(request: Request) -> dict:
    _current_user(request)
    file_store.ensure_output_dirs()
    return {
        "outputs": str(file_store.OUTPUTS_DIR.resolve()),
        "transcripts": str(file_store.TRANSCRIPTS_DIR.resolve()),
        "summaries": str(file_store.SUMMARIES_DIR.resolve()),
        "pdfs": str(file_store.PDFS_DIR.resolve()),
        "combined": str(file_store.COMBINED_DIR.resolve()),
    }


@app.post("/api/outputs/open")
def open_outputs_folder(request: Request) -> dict:
    _current_user(request)
    file_store.ensure_output_dirs()
    try:
        subprocess.Popen(["explorer.exe", str(file_store.OUTPUTS_DIR.resolve())])
    except Exception:
        logging.exception("Failed to open outputs folder")
        raise HTTPException(status_code=500, detail="Could not open outputs folder.")
    return {"opened": True, "path": str(file_store.OUTPUTS_DIR.resolve())}


@app.get("/api/sessions")
def list_sessions(request: Request, q: str = "", date: str = "all") -> list[dict]:
    user = _current_user(request)
    sessions = db.get_sessions(query=q, date_filter=date, user_id=int(user["id"]))
    for session in sessions:
        session.setdefault("filename", session.get("title", ""))
    return sessions


@app.get("/api/sessions/{session_id}")
def session_detail(session_id: int, request: Request) -> dict:
    user = _current_user(request)
    return _session_with_intelligence(session_id, int(user["id"]))


@app.post("/api/sessions/{session_id}/generate/{kind}")
def regenerate_session_output(session_id: int, kind: str, request: Request) -> dict:
    user = _current_user(request)
    _check_rate(request, ai_limiter, config.RATE_LIMIT_AI_PER_MINUTE, "ai")
    if kind not in REGENERATE_KINDS:
        raise HTTPException(status_code=400, detail="That study section cannot be regenerated.")
    session = _owned_session(session_id, int(user["id"]))
    try:
        db.update_session_status(session_id, "generating")
        transcript = session.get("transcript", "")
        if kind == "quiz":
            questions = summariser.generate_quiz_questions(transcript)
            db.set_session_quiz(session_id, summariser.quiz_to_markdown(questions), questions)
        elif kind == "all":
            _generate_and_save_study_outputs(session_id, transcript)
        else:
            value = summariser.generate_output(transcript, kind)
            db.update_session_study_outputs(session_id, **{kind: value}, status="completed")
        _update_outputs_for_session(session_id, int(user["id"]))
        return _session_with_intelligence(session_id, int(user["id"]))
    except Exception:
        logging.exception("Failed to regenerate %s for session %s", kind, session_id)
        db.update_session_status(session_id, "failed", "Could not regenerate that section.")
        raise HTTPException(status_code=500, detail="Could not regenerate that section. Please try again.")


@app.get("/api/sessions/{session_id}/chat")
def get_chat(session_id: int, request: Request) -> dict:
    user = _current_user(request)
    _owned_session(session_id, int(user["id"]))
    suggestions = [
        "What are the most important ideas?",
        "Explain this more simply.",
        "What should I revise first?",
    ]
    return {"messages": db.get_chat_messages(session_id), "suggestions": suggestions}


@app.post("/api/sessions/{session_id}/chat")
def ask_chat(session_id: int, payload: dict, request: Request) -> dict:
    user = _current_user(request)
    _check_rate(request, ai_limiter, config.RATE_LIMIT_AI_PER_MINUTE, "ai")
    session = _owned_session(session_id, int(user["id"]))
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="Ask a question first.")
    db.add_chat_message(session_id, "user", message)
    history = db.get_chat_messages(session_id)
    try:
        answer = summariser.answer_question(session.get("transcript", ""), message, history)
    except Exception:
        logging.exception("Failed to answer lecture question for session %s", session_id)
        answer = "I couldn't answer that just now. Please try again."
    db.add_chat_message(session_id, "assistant", answer)
    return {"answer": answer, "messages": db.get_chat_messages(session_id)}


@app.delete("/api/sessions/{session_id}/chat")
def clear_chat(session_id: int, request: Request) -> dict:
    user = _current_user(request)
    _owned_session(session_id, int(user["id"]))
    db.clear_chat_messages(session_id)
    return {"ok": True, "messages": []}


@app.get("/api/sessions/{session_id}/flashcards")
def get_flashcards(session_id: int, request: Request) -> dict:
    user = _current_user(request)
    _owned_session(session_id, int(user["id"]))
    return {"flashcards": db.get_flashcards(session_id)}


@app.post("/api/sessions/{session_id}/flashcards")
def create_flashcards(session_id: int, request: Request) -> dict:
    user = _current_user(request)
    _check_rate(request, ai_limiter, config.RATE_LIMIT_AI_PER_MINUTE, "ai")
    session = _owned_session(session_id, int(user["id"]))
    try:
        cards = summariser.generate_flashcards(session.get("transcript", ""))
        saved = db.replace_flashcards(session_id, cards)
        weak_topics = study_intelligence.compute_weak_topics(db.get_quiz_attempts(session_id), saved)
        _update_outputs_for_session(session_id, int(user["id"]))
        return {"flashcards": saved, "weak_topics": weak_topics}
    except Exception:
        logging.exception("Failed to create flashcards for session %s", session_id)
        raise HTTPException(status_code=500, detail="Could not create flashcards. Please try again.")


@app.patch("/api/flashcards/{card_id}")
@app.put("/api/flashcards/{card_id}")
def update_flashcard(card_id: int, payload: dict, request: Request) -> dict:
    user = _current_user(request)
    status = str(payload.get("status", "")).strip().lower()
    if status not in {"new", "got_it", "not_yet"}:
        raise HTTPException(status_code=400, detail="That flashcard status is not supported.")
    card = db.update_flashcard_status(card_id, status, user_id=int(user["id"]))
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    return card


@app.delete("/api/flashcards/{card_id}")
def delete_flashcard(card_id: int, request: Request) -> dict:
    user = _current_user(request)
    db.delete_flashcard(card_id, user_id=int(user["id"]))
    return {"deleted": True}


@app.get("/api/sessions/{session_id}/quiz")
def get_structured_quiz(session_id: int, request: Request) -> dict:
    user = _current_user(request)
    session = _owned_session(session_id, int(user["id"]))
    try:
        questions = _ensure_quiz_questions(session)
        return {"questions": questions, "attempts": db.get_quiz_attempts(session_id)}
    except Exception:
        logging.exception("Failed to load structured quiz for session %s", session_id)
        raise HTTPException(status_code=500, detail="Could not prepare the quiz. Please try again.")


@app.post("/api/sessions/{session_id}/quiz/attempts")
def submit_quiz_attempt(session_id: int, payload: dict, request: Request) -> dict:
    user = _current_user(request)
    session = _owned_session(session_id, int(user["id"]))
    try:
        questions = _ensure_quiz_questions(session)
        score = study_intelligence.score_quiz_attempt(questions, payload.get("answers") or {})
        attempt = db.add_quiz_attempt(
            session_id,
            score["score"],
            score["total"],
            score["percent"],
            score["results"],
            focus_topic=(score["results"][0]["topic"] if score["results"] else ""),
        )
        attempts = db.get_quiz_attempts(session_id)
        weak_topics = study_intelligence.compute_weak_topics(attempts, db.get_flashcards(session_id))
        _update_outputs_for_session(session_id, int(user["id"]))
        return {"attempt": attempt, "attempts": attempts, "weak_topics": weak_topics}
    except Exception:
        logging.exception("Failed to score quiz for session %s", session_id)
        raise HTTPException(status_code=500, detail="Could not score that quiz. Please try again.")


@app.get("/api/sessions/{session_id}/quiz/practice")
def get_practice_quiz(session_id: int, request: Request, topic: str = "") -> dict:
    user = _current_user(request)
    _check_rate(request, ai_limiter, config.RATE_LIMIT_AI_PER_MINUTE, "ai")
    session = _owned_session(session_id, int(user["id"]))
    try:
        questions = summariser.generate_quiz_questions(session.get("transcript", ""), focus_topic=topic, count=5)
        return {"questions": questions}
    except Exception:
        logging.exception("Failed to create practice quiz for session %s", session_id)
        raise HTTPException(status_code=500, detail="Could not make a practice quiz. Please try again.")


@app.get("/api/sessions/{session_id}/weak-topics")
def get_weak_topics(session_id: int, request: Request) -> dict:
    user = _current_user(request)
    _owned_session(session_id, int(user["id"]))
    weak_topics = study_intelligence.compute_weak_topics(db.get_quiz_attempts(session_id), db.get_flashcards(session_id))
    return {"weak_topics": weak_topics}


@app.get("/api/recommendations")
def get_recommendations(request: Request) -> dict:
    user = _current_user(request)
    sessions = db.get_sessions(user_id=int(user["id"]))
    attempts = db.get_all_quiz_attempts(user_id=int(user["id"]))
    cards = db.get_all_flashcards(user_id=int(user["id"]))
    weak_by_session = {
        int(session["id"]): study_intelligence.compute_weak_topics(attempts.get(int(session["id"]), []), cards.get(int(session["id"]), []))
        for session in sessions
    }
    recommendations = study_intelligence.build_recommendations(sessions, attempts, weak_by_session, cards)
    weak_topics = [item["topic"] for topics in weak_by_session.values() for item in topics]
    return {"recommendations": recommendations, "weak_topics": weak_topics}


@app.get("/api/sessions/{session_id}/mind-map")
def get_mind_map(session_id: int, request: Request) -> dict:
    user = _current_user(request)
    session = _session_with_intelligence(session_id, int(user["id"]))
    if not session.get("mind_map"):
        raise HTTPException(status_code=404, detail="Mind map not found")
    return {"mind_map": session["mind_map"]}


@app.post("/api/sessions/{session_id}/mind-map")
def create_mind_map(session_id: int, request: Request) -> dict:
    user = _current_user(request)
    _check_rate(request, ai_limiter, config.RATE_LIMIT_AI_PER_MINUTE, "ai")
    session = _owned_session(session_id, int(user["id"]))
    try:
        tree = summariser.generate_mind_map(session.get("transcript", ""), session.get("title", "Lecture"))
        return {"mind_map": _save_mind_map(session_id, tree, int(user["id"]))}
    except Exception:
        logging.exception("Failed to create mind map for session %s", session_id)
        raise HTTPException(status_code=500, detail="Could not create the mind map. Please try again.")


@app.patch("/api/sessions/{session_id}/mind-map/nodes/{node_id}")
def rename_mind_map_node(session_id: int, node_id: str, payload: dict, request: Request) -> dict:
    user = _current_user(request)
    session = _session_with_intelligence(session_id, int(user["id"]))
    tree = session.get("mind_map")
    if not tree:
        raise HTTPException(status_code=404, detail="Mind map not found")
    label = str(payload.get("label", "")).strip()
    if not label:
        raise HTTPException(status_code=400, detail="Give the node a name first.")
    if not _rename_node(tree, node_id, label):
        raise HTTPException(status_code=404, detail="Mind map node not found")
    return {"mind_map": _save_mind_map(session_id, tree, int(user["id"]))}


@app.delete("/api/sessions/{session_id}/mind-map/nodes/{node_id}")
def delete_mind_map_node(session_id: int, node_id: str, request: Request) -> dict:
    user = _current_user(request)
    session = _session_with_intelligence(session_id, int(user["id"]))
    tree = session.get("mind_map")
    if not tree:
        raise HTTPException(status_code=404, detail="Mind map not found")
    if tree.get("id") == node_id:
        raise HTTPException(status_code=400, detail="Keep the central topic and delete a branch instead.")
    if not _delete_node(tree, node_id):
        raise HTTPException(status_code=404, detail="Mind map node not found")
    return {"mind_map": _save_mind_map(session_id, tree, int(user["id"]))}


@app.post("/api/sessions/{session_id}/video-script")
def create_video_script(session_id: int, request: Request) -> dict:
    user = _current_user(request)
    _check_rate(request, ai_limiter, config.RATE_LIMIT_AI_PER_MINUTE, "ai")
    session = _owned_session(session_id, int(user["id"]))
    try:
        script = summariser.generate_video_script(session.get("transcript", ""), session.get("title", "Lecture"))
        db.update_advanced_outputs(session_id, video_script=script)
        _update_outputs_for_session(session_id, int(user["id"]))
        return {"video_script": script}
    except Exception:
        logging.exception("Failed to create video script for session %s", session_id)
        raise HTTPException(status_code=500, detail="Could not write the video script. Please try again.")


@app.post("/api/sessions/{session_id}/podcast-script")
def create_podcast_script(session_id: int, payload: dict, request: Request) -> dict:
    user = _current_user(request)
    _check_rate(request, ai_limiter, config.RATE_LIMIT_AI_PER_MINUTE, "ai")
    session = _owned_session(session_id, int(user["id"]))
    style = str(payload.get("style", "two_voice") or "two_voice")
    try:
        script = summariser.generate_podcast_script(session.get("transcript", ""), session.get("title", "Lecture"), style)
        db.update_advanced_outputs(session_id, podcast_script=script, podcast_style=style)
        _update_outputs_for_session(session_id, int(user["id"]))
        return {"podcast_script": script, "podcast_style": style}
    except Exception:
        logging.exception("Failed to create podcast script for session %s", session_id)
        raise HTTPException(status_code=500, detail="Could not write the podcast script. Please try again.")


@app.get("/api/sessions/{session_id}/export")
def export_session(
    session_id: int,
    request: Request,
    format: str = "markdown",
    include_transcript: bool = True,
    include_quiz: bool = True,
    include_flashcards: bool = True,
    include_mind_map: bool = True,
) -> Response:
    user = _current_user(request)
    try:
        options = _export_options_from_query(include_transcript, include_quiz, include_flashcards, include_mind_map)
        session = _update_outputs_for_session(session_id, int(user["id"]), options=options)
        filename_base = f"lecture-session-{session_id}"
        if format == "txt":
            body = session.get("transcript", "")
            return Response(body, media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename_base}-transcript.txt"'})
        if format == "pdf":
            pdf = exporter.generate_pdf(session, options=options)
            return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename_base}.pdf"'})
        body = file_store.build_markdown_export(session, options)
        return Response(body, media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename_base}.md"'})
    except sqlite3.Error:
        raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except Exception:
        logging.exception("Failed to prepare exports for session %s", session_id)
        raise HTTPException(status_code=500, detail="Could not prepare your export.")
