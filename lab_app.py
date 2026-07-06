import json
import logging
import os
import shutil
import sqlite3
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import lab_db
import lab_exporter
import lab_file_store
import lab_ocr
import lab_summariser
import lab_video
import transcriber


BASE_DIR = Path(__file__).resolve().parent
STATIC_LABS_DIR = BASE_DIR / "static_labs"
BREAKDOWN_PENDING = "Lab breakdown is being generated. The transcript and recording are already saved."

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="Personal Lab Notes")
app.mount("/static-labs", StaticFiles(directory=STATIC_LABS_DIR), name="static_labs")

executor = ThreadPoolExecutor(max_workers=1)
jobs_lock = threading.Lock()
jobs: dict[str, dict] = {}


@app.on_event("startup")
def startup() -> None:
    lab_db.init_db()
    lab_file_store.ensure_output_dirs()


@app.exception_handler(HTTPException)
async def http_exception_handler(_request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request, exc: Exception) -> JSONResponse:
    logging.exception("Unhandled lab server error: %s", exc)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_LABS_DIR / "index.html")


def _set_job(job_id: str, **updates) -> None:
    with jobs_lock:
        job = jobs.setdefault(job_id, {})
        job.update(updates)


def _get_job(job_id: str) -> dict | None:
    with jobs_lock:
        job = jobs.get(job_id)
        return dict(job) if job else None


def _list_jobs() -> list[dict]:
    with jobs_lock:
        return [{"job_id": job_id, **job} for job_id, job in jobs.items()]


def _queue_position(job_id: str) -> int | None:
    with jobs_lock:
        queued_ids = [
            queued_job_id
            for queued_job_id, job in sorted(jobs.items(), key=lambda item: item[1].get("created_at", ""))
            if job.get("status") == "queued"
        ]
    if job_id not in queued_ids:
        return None
    return queued_ids.index(job_id) + 1


def _suffix_for_upload(upload: UploadFile) -> str:
    content_type = (upload.content_type or "").lower()
    filename = (upload.filename or "").lower()
    if "mp4" in content_type or filename.endswith(".mp4"):
        return ".mp4"
    if "quicktime" in content_type or filename.endswith(".mov"):
        return ".mov"
    return ".webm"


def _parse_markers(raw_markers: str | None) -> list[dict]:
    if not raw_markers:
        return []
    try:
        data = json.loads(raw_markers)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []

    markers = []
    for marker in data[:100]:
        if not isinstance(marker, dict):
            continue
        note = str(marker.get("note") or "").strip()[:300]
        elapsed = max(0, int(marker.get("elapsed_seconds") or 0))
        if note:
            markers.append({"note": note, "elapsed_seconds": elapsed})
    return markers


def _process_lab_recording(job_id: str, recording_path: str, duration_seconds: int, markers: list[dict]) -> None:
    try:
        frames_dir = lab_file_store.FRAMES_DIR / job_id
        _set_job(job_id, status="extracting", message="Extracting screen frames")
        frames = lab_video.extract_frames(recording_path, frames_dir)

        _set_job(job_id, status="reading", message="Reading screen text", frame_count=len(frames))
        ocr_text = lab_ocr.read_frames(frames)

        _set_job(job_id, status="transcribing", message="Transcribing lab audio", frame_count=len(frames))
        try:
            transcript = transcriber.transcribe(recording_path)
        except Exception:
            logging.info("Lab recording had no readable audio; continuing with visual anchors only", exc_info=True)
            transcript = ""

        title = f"Lab Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        session_id = lab_db.save_lab_session(
            title=title,
            transcript=transcript,
            breakdown=BREAKDOWN_PENDING,
            duration_seconds=duration_seconds,
            recording_path=str(Path(recording_path).resolve()),
            frames=frames,
            markers=markers,
            ocr_text=ocr_text,
        )
        session = lab_db.get_lab_session(session_id)
        output_paths = lab_file_store.write_outputs(session, include_breakdown=False) if session else {}
        if output_paths:
            lab_db.update_lab_outputs(session_id, **output_paths)

        _set_job(
            job_id,
            status="breaking_down",
            message="Building lab breakdown",
            session_id=session_id,
            transcript=transcript,
            breakdown=BREAKDOWN_PENDING,
            output_paths=output_paths,
            ocr_text=ocr_text,
        )

        breakdown = lab_summariser.summarise_lab(transcript, markers, len(frames), ocr_text)
        lab_db.update_lab_breakdown(session_id, breakdown)
        session = lab_db.get_lab_session(session_id)
        output_paths = lab_file_store.write_outputs(session, include_breakdown=True) if session else output_paths
        if output_paths:
            lab_db.update_lab_outputs(session_id, **output_paths)

        _set_job(
            job_id,
            status="completed",
            message="Complete",
            session_id=session_id,
            transcript=transcript,
            breakdown=breakdown,
            output_paths=output_paths,
            frame_count=len(frames),
            ocr_text=ocr_text,
        )
    except sqlite3.Error:
        logging.exception("Database error while processing lab job %s", job_id)
        _set_job(job_id, status="failed", message="Database error", error="Database error")
    except Exception:
        logging.exception("Failed to process lab job %s", job_id)
        _set_job(job_id, status="failed", message="Failed", error="Failed to process lab recording")


