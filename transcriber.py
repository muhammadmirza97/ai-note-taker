import logging
from pathlib import Path

from faster_whisper import WhisperModel


_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        logging.info("Loading faster-whisper base model on CPU")
        try:
            _model = WhisperModel("base", device="cpu", compute_type="int8", local_files_only=True)
        except Exception:
            logging.info("Local faster-whisper cache unavailable; attempting model download", exc_info=True)
            _model = WhisperModel("base", device="cpu", compute_type="int8")
    return _model


def transcribe(audio_path: str) -> str:
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    segments, _info = _get_model().transcribe(str(path), beam_size=5)
    transcript_parts = []
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        transcript_parts.append(f"[{_format_timestamp(segment.start)}] {text}")
    transcript = "\n".join(transcript_parts)
    return transcript.strip()


def _format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    remainder = total % 60
    if hours:
        return f"{hours}:{minutes:02d}:{remainder:02d}"
    return f"{minutes}:{remainder:02d}"
