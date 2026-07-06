from pathlib import Path

from fpdf import FPDF


def _pdf_text(value: object) -> str:
    text = "" if value is None else str(value)
    return text.encode("latin-1", "replace").decode("latin-1")


def _section(pdf: FPDF, heading: str, body: str) -> None:
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 9, _pdf_text(heading), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, _pdf_text(body))
    pdf.ln(5)


def generate_pdf(session: dict) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.multi_cell(0, 10, _pdf_text(session["title"]))
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, _pdf_text(f"Date: {session['created_at']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0,
        8,
        _pdf_text(f"Duration: {session.get('duration_seconds', 0)} seconds"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(6)

    _section(pdf, "Lab Breakdown", session.get("breakdown", ""))

    markers = session.get("markers") or []
    if markers:
        marker_lines = []
        for marker in markers:
            elapsed = int(marker.get("elapsed_seconds") or 0)
            note = str(marker.get("note") or "Marker")
            marker_lines.append(f"{elapsed // 60}:{elapsed % 60:02d} - {note}")
        _section(pdf, "Markers", "\n".join(marker_lines))

    ocr_text = str(session.get("ocr_text", "")).strip()
    if ocr_text:
        _section(pdf, "Screen Text", ocr_text)

    frames = [Path(path) for path in session.get("frames", []) if Path(path).exists()]
    if frames:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 9, "Screen Frames", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        for frame in frames[:6]:
            if pdf.get_y() > 210:
                pdf.add_page()
            pdf.image(str(frame), w=170)
            pdf.ln(5)

    _section(pdf, "Transcript", session.get("transcript", ""))

    result = pdf.output(dest="S")
    if isinstance(result, str):
        return result.encode("latin-1")
    return bytes(result)
