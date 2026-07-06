import logging
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "notes.db"


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db() -> None:
    try:
        with _connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    transcript TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    duration_seconds INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            migrations = {
                "transcript_path": "ALTER TABLE sessions ADD COLUMN transcript_path TEXT",
                "summary_path": "ALTER TABLE sessions ADD COLUMN summary_path TEXT",
                "pdf_path": "ALTER TABLE sessions ADD COLUMN pdf_path TEXT",
                "combined_path": "ALTER TABLE sessions ADD COLUMN combined_path TEXT",
                "source_type": "ALTER TABLE sessions ADD COLUMN source_type TEXT NOT NULL DEFAULT 'recorded'",
                "status": "ALTER TABLE sessions ADD COLUMN status TEXT NOT NULL DEFAULT 'completed'",
                "short_summary": "ALTER TABLE sessions ADD COLUMN short_summary TEXT NOT NULL DEFAULT ''",
                "detailed_summary": "ALTER TABLE sessions ADD COLUMN detailed_summary TEXT NOT NULL DEFAULT ''",
                "key_points": "ALTER TABLE sessions ADD COLUMN key_points TEXT NOT NULL DEFAULT ''",
                "terms": "ALTER TABLE sessions ADD COLUMN terms TEXT NOT NULL DEFAULT ''",
                "quiz": "ALTER TABLE sessions ADD COLUMN quiz TEXT NOT NULL DEFAULT ''",
                "quiz_json": "ALTER TABLE sessions ADD COLUMN quiz_json TEXT NOT NULL DEFAULT ''",
                "mind_map_json": "ALTER TABLE sessions ADD COLUMN mind_map_json TEXT NOT NULL DEFAULT ''",
                "video_script": "ALTER TABLE sessions ADD COLUMN video_script TEXT NOT NULL DEFAULT ''",
                "podcast_script": "ALTER TABLE sessions ADD COLUMN podcast_script TEXT NOT NULL DEFAULT ''",
                "podcast_style": "ALTER TABLE sessions ADD COLUMN podcast_style TEXT NOT NULL DEFAULT 'two_voice'",
                "lesson_breakdown": "ALTER TABLE sessions ADD COLUMN lesson_breakdown TEXT NOT NULL DEFAULT ''",
                "error_message": "ALTER TABLE sessions ADD COLUMN error_message TEXT NOT NULL DEFAULT ''",
                "user_id": "ALTER TABLE sessions ADD COLUMN user_id INTEGER",
            }
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
            for column, sql in migrations.items():
                if column not in columns:
                    conn.execute(sql)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    csrf_token TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    session_id INTEGER,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    step INTEGER NOT NULL DEFAULT 1,
                    message TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE SET NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_token ON auth_sessions(token)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS flashcards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    front TEXT NOT NULL,
                    back TEXT NOT NULL,
                    topic TEXT NOT NULL DEFAULT 'General',
                    status TEXT NOT NULL DEFAULT 'new',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    total INTEGER NOT NULL,
                    percent INTEGER NOT NULL,
                    results_json TEXT NOT NULL,
                    focus_topic TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
                """
            )
            conn.commit()
    except sqlite3.Error:
        logging.exception("Failed to initialize database")
        raise


def save_session(
    title: str,
    transcript: str,
    summary: str,
    duration_seconds: int,
    source_type: str = "recorded",
    status: str = "processing",
    user_id: int | None = None,
) -> int:
    created_at = datetime.now().isoformat(timespec="seconds")
    try:
        with _connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO sessions (
                    title, created_at, transcript, summary, duration_seconds,
                    source_type, status, detailed_summary, user_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    created_at,
                    transcript,
                    summary,
                    max(0, int(duration_seconds or 0)),
                    source_type,
                    status,
                    summary if status == "completed" else "",
                    user_id,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)
    except sqlite3.Error:
        logging.exception("Failed to save session")
        raise


def get_sessions(query: str | None = None, date_filter: str | None = None, user_id: int | None = None) -> list[dict]:
    try:
        with _connect() as conn:
            clauses = []
            values: list[str | int] = []
            if user_id is not None:
                clauses.append("user_id = ?")
                values.append(user_id)
            if query:
                term = f"%{query.strip()}%"
                clauses.append(
                    "(transcript LIKE ? OR summary LIKE ? OR title LIKE ? OR key_points LIKE ? OR terms LIKE ?)"
                )
                values.extend([term, term, term, term, term])

            if date_filter and date_filter != "all":
                now = datetime.now()
                if date_filter == "today":
                    clauses.append("date(created_at) = date(?)")
                    values.append(now.isoformat(timespec="seconds"))
                elif date_filter == "week":
                    clauses.append("datetime(created_at) >= datetime(?, '-7 days')")
                    values.append(now.isoformat(timespec="seconds"))
                elif date_filter == "month":
                    clauses.append("datetime(created_at) >= datetime(?, '-30 days')")
                    values.append(now.isoformat(timespec="seconds"))

            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = conn.execute(
                f"""
                SELECT id, title, created_at, summary, duration_seconds,
                       source_type, status, error_message, user_id
                FROM sessions
                {where}
                ORDER BY created_at DESC, id DESC
                """,
                values,
            ).fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error:
        logging.exception("Failed to load sessions")
        raise


def update_session_summary(session_id: int, summary: str) -> None:
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE sessions SET summary = ?, detailed_summary = ? WHERE id = ?",
                (summary, summary, session_id),
            )
            conn.commit()
    except sqlite3.Error:
        logging.exception("Failed to update summary for session %s", session_id)
        raise


def update_session_status(session_id: int, status: str, error_message: str = "") -> None:
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE sessions SET status = ?, error_message = ? WHERE id = ?",
                (status, error_message, session_id),
            )
            conn.commit()
    except sqlite3.Error:
        logging.exception("Failed to update status for session %s", session_id)
        raise


def update_session_study_outputs(
    session_id: int,
    short_summary: str | None = None,
    detailed_summary: str | None = None,
    key_points: str | None = None,
    terms: str | None = None,
    quiz: str | None = None,
    quiz_json: str | None = None,
    status: str | None = None,
) -> None:
    updates = {
        "short_summary": short_summary,
        "detailed_summary": detailed_summary,
        "summary": detailed_summary,
        "key_points": key_points,
        "terms": terms,
        "quiz": quiz,
        "quiz_json": quiz_json,
        "status": status,
    }
    assignments = [f"{column} = ?" for column, value in updates.items() if value is not None]
    values = [value for value in updates.values() if value is not None]
    if not assignments:
        return

    try:
        with _connect() as conn:
            conn.execute(
                f"UPDATE sessions SET {', '.join(assignments)} WHERE id = ?",
                (*values, session_id),
            )
            conn.commit()
    except sqlite3.Error:
        logging.exception("Failed to update study outputs for session %s", session_id)
        raise


def update_session_outputs(
    session_id: int,
    transcript_path: str | None = None,
    summary_path: str | None = None,
    pdf_path: str | None = None,
    combined_path: str | None = None,
) -> None:
    updates = {
        "transcript_path": transcript_path,
        "summary_path": summary_path,
        "pdf_path": pdf_path,
        "combined_path": combined_path,
    }
    assignments = [f"{column} = ?" for column, value in updates.items() if value is not None]
    values = [value for value in updates.values() if value is not None]
    if not assignments:
        return

    try:
        with _connect() as conn:
            conn.execute(
                f"UPDATE sessions SET {', '.join(assignments)} WHERE id = ?",
                (*values, session_id),
            )
            conn.commit()
    except sqlite3.Error:
        logging.exception("Failed to update output paths for session %s", session_id)
        raise


def get_session(session_id: int, user_id: int | None = None) -> dict | None:
    try:
        with _connect() as conn:
            clauses = ["id = ?"]
            values: list[int] = [session_id]
            if user_id is not None:
                clauses.append("user_id = ?")
                values.append(user_id)
            row = conn.execute(
                """
                SELECT id, title, created_at, transcript, summary, duration_seconds,
                       transcript_path, summary_path, pdf_path, combined_path,
                       source_type, status, short_summary, detailed_summary,
                       key_points, terms, quiz, quiz_json, mind_map_json,
                       video_script, podcast_script, podcast_style, lesson_breakdown,
                       error_message, user_id
                FROM sessions
                WHERE """ + " AND ".join(clauses) + """
                """,
                values,
            ).fetchone()
            return dict(row) if row else None
    except sqlite3.Error:
        logging.exception("Failed to load session %s", session_id)
        raise


def update_advanced_outputs(
    session_id: int,
    mind_map_json: str | None = None,
    video_script: str | None = None,
    podcast_script: str | None = None,
    podcast_style: str | None = None,
    lesson_breakdown: str | None = None,
) -> None:
    updates = {
        "mind_map_json": mind_map_json,
        "video_script": video_script,
        "podcast_script": podcast_script,
        "podcast_style": podcast_style,
        "lesson_breakdown": lesson_breakdown,
    }
    assignments = [f"{column} = ?" for column, value in updates.items() if value is not None]
    values = [value for value in updates.values() if value is not None]
    if not assignments:
        return
    try:
        with _connect() as conn:
            conn.execute(
                f"UPDATE sessions SET {', '.join(assignments)} WHERE id = ?",
                (*values, session_id),
            )
            conn.commit()
    except sqlite3.Error:
        logging.exception("Failed to update advanced outputs for session %s", session_id)
        raise


def set_session_quiz(session_id: int, quiz_text: str, quiz_questions: list[dict]) -> None:
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE sessions SET quiz = ?, quiz_json = ?, status = 'completed' WHERE id = ?",
                (quiz_text, json.dumps(quiz_questions), session_id),
            )
            conn.commit()
    except sqlite3.Error:
        logging.exception("Failed to update quiz for session %s", session_id)
        raise


def add_chat_message(session_id: int, role: str, content: str) -> dict:
    created_at = datetime.now().isoformat(timespec="seconds")
    try:
        with _connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO chat_messages (session_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content, created_at),
            )
            conn.commit()
            return {
                "id": int(cursor.lastrowid),
                "session_id": session_id,
                "role": role,
                "content": content,
                "created_at": created_at,
            }
    except sqlite3.Error:
        logging.exception("Failed to add chat message for session %s", session_id)
        raise


def get_chat_messages(session_id: int) -> list[dict]:
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, role, content, created_at
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error:
        logging.exception("Failed to load chat messages for session %s", session_id)
        raise


def clear_chat_messages(session_id: int) -> None:
    try:
        with _connect() as conn:
            conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            conn.commit()
    except sqlite3.Error:
        logging.exception("Failed to clear chat messages for session %s", session_id)
        raise


def replace_flashcards(session_id: int, cards: list[dict]) -> list[dict]:
    now = datetime.now().isoformat(timespec="seconds")
    try:
        with _connect() as conn:
            conn.execute("DELETE FROM flashcards WHERE session_id = ?", (session_id,))
            for card in cards:
                conn.execute(
                    """
                    INSERT INTO flashcards (session_id, front, back, topic, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'new', ?, ?)
                    """,
                    (session_id, card["front"], card["back"], card.get("topic") or "General", now, now),
                )
            conn.commit()
        return get_flashcards(session_id)
    except sqlite3.Error:
        logging.exception("Failed to replace flashcards for session %s", session_id)
        raise


def get_flashcards(session_id: int) -> list[dict]:
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, front, back, topic, status, created_at, updated_at
                FROM flashcards
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error:
        logging.exception("Failed to load flashcards for session %s", session_id)
        raise


def update_flashcard_status(card_id: int, status: str, user_id: int | None = None) -> dict | None:
    now = datetime.now().isoformat(timespec="seconds")
    try:
        with _connect() as conn:
            if user_id is None:
                conn.execute(
                    "UPDATE flashcards SET status = ?, updated_at = ? WHERE id = ?",
                    (status, now, card_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE flashcards
                    SET status = ?, updated_at = ?
                    WHERE id = ? AND session_id IN (SELECT id FROM sessions WHERE user_id = ?)
                    """,
                    (status, now, card_id, user_id),
                )
            row = conn.execute(
                """
                SELECT flashcards.id, flashcards.session_id, front, back, topic,
                       flashcards.status, flashcards.created_at, flashcards.updated_at
                FROM flashcards
                JOIN sessions ON sessions.id = flashcards.session_id
                WHERE flashcards.id = ?
                """ + (" AND sessions.user_id = ?" if user_id is not None else "") + """
                """,
                (card_id, user_id) if user_id is not None else (card_id,),
            ).fetchone()
            conn.commit()
            return dict(row) if row else None
    except sqlite3.Error:
        logging.exception("Failed to update flashcard %s", card_id)
        raise


