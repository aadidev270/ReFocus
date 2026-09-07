import base64
import io
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .config import CAPTURE_DIR
from .database import initialize, connection
from .services import now, category_for, settings, save_settings, analyze, latest_brief

app = FastAPI(title="ReFocus Local API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
app.mount("/captures", StaticFiles(directory=CAPTURE_DIR), name="captures")
@app.on_event("startup")
def startup(): initialize()
class CaptureIn(BaseModel):
    app_name: str = "Unknown"; window_title: str = ""; image_base64: Optional[str] = None; ocr_text: str = ""; category: Optional[str] = None
class SettingsIn(BaseModel):
    privacy_enabled: Optional[bool] = None; capture_interval: Optional[int] = Field(default=None, ge=10, le=300); ollama_model: Optional[str] = None; tesseract_path: Optional[str] = None
class GoalIn(BaseModel): title: str = Field(min_length=1, max_length=240); goal_date: Optional[str] = None
class InterruptionIn(BaseModel): category: str; started_at: Optional[str] = None; ended_at: Optional[str] = None; resumed: bool = False
@app.get("/api/health")
def health(): return {"ok": True, "ollama": analyze("health check", "ReFocus", "Health")[2] == "ready"}
@app.get("/api/settings")
def get_settings(): return settings()
@app.put("/api/settings")
def update_settings(body: SettingsIn): return save_settings({k:v for k,v in body.model_dump().items() if v is not None})
@app.post("/api/captures")
def ingest_capture(body: CaptureIn):
    if settings().get("privacy_enabled") != "true": raise HTTPException(403, "Capture is disabled by privacy settings")
    category = body.category or category_for(body.app_name, body.window_title); created = now(); image_path = None
    if body.image_base64:
        try:
            raw = base64.b64decode(body.image_base64); name = f"capture-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.png"; path = CAPTURE_DIR / name; path.write_bytes(raw); image_path = f"/captures/{name}"
        except ValueError: raise HTTPException(422, "Invalid image data")
    ocr_text = body.ocr_text
    if not ocr_text and body.image_base64:
        try:
            import pytesseract
            from PIL import Image
            configured = settings().get("tesseract_path")
            if configured: pytesseract.pytesseract.tesseract_cmd = configured
            ocr_text = pytesseract.image_to_string(Image.open(io.BytesIO(base64.b64decode(body.image_base64))))
        except Exception: pass
    summary, next_action, status = analyze(ocr_text, body.app_name, body.window_title)
    with connection() as conn:
        cursor = conn.execute("INSERT INTO captures(created_at,app_name,window_title,category,image_path,ocr_text,ai_status,task_summary,next_action) VALUES(?,?,?,?,?,?,?,?,?)", (created,body.app_name,body.window_title,category,image_path,ocr_text,status,summary,next_action))
    return {"id": cursor.lastrowid, "category": category, "ai_status": status}
@app.get("/api/captures")
def captures(limit: int = 24):
    with connection() as conn: return [dict(r) for r in conn.execute("SELECT * FROM captures ORDER BY id DESC LIMIT ?", (min(limit,100),))]
@app.delete("/api/captures/{capture_id}")
def delete_capture(capture_id: int):
    with connection() as conn:
        row=conn.execute("SELECT image_path FROM captures WHERE id=?",(capture_id,)).fetchone(); conn.execute("DELETE FROM captures WHERE id=?",(capture_id,))
    if not row: raise HTTPException(404, "Capture not found")
    if row["image_path"]:
        (CAPTURE_DIR / Path(row["image_path"]).name).unlink(missing_ok=True)
    return {"deleted": capture_id}
@app.get("/api/resume-brief")
def resume_brief(): return latest_brief()
@app.post("/api/interruptions")
def record_interruption(body: InterruptionIn):
    started = body.started_at or now(); ended = body.ended_at
    duration = 0
    if ended:
        duration = max(0, int((datetime.fromisoformat(ended.replace("Z", "+00:00")) - datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds()))
    with connection() as conn:
        cursor = conn.execute("INSERT INTO interruptions(started_at,ended_at,category,duration_seconds,resumed) VALUES(?,?,?,?,?)", (started, ended, body.category, duration, int(body.resumed)))
    return {"id": cursor.lastrowid, "duration_seconds": duration}
@app.get("/api/goals")
def goals(goal_date: Optional[str] = None):
    target = goal_date or date.today().isoformat()
    with connection() as conn: return [dict(r) for r in conn.execute("SELECT * FROM goals WHERE goal_date=? ORDER BY completed,id",(target,))]
@app.post("/api/goals")
def add_goal(body: GoalIn):
    target=body.goal_date or date.today().isoformat()
    with connection() as conn: cursor=conn.execute("INSERT INTO goals(title,goal_date) VALUES (?,?)",(body.title,target))
    return {"id":cursor.lastrowid,"title":body.title,"goal_date":target,"completed":0}
@app.patch("/api/goals/{goal_id}/complete")
def toggle_goal(goal_id:int):
    with connection() as conn: conn.execute("UPDATE goals SET completed=1-completed WHERE id=?",(goal_id,)); row=conn.execute("SELECT * FROM goals WHERE id=?",(goal_id,)).fetchone()
    if not row: raise HTTPException(404,"Goal not found")
    return dict(row)
@app.get("/api/analytics/daily")
def daily():
    today=date.today().isoformat()
    with connection() as conn:
        captures=conn.execute("SELECT count(*) c FROM captures WHERE substr(created_at,1,10)=?",(today,)).fetchone()["c"]; goals_done=conn.execute("SELECT count(*) c FROM goals WHERE goal_date=? AND completed=1",(today,)).fetchone()["c"]; goals_total=conn.execute("SELECT count(*) c FROM goals WHERE goal_date=?",(today,)).fetchone()["c"]
        interruptions=conn.execute("SELECT count(*) c,coalesce(sum(duration_seconds),0) seconds FROM interruptions WHERE substr(started_at,1,10)=?",(today,)).fetchone()
        previous=conn.execute("SELECT coalesce(sum(duration_seconds),0) seconds FROM interruptions WHERE substr(started_at,1,10)=date(?, '-1 day')",(today,)).fetchone()["seconds"]
    return {"date":today,"captures":captures,"interruptions":interruptions["c"],"away_minutes":round(interruptions["seconds"]/60),"goals_completed":goals_done,"goals_total":goals_total,"change_from_previous_day":round((interruptions["seconds"]-previous)/60)}
