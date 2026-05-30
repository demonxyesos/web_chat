import os
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from asyncgram_common.app_factory import add_cors, add_health
from asyncgram_common.auth_deps import CurrentTokenUser

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(Path(__file__).resolve().parents[3] / "uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", str(10 * 1024 * 1024)))

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg",
    ".mp4", ".webm", ".mov", ".avi", ".mkv",
    ".mp3", ".ogg", ".wav", ".flac",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".csv", ".zip", ".rar", ".7z", ".tar", ".gz",
}

app = FastAPI(title="Asyncgram Media Service")
add_cors(app)
add_health(app)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.post("/upload")
async def upload_file(
    current_user: CurrentTokenUser,
    file: UploadFile = File(...),
):
    _ = current_user
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not allowed")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / unique_name
    dest.write_bytes(contents)

    return {
        "file_url": f"/uploads/{unique_name}",
        "file_name": file.filename,
        "file_type": file.content_type or "",
        "file_size": len(contents),
    }
