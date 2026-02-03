from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
import uuid
import shutil
import json
from datetime import datetime

app = FastAPI()

BASE = Path("jobs")
BASE.mkdir(exist_ok=True)

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <h1>Addition Demo</h1>

    <h2>Addition Demo</h2>
    <form action="/add" method="post">
        <input type="number" name="a" step="any" required>
        +
        <input type="number" name="b" step="any" required>
        <button type="submit">Add</button>
    </form>

    <hr>

    <h2>Video Upload</h2>
    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file" required>
        <button type="submit">Upload Video</button>
    </form>

    <p style="margin-top:20px;">
      Dev tools: <a href="/docs">/docs</a>
    </p>
    """

@app.post("/add", response_class=HTMLResponse)
def add(a: float = Form(...), b: float = Form(...)):
    result = a + b
    return f"""
    <h1>Addition Result</h1>
    <p>{a} + {b} = <strong>{result}</strong></p>
    <a href="/">Back to home</a>
    """

@app.post("/upload", response_class=HTMLResponse)
async def upload(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".mp4", ".mov", ".m4v", ".avi")):
        raise HTTPException(status_code=400, detail="Upload a video file (.mp4/.mov/.m4v/.avi)")

    job_id = str(uuid.uuid4())
    job_dir = BASE / job_id
    input_dir = job_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    save_path = input_dir / file.filename
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    meta = {
        "job_id": job_id,
        "filename": file.filename,
        "status": "uploaded",
        "created_at": now_iso(),
        "input_path": str(save_path),
    }
    (job_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    # Simple HTML "success" page
    return f"""
    <h1>Upload Successful ✅</h1>
    <p><strong>Filename:</strong> {file.filename}</p>
    <p><strong>Job ID:</strong> {job_id}</p>

    <ul>
      <li><a href="/status-page/{job_id}">View status (human-friendly)</a></li>
      <li><a href="/status/{job_id}">View status (raw JSON)</a></li>
      <li><a href="/download/{job_id}">Download uploaded file</a></li>
    </ul>

    <a href="/">Back to home</a>
    """

@app.get("/status/{job_id}")
def status(job_id: str):
    meta_path = BASE / job_id / "meta.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return json.loads(meta_path.read_text())

@app.get("/status-page/{job_id}", response_class=HTMLResponse)
def status_page(job_id: str):
    meta_path = BASE / job_id / "meta.json"
    if not meta_path.exists():
        return "<h1>Not found</h1><p>Unknown job_id</p><a href='/'>Back</a>"
    meta = json.loads(meta_path.read_text())
    return f"""
    <h1>Job Status</h1>
    <p><strong>Job ID:</strong> {meta["job_id"]}</p>
    <p><strong>Filename:</strong> {meta["filename"]}</p>
    <p><strong>Status:</strong> {meta["status"]}</p>
    <p><strong>Created:</strong> {meta["created_at"]}</p>

    <p><a href="/download/{job_id}">Download uploaded file</a></p>
    <p><a href="/">Back to home</a></p>
    """

@app.get("/download/{job_id}")
def download(job_id: str):
    meta_path = BASE / job_id / "meta.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Unknown job_id")
    meta = json.loads(meta_path.read_text())
    input_path = Path(meta["input_path"])
    if not input_path.exists():
        raise HTTPException(status_code=404, detail="Input file missing")
    return FileResponse(str(input_path), filename=input_path.name)