def delete_flashcard(card_id: int, user_id: int | None = None) -> None:
    try:
        with _connect() as conn:
            if user_id is None:
                conn.execute("DELETE FROM flashcards WHERE id = ?", (card_id,))
            else:
                conn.execute(
                    """
                    DELETE FROM flashcards
                    WHERE id = ? AND session_id IN (SELECT id FROM sessions WHERE user_id = ?)
                    """,
                    (card_id, user_id),
                )
            conn.commit()
    except sqlite3.Error:
        logging.exception("Failed to delete flashcard %s", card_id)
        raise


def add_quiz_attempt(
    session_id: int,
    score: int,
    total: int,
    percent: int,
    results: list[dict],
    focus_topic: str = "",
) -> dict:
    created_at = datetime.now().isoformat(timespec="seconds")
    try:
        with _connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO quiz_attempts (session_id, created_at, score, total, percent, results_json, focus_topic)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, created_at, score, total, percent, json.dumps(results), focus_topic),
            )
            conn.commit()
            return {
                "id": int(cursor.lastrowid),
                "session_id": session_id,
                "created_at": created_at,
                "score": score,
                "total": total,
                "percent": percent,
                "results": results,
                "focus_topic": focus_topic,
            }
    except sqlite3.Error:
        logging.exception("Failed to add quiz attempt for session %s", session_id)
        raise


