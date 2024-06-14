from fastapi import FastAPI, UploadFile, File, HTTPException, Request 
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask
import os, shutil, uuid, subprocess

###################
# CONFIG

HOSTED_URL = 'https://hls.nnisarg.in'
UPLOAD_FOLDER = 'videos'
OUTPUT_FOLDER = 'outputs'
ZIPS_FOLDER = 'zips'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov'}
RESOLUTIONS = {
    "360p": {"resolution": "640x360", "bitrate": "800k"},
    "480p": {"resolution": "854x480", "bitrate": "1200k"},
    "720p": {"resolution": "1280x720", "bitrate": "2500k"},
    "1080p": {"resolution": "1920x1080", "bitrate": "5000k"}
}

###################
# TEMPLATES

templates = Jinja2Templates(directory='templates')

###################
# INIT

app = FastAPI(
    title='HLS Stream Generator',
    description='Generate HLS streams from video files',
    version='1.0.0',
    docs_url='/docs',
    redoc_url='/redoc',
)

###################
# FUNCTIONS

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_hls(filepath: str) -> str:
    id = str(uuid.uuid4())

    if not os.path.exists(os.path.join(OUTPUT_FOLDER, id)):
        os.mkdir(os.path.join(OUTPUT_FOLDER, id))
        dir = os.path.join(OUTPUT_FOLDER, id)

        try:
            master_playlist_path = os.path.join(dir, "index.m3u8")
            with open(master_playlist_path, "w") as master_playlist:
                master_playlist.write("#EXTM3U\n")
                for resolution, settings in RESOLUTIONS.items():
                    output_path = os.path.join(dir, resolution)
                    os.mkdir(output_path)
                    cmd = (f'ffmpeg -i {filepath} -vf scale={settings["resolution"]} -c:v h264 -b:v {settings["bitrate"]} '
                           '-c:a aac -f hls -hls_time 10 -hls_playlist_type vod -hls_segment_filename '
                           f'{output_path}/%03d.ts {output_path}/index.m3u8')
                    subprocess.run(cmd, shell=True, check=True)
                    master_playlist.write(f"#EXT-X-STREAM-INF:BANDWIDTH={settings['bitrate']},RESOLUTION={settings['resolution']}\n")
                    master_playlist.write(f"{resolution}/index.m3u8\n")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return id

    else:
        return generate_hls(filepath)

def zip_folder(id: str):
    try:
        shutil.make_archive(os.path.join(ZIPS_FOLDER, id), 'zip', os.path.join(OUTPUT_FOLDER, id))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def cleanup(video: str, id: str):
    os.remove(os.path.join(UPLOAD_FOLDER, video))
    shutil.rmtree(os.path.join(OUTPUT_FOLDER, id))
    os.remove(os.path.join(ZIPS_FOLDER, f'{id}.zip'))

###################
# ROUTES

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})

@app.post("/upload")
def upload_file(video: UploadFile = File(...)):
    if not video or not video.filename or not allowed_file(video.filename):
        raise HTTPException(status_code=400, detail='File type not allowed or file extension is not supported. Supported formats: mp4, avi, mov')

    try:
        file_path = os.path.join(os.getcwd(), UPLOAD_FOLDER, video.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)

        folder_id = generate_hls(file_path)
        zip_folder(folder_id)

        return FileResponse(os.path.join(ZIPS_FOLDER, f'{folder_id}.zip'), background=BackgroundTask(cleanup, video.filename, folder_id), media_type='application/zip', filename=f'{video.filename.split(".")[0]}.zip')

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

###################
# SEO

@app.get("/sitemap.xml", response_class=PlainTextResponse)
def generate_sitemap():
    base_url = HOSTED_URL
    routes = app.routes
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for route in routes:
        if not route.path.startswith("/docs") and not route.path.startswith("/redoc"):
            sitemap += f'<url>\n<loc>{base_url}{route.path}</loc>\n</url>\n'
    sitemap += "</urlset>"
    return PlainTextResponse(content=sitemap)

@app.get("/robots.txt", response_class=PlainTextResponse)
def get_robots_txt():
    robots_txt = "User-agent: *\nDisallow: /docs\nDisallow: /redoc\n"
    return PlainTextResponse(content=robots_txt)

###################

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
