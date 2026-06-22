from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
SCREENSHOTS_DIR = OUTPUT_DIR / "screenshots"
DOWNLOADS_DIR = OUTPUT_DIR / "downloads"
REPORTS_DIR = OUTPUT_DIR / "reports"

def ensure_dirs():
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def save_report(content: str):
    ensure_dirs()
    report_file = REPORTS_DIR / f"relatorio_{timestamp()}.md"
    report_file.write_text(content, encoding="utf-8")
    return report_file
