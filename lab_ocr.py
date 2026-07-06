import logging
import re
import shutil
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def _find_tesseract() -> str | None:
    command = shutil.which("tesseract")
    if command:
        return command

    candidates = [
        Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
        Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _get_pytesseract():
    tesseract_cmd = _find_tesseract()
    if not tesseract_cmd:
        return None
    try:
        import pytesseract
    except Exception:
        return None
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    return pytesseract


def ocr_available() -> bool:
    return _get_pytesseract() is not None


def _prepare_image(path: str) -> Image.Image:
    image = Image.open(path).convert("L")
    image = ImageOps.autocontrast(image)
    image = ImageEnhance.Contrast(image).enhance(2.1)
    image = image.filter(ImageFilter.SHARPEN)
    width, height = image.size
    if width < 1800:
        scale = 1800 / max(1, width)
        image = image.resize((int(width * scale), int(height * scale)))
    image = image.point(lambda value: 255 if value > 175 else 0)
    return image


def _clean_text(text: str) -> str:
    def normalize_interface(match: re.Match) -> str:
        value = match.group(1).lower()
        value = value.replace("@", "0").replace("o", "0")
        value = re.sub(r"^ga/", "g0/", value)
        value = re.sub(r"/e0?$", "/0", value)
        return f"interface {value}"

    lines = []
    seen = set()
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        line = re.sub(r"Router\(config[})]\)#", "Router(config)#", line)
        line = re.sub(r"(?i)\bip\s*address\b", "ip address", line)
        line = re.sub(r"(?i)\bip address\.", "ip address", line)
        line = re.sub(r"(?<=\d),(?=\d)", ".", line)
        line = re.sub(r"(?<=\d)@(?=\D|$)", "0", line)
        line = re.sub(r"(?<=\.)@(?=\D|$)", "0", line)
        line = re.sub(r"(?i)\binterface\s+([a-z0-9@]+/[a-z0-9@]+)", normalize_interface, line)
        line = re.sub(r"\b([Gg])O/(\d)\b", r"g0/\2", line)
        line = re.sub(r"\b([Gg])(\d)/(\d)\b", r"g\2/\3", line)
        line = re.sub(r"(?i)\binterface\s+2(\d/\d)\b", r"interface g\1", line)
        line = re.sub(r"(?i)\binterface\s+9(\d/\d)\b", r"interface g\1", line)
        line = re.sub(r"(?i)inputdetected", "input detected", line)
        line = re.sub(r"(?i)inputdetacted", "input detected", line)
        if len(line) < 3:
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(line)
    return "\n".join(lines)


def read_frames(frame_paths: list[str], max_chars: int = 12000) -> str:
    pytesseract = _get_pytesseract()
    if pytesseract is None:
        return ""

    chunks: list[str] = []
    for index, frame_path in enumerate(frame_paths, start=1):
        path = Path(frame_path)
        if not path.exists():
            continue
        try:
            image = _prepare_image(str(path))
            config = "--oem 3 --psm 6 -c preserve_interword_spaces=1"
            text = pytesseract.image_to_string(image, config=config)
            cleaned = _clean_text(text)
        except Exception:
            logging.info("OCR failed for frame %s", frame_path, exc_info=True)
            continue
        if cleaned:
            chunks.append(f"Frame {index}\n{cleaned}")
        if sum(len(chunk) for chunk in chunks) >= max_chars:
            break

    return "\n\n".join(chunks)[:max_chars].strip()
