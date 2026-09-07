import json
import re
from datetime import datetime, timezone
from pathlib import Path
import httpx
from .config import CAPTURE_DIR
from .database import connection

def now(): return datetime.now(timezone.utc).isoformat()

def category_for(app_name: str, title: str) -> str:
    text = f"{app_name} {title}".lower()
    if any(x in text for x in ("code", "visual studio", "pycharm", "intellij", "terminal", "powershell", "cmd.exe")): return "coding"
    if any(x in text for x in ("teams", "zoom", "meet", "slack huddle")): return "meeting"
    if any(x in text for x in ("youtube", "netflix", "vlc", "spotify", "media player")): return "media"
    if any(x in text for x in ("chrome", "edge", "firefox", "reader", "acrobat")): return "browsing"
    return "other"

def settings():
    with connection() as conn:
        return {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM settings")}

def save_settings(values):
    with connection() as conn:
        for key, value in values.items(): conn.execute("INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value).lower() if isinstance(value, bool) else str(value)))
    return settings()

def analyze(text, app_name, title):
    if not text.strip(): return ("No readable text was found in the last capture.", f"Return to {title or app_name} and review the most recent screen.", "fallback")
    model = settings().get("ollama_model", "llama3.2")
    prompt = f"Return JSON only with keys summary and next_action. Infer the user's work from app={app_name}, title={title}, OCR={text[:3000]!r}. Be concise."
    try:
        response = httpx.post("http://localhost:11434/api/generate", json={"model": model, "prompt": prompt, "stream": False, "format": "json"}, timeout=15)
        response.raise_for_status(); payload = json.loads(response.json()["response"])
        return (payload.get("summary", "Work context captured."), payload.get("next_action", "Resume the last task."), "ready")
    except Exception:
        excerpt = re.sub(r"\s+", " ", text).strip()[:180]
        return (f"You were working in {title or app_name}. Recent text: {excerpt}", "Review the latest capture and continue from the last visible step.", "unavailable")

def latest_brief():
    with connection() as conn:
        row = conn.execute("SELECT * FROM captures ORDER BY id DESC LIMIT 1").fetchone()
    if not row: return {"available": False, "message": "No captured work context yet."}
    return {"available": True, "capture": dict(row), "summary": row["task_summary"], "next_action": row["next_action"], "ai_status": row["ai_status"]}