def get_quiz_attempts(session_id: int) -> list[dict]:
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, created_at, score, total, percent, results_json, focus_topic
                FROM quiz_attempts
                WHERE session_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (session_id,),
            ).fetchall()
            attempts = []
            for row in rows:
                item = dict(row)
                item["results"] = json.loads(item.pop("results_json") or "[]")
                attempts.append(item)
            return attempts
    except sqlite3.Error:
        logging.exception("Failed to load quiz attempts for session %s", session_id)
        raise


def get_all_quiz_attempts(user_id: int | None = None) -> dict[int, list[dict]]:
    attempts_by_session: dict[int, list[dict]] = {}
    try:
        with _connect() as conn:
            where = "WHERE sessions.user_id = ?" if user_id is not None else ""
            params = (user_id,) if user_id is not None else ()
            rows = conn.execute(
                """
                SELECT quiz_attempts.id, session_id, quiz_attempts.created_at, score, total, percent,
                       results_json, focus_topic
                FROM quiz_attempts
                JOIN sessions ON sessions.id = quiz_attempts.session_id
                """ + where + """
                ORDER BY quiz_attempts.created_at DESC, quiz_attempts.id DESC
                """,
                params,
            ).fetchall()
            for row in rows:
                item = dict(row)
                item["results"] = json.loads(item.pop("results_json") or "[]")
                attempts_by_session.setdefault(int(item["session_id"]), []).append(item)
            return attempts_by_session
    except sqlite3.Error:
        logging.exception("Failed to load all quiz attempts")
        raise


