import os
import shutil
import subprocess
import uuid
import zipfile

import aiofiles
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.routing import APIRoute
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask

###################
# CONFIG

HOSTED_URL = "https://hls.nnisarg.in"

UPLOAD_FOLDER = "videos"
OUTPUT_FOLDER = "outputs"
ZIPS_FOLDER = "zips"

ALLOWED_EXTENSIONS = {"mp4", "avi", "mov"}

RESOLUTIONS = {
    "360p": {"resolution": "640x360", "bitrate": "800k"},
    "480p": {"resolution": "854x480", "bitrate": "1200k"},
    "720p": {"resolution": "1280x720", "bitrate": "2500k"},  # Default
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
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

###################
# FUNCTIONS

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

async def save_uploaded_file(file: UploadFile, destination: str):
    async with aiofiles.open(destination, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            await buffer.write(chunk)

def generate_hls(filepath: str, resolution: str) -> str:
    if resolution not in RESOLUTIONS:
        raise HTTPException(status_code=400, detail="Invalid resolution selected.")

    id = str(uuid.uuid4())
    output_path = os.path.join(OUTPUT_FOLDER, id)

    if os.path.exists(output_path):
        raise HTTPException(status_code=500, detail="Output folder collision, try again.")

    os.mkdir(output_path)

    settings = RESOLUTIONS[resolution]
    output_folder = os.path.join(output_path, resolution)
    os.mkdir(output_folder)

    try:
        cmd = [
            "ffmpeg", "-i", filepath,
            "-vf", f"scale={settings['resolution']}",
            "-c:v", "h264", "-b:v", settings["bitrate"],
            "-c:a", "aac", "-f", "hls",
            "-hls_time", "10", "-hls_playlist_type", "vod",
            "-hls_segment_filename", os.path.join(output_folder, "%03d.ts"),
            os.path.join(output_folder, "index.m3u8")
        ]
        subprocess.run(cmd, check=True)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"FFmpeg error: {str(e)}")

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
    try:
        video_path = os.path.join(UPLOAD_FOLDER, video)
        output_path = os.path.join(OUTPUT_FOLDER, id)
        zip_path = os.path.join(ZIPS_FOLDER, f"{id}.zip")

        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(output_path):
            shutil.rmtree(output_path)
        if os.path.exists(zip_path):
            os.remove(zip_path)

    except Exception as e:
        print(f"Cleanup failed: {e}")

###################
# ROUTES

@app.get("/", include_in_schema=False, response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_file(
    video: UploadFile = File(...),
    resolution: str = Query("720p", enum=RESOLUTIONS.keys())
):
    if not video or not video.filename or not allowed_file(video.filename):
        raise HTTPException(status_code=400, detail="Unsupported file format")

    unique_filename = f"{uuid.uuid4()}.{video.filename.rsplit('.', 1)[1]}"
    file_path = os.path.join(UPLOAD_FOLDER, unique_filename)

    await save_uploaded_file(video, file_path)

    folder_id = generate_hls(file_path, resolution)
    zip_folder(folder_id)

    return FileResponse(
        os.path.join(ZIPS_FOLDER, f"{folder_id}.zip"),
        background=BackgroundTask(cleanup, unique_filename, folder_id),
        media_type="application/zip",
        filename=f"{video.filename.rsplit('.', 1)[0]}.zip"
    )

###################
# SEO

@app.get("/sitemap.xml", include_in_schema=False, response_class=PlainTextResponse)
def generate_sitemap():
    base_url = HOSTED_URL
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for route in routes:
        if not route.path.startswith("/docs") and not route.path.startswith("/redoc"):
            sitemap += f"<url>\n<loc>{base_url}{route.path}</loc>\n</url>\n"
    sitemap += "</urlset>"
    return PlainTextResponse(content=sitemap)

@app.get("/robots.txt", include_in_schema=False, response_class=PlainTextResponse)
def get_robots_txt():
    robots_txt = "User-agent: *\nDisallow: /docs\nDisallow: /redoc\n"
    return PlainTextResponse(content=robots_txt)

###################
# RUN SETUP

if __name__ == "__main__":
    for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER, ZIPS_FOLDER]:
        if not os.path.exists(folder):
            os.makedirs(folder)
