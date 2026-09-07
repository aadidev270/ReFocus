"""Windows companion agent. Run while the FastAPI backend is running."""
import base64, io, time, ctypes
import requests
from PIL import Image
API = "http://127.0.0.1:8000/api"
INTERVAL = 20
THRESHOLDS = {"coding":300, "meeting":300, "browsing":420, "media":300, "other":300}
def foreground_window():
    try:
        import win32gui, win32process, psutil
        hwnd=win32gui.GetForegroundWindow(); title=win32gui.GetWindowText(hwnd); _,pid=win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).name(), title
    except Exception: return "Unknown", ""
def screenshot_b64():
    import mss
    with mss.mss() as sct:
        shot=sct.grab(sct.monitors[1]); image=Image.frombytes("RGB",shot.size,shot.rgb); out=io.BytesIO(); image.save(out,"PNG"); return base64.b64encode(out.getvalue()).decode()
def ocr(image_b64):
    try:
        import pytesseract
        return pytesseract.image_to_string(Image.open(io.BytesIO(base64.b64decode(image_b64))))
    except Exception: return ""
def idle_seconds():
    """Windows last-input duration. Returns 0 on unsupported systems."""
    try:
        class LASTINPUTINFO(ctypes.Structure): _fields_=[('cbSize',ctypes.c_uint),('dwTime',ctypes.c_uint)]
        info=LASTINPUTINFO(); info.cbSize=ctypes.sizeof(info); ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
        return (ctypes.windll.kernel32.GetTickCount()-info.dwTime)/1000
    except Exception: return 0
def run():
    away_started = None
    while True:
        try:
            cfg=requests.get(f"{API}/settings",timeout=3).json()
            if cfg.get("privacy_enabled") == "true":
                app,title=foreground_window(); image=screenshot_b64(); payload={"app_name":app,"window_title":title,"image_base64":image,"ocr_text":ocr(image)}
                response=requests.post(f"{API}/captures",json=payload,timeout=30); category=response.json().get("category","other")
                idle=idle_seconds(); threshold=THRESHOLDS.get(category,300)
                # Media pause-state is platform-specific; without a browser extension, only OS inactivity is used.
                if idle >= threshold and away_started is None: away_started=time.time()
                if away_started and idle < 3:
                    requests.post(f"{API}/interruptions",json={"category":category,"started_at":time.strftime('%Y-%m-%dT%H:%M:%S+00:00',time.gmtime(away_started)),"ended_at":time.strftime('%Y-%m-%dT%H:%M:%S+00:00',time.gmtime()),"resumed":True},timeout=5); away_started=None
            time.sleep(int(cfg.get("capture_interval",INTERVAL)))
        except requests.RequestException: time.sleep(5)
if __name__ == "__main__": run()
