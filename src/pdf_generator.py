import os
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def generate_pdf(json_data: dict, output_path: str) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=True)
    html = env.get_template("report.html").render(
        data=json_data,
        created_at=datetime.now().strftime("%d.%m.%Y %H:%M Uhr"),
    )
    HTML(string=html).write_pdf(output_path)
    return output_path
