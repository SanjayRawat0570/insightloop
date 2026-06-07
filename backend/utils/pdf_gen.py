"""PDF report generator.

Uses fpdf2 (pure Python, no native dependencies) so it works reliably on
Windows/macOS/Linux without the GTK/Pango stack that WeasyPrint requires.

Input: a report_json dict shaped like the compiler agent's output:
    {
      "title": str,
      "generated_at": str,
      "executive_summary": str,
      "sections": [
        {"title", "chart_config", "narrative", "data_table", "sql_used"}
      ],
    }
Returns the PDF as bytes.
"""
from __future__ import annotations

from typing import Any, Dict, List

from fpdf import FPDF

BRAND = (37, 99, 235)  # blue-600
INK = (15, 23, 42)     # slate-900
MUTED = (100, 116, 139)  # slate-500


def _safe(text: Any) -> str:
    """fpdf core fonts are latin-1; replace unsupported characters."""
    s = "" if text is None else str(text)
    return s.encode("latin-1", "replace").decode("latin-1")


class _ReportPDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*MUTED)
        self.cell(0, 8, "InsightLoop Report", align="L")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def _heading(pdf: FPDF, text: str, size: int = 14):
    pdf.set_font("Helvetica", "B", size)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 8, _safe(text))
    pdf.ln(1)


def _paragraph(pdf: FPDF, text: str, size: int = 11, color=INK):
    pdf.set_font("Helvetica", "", size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, 6, _safe(text))
    pdf.ln(1)


def _data_table(pdf: FPDF, rows: List[Dict[str, Any]], max_rows: int = 20):
    if not rows:
        _paragraph(pdf, "No data.", color=MUTED)
        return
    columns = list(rows[0].keys())
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    col_w = usable / max(len(columns), 1)

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(241, 245, 249)  # slate-100
    pdf.set_text_color(*INK)
    for col in columns:
        pdf.cell(col_w, 8, _safe(col)[:24], border=0, fill=True, align="L")
    pdf.ln(8)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    for row in rows[:max_rows]:
        for col in columns:
            val = row.get(col, "")
            if isinstance(val, float):
                val = f"{val:,.2f}"
            pdf.cell(col_w, 7, _safe(val)[:24], border="B", align="L")
        pdf.ln(7)
    if len(rows) > max_rows:
        pdf.ln(1)
        _paragraph(pdf, f"... and {len(rows) - max_rows} more rows", size=8, color=MUTED)


def render_pdf(report_json: Dict[str, Any], chart_images: Dict[str, bytes] | None = None) -> bytes:
    report = report_json or {}
    pdf = _ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Cover / title block
    pdf.ln(20)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(*BRAND)
    pdf.multi_cell(0, 12, _safe(report.get("title") or "InsightLoop Report"))
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, _safe(f"Generated {report.get('generated_at', '')}"))
    pdf.ln(14)

    # Executive summary
    if report.get("executive_summary"):
        _heading(pdf, "Executive Summary", size=15)
        _paragraph(pdf, report["executive_summary"])
        pdf.ln(4)

    # Sections
    sections = report.get("sections") or []
    if not sections:
        _paragraph(pdf, "This report has no sections yet. Run a query to populate it.", color=MUTED)

    for i, section in enumerate(sections):
        if i > 0:
            pdf.ln(4)
        _heading(pdf, section.get("title") or f"Section {i + 1}", size=14)

        narrative = section.get("narrative") or {}
        if narrative.get("headline"):
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(*INK)
            pdf.multi_cell(0, 7, _safe(narrative["headline"]))
            pdf.ln(1)
        for line in narrative.get("supporting") or []:
            _paragraph(pdf, f"- {line}", size=10, color=MUTED)
        if narrative.get("recommendation"):
            _paragraph(pdf, f"Recommendation: {narrative['recommendation']}", size=10)

        chart = section.get("chart_config") or {}
        if chart.get("chart_type"):
            _paragraph(
                pdf,
                f"Visualization: {chart.get('chart_type')} chart "
                f"(x: {chart.get('x_axis', '-')}, y: {chart.get('y_axis', '-')})",
                size=9,
                color=MUTED,
            )

        pdf.ln(2)
        _data_table(pdf, section.get("data_table") or [])

        if section.get("sql_used"):
            pdf.ln(2)
            pdf.set_font("Courier", "", 8)
            pdf.set_text_color(*MUTED)
            pdf.multi_cell(0, 5, _safe("SQL: " + section["sql_used"]))

    out = pdf.output()
    return bytes(out)