@app.post("/api/labs")
async def create_lab(
    recording: UploadFile = File(...),
    duration_seconds: int = Form(0),
    markers: str | None = Form(None),
) -> Response:
    content_type = (recording.content_type or "").lower()
    if not (
        content_type.startswith("video/")
        or content_type.startswith("audio/")
        or content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="Upload must be a screen or audio recording")

    temp_path = ""
    try:
        suffix = _suffix_for_upload(recording)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            while chunk := await recording.read(1024 * 1024):
                temp_file.write(chunk)

        job_id = uuid.uuid4().hex
        lab_file_store.ensure_output_dirs()
        recording_path = lab_file_store.RECORDINGS_DIR / f"lab-{job_id}{suffix}"
        shutil.move(temp_path, recording_path)
        temp_path = ""

        safe_duration = max(0, int(duration_seconds or 0))
        parsed_markers = _parse_markers(markers)
        _set_job(
            job_id,
            status="queued",
            message="Queued",
            created_at=datetime.now().isoformat(timespec="seconds"),
            duration_seconds=safe_duration,
            frame_count=0,
        )
        executor.submit(_process_lab_recording, job_id, str(recording_path), safe_duration, parsed_markers)
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"job_id": job_id, "status": "queued", "message": "Lab processing started"},
        )
    except HTTPException:
        raise
    except Exception:
        logging.exception("Failed to accept lab upload")
        raise HTTPException(status_code=500, detail="Failed to accept lab recording")
    finally:
        await recording.close()
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


@app.get("/api/labs/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = _get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    payload = {"job_id": job_id, **job}
    position = _queue_position(job_id)
    if position is not None:
        payload["queue_position"] = position
        payload["message"] = f"Queued at position {position}"
    return payload


@app.get("/api/labs/jobs")
def list_jobs() -> list[dict]:
    return _list_jobs()


@app.get("/api/labs")
def list_labs(q: str | None = None) -> list[dict]:
    try:
        return lab_db.get_lab_sessions(q)
    except sqlite3.Error:
        raise HTTPException(status_code=500, detail="Database error")


@app.get("/api/labs/{session_id}")
def lab_detail(session_id: int) -> dict:
    try:
        session = lab_db.get_lab_session(session_id)
    except sqlite3.Error:
        raise HTTPException(status_code=500, detail="Database error")

    if session is None:
        raise HTTPException(status_code=404, detail="Lab session not found")
    return session


@app.get("/api/labs/{session_id}/frames/{frame_index}")
def lab_frame(session_id: int, frame_index: int) -> FileResponse:
    try:
        session = lab_db.get_lab_session(session_id)
    except sqlite3.Error:
        raise HTTPException(status_code=500, detail="Database error")

    if session is None:
        raise HTTPException(status_code=404, detail="Lab session not found")

    frames = session.get("frames") or []
    if frame_index < 0 or frame_index >= len(frames):
        raise HTTPException(status_code=404, detail="Frame not found")

    frame_path = Path(frames[frame_index]).resolve()
    allowed_root = lab_file_store.FRAMES_DIR.resolve()
    if allowed_root not in frame_path.parents:
        raise HTTPException(status_code=403, detail="Frame path is outside lab outputs")
    if not frame_path.exists():
        raise HTTPException(status_code=404, detail="Frame file not found")

    return FileResponse(frame_path)


@app.get("/api/labs/{session_id}/export")
def export_lab(session_id: int) -> Response:
    try:
        session = lab_db.get_lab_session(session_id)
    except sqlite3.Error:
        raise HTTPException(status_code=500, detail="Database error")

    if session is None:
        raise HTTPException(status_code=404, detail="Lab session not found")

    try:
        output_paths = lab_file_store.write_outputs(session, include_breakdown=True)
        lab_db.update_lab_outputs(session_id, **output_paths)
        pdf = lab_exporter.generate_pdf(session)
    except Exception:
        logging.exception("Failed to generate lab PDF for session %s", session_id)
        raise HTTPException(status_code=500, detail="Failed to generate PDF")

    filename = f"lab-session-{session_id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/labs/outputs/locations")
def output_locations() -> dict:
    return {
        "outputs_dir": str(lab_file_store.OUTPUTS_DIR.resolve()),
        "recordings_dir": str(lab_file_store.RECORDINGS_DIR.resolve()),
        "frames_dir": str(lab_file_store.FRAMES_DIR.resolve()),
        "breakdowns_dir": str(lab_file_store.BREAKDOWNS_DIR.resolve()),
        "pdfs_dir": str(lab_file_store.PDFS_DIR.resolve()),
        "combined_dir": str(lab_file_store.COMBINED_DIR.resolve()),
        "ocr_available": lab_ocr.ocr_available(),
    }


@app.post("/api/labs/outputs/open")
def open_outputs_folder() -> dict:
    lab_file_store.ensure_output_dirs()
    try:
        os.startfile(str(lab_file_store.OUTPUTS_DIR.resolve()))
    except Exception:
        logging.exception("Failed to open lab outputs folder")
        raise HTTPException(status_code=500, detail="Failed to open lab outputs folder")
    return {"opened": True, "path": str(lab_file_store.OUTPUTS_DIR.resolve())}
