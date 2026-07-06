import logging
from pathlib import Path

import av


def extract_frames(video_path: str, output_dir: Path, max_frames: int = 8) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    frames: list[str] = []

    try:
        container = av.open(video_path)
    except Exception:
        logging.info("Could not open lab video for frame extraction", exc_info=True)
        return frames

    try:
        stream = next((item for item in container.streams if item.type == "video"), None)
        if stream is None:
            return frames

        duration_seconds = 0.0
        if stream.duration and stream.time_base:
            duration_seconds = float(stream.duration * stream.time_base)
        elif container.duration:
            duration_seconds = float(container.duration / av.time_base)

        interval = max(8.0, duration_seconds / max_frames) if duration_seconds else 15.0
        next_capture = 0.0

        for frame in container.decode(stream):
            timestamp = float(frame.pts * stream.time_base) if frame.pts is not None else 0.0
            if timestamp + 0.001 < next_capture:
                continue

            image = frame.to_image()
            image.thumbnail((1280, 720))
            path = output_dir / f"frame-{len(frames) + 1:02d}.jpg"
            image.save(path, "JPEG", quality=82, optimize=True)
            frames.append(str(path.resolve()))
            next_capture = timestamp + interval

            if len(frames) >= max_frames:
                break
    except Exception:
        logging.info("Frame extraction failed", exc_info=True)
    finally:
        container.close()

    return frames
