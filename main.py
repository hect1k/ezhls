import asyncio
from email.message import EmailMessage
import os
import shutil
import smtplib
import subprocess
import threading
import time
import uuid
import zipfile

import aiofiles
from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

###################
# CONFIG

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")

ZIP_EXPIRY = int(os.getenv("ZIP_EXPIRY", 86400))  # Default: 1 day

HOSTED_URL = os.getenv("HOSTED_URL", "https://hls.nnisarg.in")

UPLOAD_FOLDER = "videos"
OUTPUT_FOLDER = "outputs"
ZIPS_FOLDER = "zips"


ALLOWED_EXTENSIONS = {"mp4", "avi", "mov"}

RESOLUTIONS = {
    "360p": {"resolution": "640x360", "bitrate": "800k"},
    "480p": {"resolution": "854x480", "bitrate": "1200k"},
    "720p": {"resolution": "1280x720", "bitrate": "2500k"},
    "1080p": {"resolution": "1920x1080", "bitrate": "5000k"}
}

###################
# TEMPLATES

templates = Jinja2Templates(directory="templates")

###################
# INIT

app = FastAPI(
    title="HLS Stream Generator",
    description="Generate HLS streams from video files",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

###################
# FUNCTIONS

async def send_email(recipient: str, subject: str, body: str):
    if not SMTP_HOST or not SMTP_PORT or not SMTP_USERNAME or not SMTP_PASSWORD:
        print("SMTP credentials not set")
        return

    msg = EmailMessage()
    msg["From"] = SENDER_EMAIL
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body, subtype="html")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Email failed: {e}")

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

async def save_uploaded_file(file: UploadFile, destination: str):
    async with aiofiles.open(destination, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            await buffer.write(chunk)

def generate_hls(filepath: str) -> str:
    while True:
        id = str(uuid.uuid4())
        dir = os.path.join(OUTPUT_FOLDER, id)

        if not os.path.exists(dir):
            os.makedirs(dir, exist_ok=True)
            break

    try:
        master_playlist_path = os.path.join(dir, "index.m3u8")

        with open(master_playlist_path, "w") as master_playlist:
            master_playlist.write("#EXTM3U\n")

            for resolution, settings in RESOLUTIONS.items():
                output_path = os.path.join(dir, resolution)
                os.makedirs(output_path, exist_ok=True)

                cmd = [
                    "ffmpeg", "-i", filepath, 
                    "-vf", f"scale={settings['resolution']}",
                    "-c:v", "h264", "-b:v", settings["bitrate"],
                    "-c:a", "aac", "-f", "hls",
                    "-hls_time", "10", "-hls_playlist_type", "vod",
                    "-hls_segment_filename", os.path.join(output_path, "%03d.ts"),
                    os.path.join(output_path, "index.m3u8")
                ]

                subprocess.run(cmd, check=True)
                master_playlist.write(f"#EXT-X-STREAM-INF:BANDWIDTH={settings['bitrate']},RESOLUTION={settings['resolution']}\n")
                master_playlist.write(f"{resolution}/index.m3u8\n")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return id

def zip_folder(id: str):
    try:
        zip_path = os.path.join(ZIPS_FOLDER, f"{id}.zip")
        folder_path = os.path.join(OUTPUT_FOLDER, id)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(folder_path):
                for file in files:
                    abs_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_path, folder_path)
                    zipf.write(abs_path, rel_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def cleanup(video: str, id: str):
    os.remove(os.path.join(UPLOAD_FOLDER, video))
    shutil.rmtree(os.path.join(OUTPUT_FOLDER, id))

def process_video(video_path: str, email: str, unique_filename: str):
    folder_id = ""
    error = ""

    try:
        folder_id = generate_hls(video_path)
        zip_folder(folder_id)
    except Exception as e:
        error = f"Video processing failed: {str(e)}"
        print(f"[ERROR] - {error}")

    download_link = f"{HOSTED_URL}/download/{folder_id}"

    if error:
        email_body = f"""
        <html>
            <body>
                <p>Processing failed due to an error :/</p>
                <p>Please try again or <a href="https://github.com/hect1k/ezhls/issues" target="_blank" rel="noopener noreferrer">open an issue</a>.</p>
            </body>
        </html>
        """
        asyncio.run(send_email(email, "HLS Processing Failed - EzHLS", email_body))
        print(f"[EMAIL] - Sent error email to {email}")
    else:
        email_body = f"""
        <html>
            <body>
                <p>Your video has been successfully processed.</p>
                <p><a href="{download_link}">Download ZIP</a></p>
                <p>This link will expire in {round(ZIP_EXPIRY // 3600, 2)} hours.</p>
            </body>
        </html>
        """
        asyncio.run(send_email(email, "Your HLS Video Stream is Ready - EzHLS", email_body))
        print(f"[EMAIL] - Sent success email to {email}")

    cleanup(unique_filename, folder_id)

###################
# ROUTES

@app.get("/", include_in_schema=False, response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_file(
    video: UploadFile = File(...),
    email: str = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    if not video or not video.filename or not allowed_file(video.filename):
        raise HTTPException(status_code=400, detail="Unsupported file format")

    unique_filename = f"{uuid.uuid4()}.{video.filename.rsplit('.', 1)[1]}"
    file_path = os.path.join(UPLOAD_FOLDER, unique_filename)

    await save_uploaded_file(video, file_path)

    background_tasks.add_task(process_video, file_path, email, unique_filename)

    return {"message": "Processing started. You'll receive an email when done."}

@app.get("/download/{zip_id}")
async def download_zip(zip_id: str):
    zip_path = os.path.join(ZIPS_FOLDER, f"{zip_id}.zip")
    if os.path.exists(zip_path):
        return FileResponse(zip_path, filename=f"{zip_id}.zip", media_type="application/zip")
    raise HTTPException(status_code=404, detail="File not found or expired")

def scheduled_cleanup():
    while True:
        try:
            time.sleep(3600)
            now = time.time()
            for file in os.listdir(ZIPS_FOLDER):
                file_path = os.path.join(ZIPS_FOLDER, file)
                if os.path.isfile(file_path) and (now - os.path.getmtime(file_path)) > ZIP_EXPIRY:
                    os.remove(file_path)
        except Exception as e:
            print(f"Cleanup failed: {e}")

threading.Thread(target=scheduled_cleanup, daemon=True).start()
