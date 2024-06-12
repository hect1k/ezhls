from fastapi import FastAPI, UploadFile, File, HTTPException, Request 
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask
import os, shutil, uuid

###################
# CONFIG

UPLOAD_FOLDER = 'videos'
OUTPUT_FOLDER = 'outputs'
ZIPS_FOLDER = 'zips'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov'}

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
            os.system(f'ffmpeg -i {filepath} -c:v copy -c:a copy -bsf:v h264_mp4toannexb -f hls {dir}/index.m3u8')
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
async def index(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})

@app.post("/upload/")
async def upload_file(video: UploadFile = File(...)):
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

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
