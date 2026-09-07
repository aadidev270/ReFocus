# ReFocus

ReFocus is a local-first Windows focus recovery demo. It captures recent work context (only after you enable capture), extracts local OCR text, and asks a local Ollama model to help you resume after an interruption.

## Architecture

- `backend/`: FastAPI + SQLite API, local screenshot store, Ollama recovery briefs.
- `agent/`: Windows companion process for foreground-window context, screenshots, OCR, and category-aware idle detection.
- `frontend/`: React/Vite dashboard for resume briefs, timeline, goals, analytics, and local privacy settings.

## Run locally

Prerequisites: Python 3.11+, Node 20+, [Tesseract](https://github.com/tesseract-ocr/tesseract), and optionally [Ollama](https://ollama.com/) with `ollama pull llama3.2`.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Then run `pip install -r agent/requirements.txt` and `python agent/refocus_agent.py` from a third terminal. Open the dashboard, enable **Private capture**, and ReFocus will begin collecting local context every 20 seconds.

## Privacy

Capture is disabled by default. Screenshots, OCR text, activity history, goals, and summaries remain in `data/` on the local machine. The UI can remove individual captures; delete `data/` to remove all local demo data while the services are stopped.

## Limits of this demo

The native agent intentionally does not use a browser extension, so browser URLs and precise YouTube pause state are unavailable. Media uses its category idle threshold as a local fallback. Ollama failure does not stop capture: ReFocus displays a deterministic recovery note based on the latest OCR and window context.