def get_all_flashcards(user_id: int | None = None) -> dict[int, list[dict]]:
    cards_by_session: dict[int, list[dict]] = {}
    try:
        with _connect() as conn:
            where = "WHERE sessions.user_id = ?" if user_id is not None else ""
            params = (user_id,) if user_id is not None else ()
            rows = conn.execute(
                """
                SELECT flashcards.id, session_id, front, back, topic, flashcards.status,
                       flashcards.created_at, flashcards.updated_at
                FROM flashcards
                JOIN sessions ON sessions.id = flashcards.session_id
                """ + where + """
                ORDER BY flashcards.id ASC
                """,
                params,
            ).fetchall()
            for row in rows:
                item = dict(row)
                cards_by_session.setdefault(int(item["session_id"]), []).append(item)
            return cards_by_session
    except sqlite3.Error:
        logging.exception("Failed to load all flashcards")
        raise


def count_users() -> int:
    with _connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])


def create_user(email: str, password_hash: str) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (email, password_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (email.lower(), password_hash, now, now),
        )
        conn.commit()
        return {"id": int(cursor.lastrowid), "email": email.lower(), "created_at": now}


def get_user_by_email(email: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash, created_at, updated_at FROM users WHERE email = ?",
            (email.lower(),),
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, email, created_at, updated_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def update_user_password(user_id: int, password_hash: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (password_hash, now, user_id),
        )
        conn.commit()


def create_auth_session(user_id: int, token: str, csrf_token: str, days: int = 30) -> dict:
    now = datetime.now()
    expires_at = now + timedelta(days=days)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO auth_sessions (user_id, token, csrf_token, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                token,
                csrf_token,
                now.isoformat(timespec="seconds"),
                expires_at.isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    return {"token": token, "csrf_token": csrf_token, "expires_at": expires_at.isoformat(timespec="seconds")}


def get_auth_session(token: str) -> dict | None:
    if not token:
        return None
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT auth_sessions.id, auth_sessions.user_id, auth_sessions.token,
                   auth_sessions.csrf_token, auth_sessions.expires_at, users.email
            FROM auth_sessions
            JOIN users ON users.id = auth_sessions.user_id
            WHERE auth_sessions.token = ?
            """,
            (token,),
        ).fetchone()
        if not row:
            return None
        item = dict(row)
        if datetime.fromisoformat(item["expires_at"]) <= datetime.now():
            conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
            conn.commit()
            return None
        return item


def delete_auth_session(token: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
        conn.commit()


def assign_legacy_sessions_to_user(user_id: int) -> int:
    with _connect() as conn:
        cursor = conn.execute("UPDATE sessions SET user_id = ? WHERE user_id IS NULL", (user_id,))
        conn.commit()
        return int(cursor.rowcount)


def upsert_job(job: dict) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    created_at = job.get("created_at") or now
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, user_id, session_id, kind, status, step, message, error,
                attempts, max_attempts, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                session_id = excluded.session_id,
                status = excluded.status,
                step = excluded.step,
                message = excluded.message,
                error = excluded.error,
                attempts = excluded.attempts,
                max_attempts = excluded.max_attempts,
                updated_at = excluded.updated_at
            """,
            (
                job["id"],
                int(job["user_id"]),
                job.get("session_id"),
                job.get("kind") or "lecture",
                job.get("status") or "queued",
                int(job.get("step") or 1),
                job.get("message") or "",
                job.get("error") or "",
                int(job.get("attempts") or 0),
                int(job.get("max_attempts") or 3),
                created_at,
                now,
            ),
        )
        conn.commit()


def get_job(job_id: str, user_id: int | None = None) -> dict | None:
    with _connect() as conn:
        clauses = ["id = ?"]
        values: list[str | int] = [job_id]
        if user_id is not None:
            clauses.append("user_id = ?")
            values.append(user_id)
        row = conn.execute(
            f"""
            SELECT id, user_id, session_id, kind, status, step, message, error,
                   attempts, max_attempts, created_at, updated_at
            FROM jobs
            WHERE {' AND '.join(clauses)}
            """,
            values,
        ).fetchone()
        return dict(row) if row else None


def list_jobs(user_id: int | None = None, limit: int = 25) -> list[dict]:
    with _connect() as conn:
        where = "WHERE user_id = ?" if user_id is not None else ""
        params: tuple[int, ...] = (user_id,) if user_id is not None else ()
        rows = conn.execute(
            f"""
            SELECT id, user_id, session_id, kind, status, step, message, error,
                   attempts, max_attempts, created_at, updated_at
            FROM jobs
            {where}
            ORDER BY created_at DESC
            LIMIT {int(limit)}
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]


def job_metrics() -> dict:
    with _connect() as conn:
        rows = conn.execute("SELECT status, COUNT(*) AS count FROM jobs GROUP BY status").fetchall()
        recent_failures = conn.execute(
            """
            SELECT id, user_id, session_id, kind, status, message, updated_at
            FROM jobs
            WHERE status = 'failed'
            ORDER BY updated_at DESC
            LIMIT 5
            """
        ).fetchall()
        return {
            "jobs_by_status": {row["status"]: int(row["count"]) for row in rows},
            "recent_failures": [dict(row) for row in recent_failures],
        }
