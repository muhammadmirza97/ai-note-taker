from fpdf import FPDF

import advanced_outputs


def _value(session: dict, key: str, fallback: str = "") -> str:
    value = session.get(key)
    if value:
        return str(value)
    return fallback


def _pdf_text(value: object) -> str:
    text = "" if value is None else str(value)
    return text.encode("latin-1", "replace").decode("latin-1")


class NotesPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)


def _section(pdf: FPDF, heading: str, body: str, empty: str = "None mentioned.") -> None:
    content = str(body or "").strip() or empty
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 9, _pdf_text(heading), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, _pdf_text(content))
    pdf.ln(5)


def generate_pdf(session: dict, options: dict | None = None) -> bytes:
    options = {
        "include_transcript": True,
        "include_quiz": True,
        "include_flashcards": True,
        "include_mind_map": True,
        **(options or {}),
    }
    pdf = NotesPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 22)
    pdf.multi_cell(0, 11, _pdf_text(session["title"]))
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, _pdf_text(f"Date: {session['created_at']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, _pdf_text(f"Source: {_value(session, 'source_type', 'recorded')}"), new_x="LMARGIN", new_y="NEXT")
    duration = int(session.get("duration_seconds") or 0)
    if duration:
        pdf.cell(0, 8, _pdf_text(f"Duration: {duration // 60}:{duration % 60:02d}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    _optional_section(pdf, "Short Summary", _value(session, "short_summary"))
    _optional_section(pdf, "Detailed Notes", _value(session, "detailed_summary", _value(session, "summary")))
    _optional_section(pdf, "Lesson Breakdown", _value(session, "lesson_breakdown"))
    _optional_section(pdf, "Key Points", _value(session, "key_points"))
    _optional_section(pdf, "Important Terms", _value(session, "terms"))
    if options["include_mind_map"] and session.get("mind_map"):
        _mind_map_visual(pdf, session["mind_map"])
    if options["include_quiz"]:
        _optional_section(pdf, "Quiz", _value(session, "quiz"))
    if options["include_flashcards"]:
        _optional_section(pdf, "Flashcards", _flashcards_text(session.get("flashcards") or []))
    _optional_section(pdf, "Recommended Revision Plan", _value(session, "revision_plan"))
    if options["include_transcript"]:
        _section(pdf, "Transcript Appendix", _value(session, "transcript"), empty="No transcript available.")

    result = pdf.output()
    if isinstance(result, str):
        return result.encode("latin-1")
    return bytes(result)


def _optional_section(pdf: FPDF, heading: str, body: str) -> None:
    if str(body or "").strip():
        _section(pdf, heading, body)


def _mind_map_visual(pdf: FPDF, tree: dict) -> None:
    try:
        node = advanced_outputs.validate_mind_map(tree)
    except Exception:
        return
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 9, _pdf_text("Mind Map"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    start_x = pdf.get_x()
    start_y = pdf.get_y()
    page_width = pdf.w - pdf.l_margin - pdf.r_margin
    center_x = start_x + page_width / 2
    box_w = min(80, page_width * 0.55)
    pdf.set_fill_color(232, 242, 239)
    pdf.set_draw_color(39, 106, 97)
    pdf.rect(center_x - box_w / 2, start_y, box_w, 14, style="DF")
    pdf.set_xy(center_x - box_w / 2 + 2, start_y + 3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.multi_cell(box_w - 4, 4, _pdf_text(node["label"]), align="C")
    y = start_y + 24
    branches = node.get("children", [])[:6]
    if not branches:
        pdf.ln(22)
        return
    col_w = page_width / 2 - 6
    for index, branch in enumerate(branches):
        col = index % 2
        row = index // 2
        x = start_x + col * (col_w + 12)
        item_y = y + row * 32
        if item_y > pdf.h - 35:
            pdf.add_page()
            item_y = pdf.get_y()
        pdf.set_xy(x, item_y)
        pdf.set_fill_color(249, 250, 247)
        pdf.set_draw_color(221, 227, 220)
        pdf.rect(x, item_y, col_w, 24, style="D")
        pdf.set_xy(x + 2, item_y + 2)
        pdf.set_font("Helvetica", "B", 9)
        pdf.multi_cell(col_w - 4, 4, _pdf_text(branch["label"]))
        child_labels = ", ".join(child["label"] for child in branch.get("children", [])[:3])
        if child_labels:
            pdf.set_x(x + 2)
            pdf.set_font("Helvetica", "", 8)
            pdf.multi_cell(col_w - 4, 4, _pdf_text(child_labels))
    pdf.set_y(y + ((len(branches) + 1) // 2) * 32 + 4)
    pdf.ln(4)


def _flashcards_text(cards: list[dict]) -> str:
    if not cards:
        return "None created yet."
    parts = []
    for index, card in enumerate(cards, start=1):
        parts.append(
            "\n".join(
                [
                    f"{index}. Front: {card.get('front', '')}",
                    f"Back: {card.get('back', '')}",
                    f"Topic: {card.get('topic', 'General')}",
                ]
            )
        )
    return "\n\n".join(parts)
