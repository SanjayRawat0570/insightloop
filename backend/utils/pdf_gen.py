from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML
import io
from typing import Dict, Any


def render_pdf(report_json: Dict[str, Any], chart_images: Dict[str, bytes] | None = None) -> bytes:
    env = Environment(loader=FileSystemLoader("./backend/templates"), autoescape=select_autoescape(["html"]))
    tpl = env.from_string("""
    <html><body>
    <h1>{{ report.title }}</h1>
    <p>{{ report.executive_summary }}</p>
    {% for s in report.sections %}
      <h2>{{ s.title }}</h2>
      <div>{{ s.narrative.headline }}</div>
    {% endfor %}
    </body></html>
    """)
    html = tpl.render(report=report_json)
    pdf = HTML(string=html).write_pdf()
    return pdf
