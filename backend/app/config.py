from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "refocus.db"
CAPTURE_DIR = DATA_DIR / "captures"
CAPTURE_DIR.mkdir(exist_ok=True)
