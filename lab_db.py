import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "labs.db"


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    try:
        with _connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lab_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    transcript TEXT NOT NULL,
                    breakdown TEXT NOT NULL,
                    duration_seconds INTEGER NOT NULL DEFAULT 0,
                    recording_path TEXT,
                    frames_json TEXT NOT NULL DEFAULT '[]',
                    markers_json TEXT NOT NULL DEFAULT '[]',
                    ocr_text TEXT NOT NULL DEFAULT '',
                    transcript_path TEXT,
                    breakdown_path TEXT,
                    combined_path TEXT,
                    pdf_path TEXT
                )
                """
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(lab_sessions)").fetchall()}
            if "ocr_text" not in columns:
                conn.execute("ALTER TABLE lab_sessions ADD COLUMN ocr_text TEXT NOT NULL DEFAULT ''")
            conn.commit()
    except sqlite3.Error:
        logging.exception("Failed to initialize lab database")
        raise


def save_lab_session(
    title: str,
    transcript: str,
    breakdown: str,
    duration_seconds: int,
    recording_path: str,
    frames: list[str],
    markers: list[dict],
    ocr_text: str = "",
) -> int:
    created_at = datetime.now().isoformat(timespec="seconds")
    try:
        with _connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO lab_sessions (
                    title, created_at, transcript, breakdown, duration_seconds,
                    recording_path, frames_json, markers_json, ocr_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    created_at,
                    transcript,
                    breakdown,
                    max(0, int(duration_seconds or 0)),
                    recording_path,
                    json.dumps(frames),
                    json.dumps(markers),
                    ocr_text,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)
    except sqlite3.Error:
        logging.exception("Failed to save lab session")
        raise


def update_lab_breakdown(session_id: int, breakdown: str) -> None:
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE lab_sessions SET breakdown = ? WHERE id = ?",
                (breakdown, session_id),
            )
            conn.commit()
    except sqlite3.Error:
        logging.exception("Failed to update lab breakdown for session %s", session_id)
        raise


def update_lab_outputs(
    session_id: int,
    transcript_path: str | None = None,
    breakdown_path: str | None = None,
    combined_path: str | None = None,
    pdf_path: str | None = None,
) -> None:
    updates = {
        "transcript_path": transcript_path,
        "breakdown_path": breakdown_path,
        "combined_path": combined_path,
        "pdf_path": pdf_path,
    }
    assignments = [f"{column} = ?" for column, value in updates.items() if value is not None]
    values = [value for value in updates.values() if value is not None]
    if not assignments:
        return

    try:
        with _connect() as conn:
            conn.execute(
                f"UPDATE lab_sessions SET {', '.join(assignments)} WHERE id = ?",
                (*values, session_id),
            )
            conn.commit()
    except sqlite3.Error:
        logging.exception("Failed to update lab output paths for session %s", session_id)
        raise


def _decode_session(row: sqlite3.Row) -> dict:
    session = dict(row)
    session["frames"] = json.loads(session.pop("frames_json") or "[]")
    session["markers"] = json.loads(session.pop("markers_json") or "[]")
    return session


def get_lab_sessions(query: str | None = None) -> list[dict]:
    try:
        with _connect() as conn:
            if query:
                term = f"%{query.strip()}%"
                rows = conn.execute(
                    """
                    SELECT id, title, created_at, breakdown, duration_seconds
                    FROM lab_sessions
                    WHERE transcript LIKE ? OR breakdown LIKE ? OR title LIKE ?
                       OR ocr_text LIKE ?
                    ORDER BY created_at DESC, id DESC
                    """,
                    (term, term, term, term),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, title, created_at, breakdown, duration_seconds
                    FROM lab_sessions
                    ORDER BY created_at DESC, id DESC
                    """
                ).fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error:
        logging.exception("Failed to load lab sessions")
        raise


def get_lab_session(session_id: int) -> dict | None:
    try:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT id, title, created_at, transcript, breakdown, duration_seconds,
                       recording_path, frames_json, markers_json, ocr_text, transcript_path,
                       breakdown_path, combined_path, pdf_path
                FROM lab_sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
            return _decode_session(row) if row else None
    except sqlite3.Error:
        logging.exception("Failed to load lab session %s", session_id)
        raise
