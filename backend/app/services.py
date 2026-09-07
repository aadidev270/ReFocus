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

def ollama_health():
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=3)
        response.raise_for_status()
        model = settings().get("ollama_model", "llama3.2")
        names = [item.get("name", "") for item in response.json().get("models", [])]
        return {"available": True, "model_available": any(name == model or name.startswith(f"{model}:") for name in names), "model": model}
    except Exception as error:
        return {"available": False, "model_available": False, "model": settings().get("ollama_model", "llama3.2"), "error": str(error)}

def analyze(text, app_name, title):
    if not text.strip(): return ("No readable text was found in the last capture.", f"Return to {title or app_name} and review the most recent screen.", "fallback")
    model = settings().get("ollama_model", "llama3.2")
    prompt = f"""Return valid JSON only with keys summary, where_working, and next_action.
Infer exactly what the person was doing from this local work capture.
Application: {app_name}
Window title: {title}
OCR text: {text[:5000]!r}
summary should state the task and its latest visible state. where_working should name the application and relevant file, website, document, or page visible in the evidence. next_action should be one concrete next step. Do not invent details."""
    try:
        response = httpx.post("http://localhost:11434/api/generate", json={"model": model, "prompt": prompt, "stream": False, "format": "json"}, timeout=15)
        response.raise_for_status(); payload = json.loads(response.json()["response"])
        where = str(payload.get("where_working") or title or app_name).strip()
        summary = str(payload.get("summary") or "Work context captured.").strip()
        summary = f"{summary}\n\nWhere you were working: {where}"
        next_action = str(payload.get("next_action") or "Review the latest capture and continue the task.").strip()
        return (summary, next_action, "ready")
    except Exception:
        excerpt = re.sub(r"\s+", " ", text).strip()[:180]
        return (f"You were working in {title or app_name}. Recent text: {excerpt}", "Review the latest capture and continue from the last visible step.", "unavailable")

def latest_brief():
    with connection() as conn:
        row = conn.execute("SELECT * FROM captures ORDER BY id DESC LIMIT 1").fetchone()
    if not row: return {"available": False, "message": "No captured work context yet."}
    return {"available": True, "capture": dict(row), "summary": row["task_summary"], "next_action": row["next_action"], "ai_status": row["ai_status"]}

def analyze_latest_capture():
    with connection() as conn:
        row = conn.execute("SELECT * FROM captures ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return None
        summary, next_action, status = analyze(row["ocr_text"], row["app_name"], row["window_title"])
        conn.execute("UPDATE captures SET task_summary=?, next_action=?, ai_status=? WHERE id=?", (summary, next_action, status, row["id"]))
    return latest_brief()
