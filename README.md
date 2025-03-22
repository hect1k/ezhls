# 🎥 EzHLS - HLS Stream Generator

EzHLS is a FastAPI-based web application that converts video files into **HLS (HTTP Live Streaming) format**. It allows users to upload a video, select a resolution, and generate an HLS stream along with a downloadable ZIP file.

## Features

- **Supports multiple video formats**: `.mp4`, `.avi`, `.mov`
- **Generates HLS streams** in **360p, 480p, 720p, and 1080p**
- **ZIP packaging** for easy downloads
- **FastAPI-powered API** with interactive Swagger docs (`/docs`)
- **Frontend with TailwindCSS** for a simple and clean UI
- **Automatic cleanup** of processed files

## Installation

### **1️⃣ Clone the Repository**
```sh
git clone https://github.com/hect1k/ezhls
cd ezhls
```

### **2️⃣ Install Dependencies**
#### Using Python (without Docker)
```sh
pip install -r requirements.txt
```

#### Using Docker (recommended)
Make sure you have **Docker** and **Docker Compose** installed.
```sh
docker-compose up --build -d
```

## Usage

### **Web Interface**
Visit: [http://localhost:8000](http://localhost:8000)  
Upload a video, select a resolution, and download the generated HLS stream.

### **API Endpoints**
#### **1️⃣ Upload a Video & Generate HLS**
**`POST /upload`**  
Upload a video file and get a downloadable ZIP of the HLS stream.

**Example using `curl`:**
```sh
curl -X 'POST' \
  'http://localhost:8000/upload?resolution=720p' \
  -F 'video=@/path/to/video.mp4' \
  -o output.zip
```

#### **2️⃣ API Documentation**
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

#### **3️⃣ SEO Features**
- **Sitemap:** `/sitemap.xml`
- **Robots.txt:** `/robots.txt`

## Project Structure

```
ezhls/
│── templates/        # HTML templates (index.html)
│── videos/           # Uploaded video files (auto-cleaned)
│── outputs/          # Generated HLS files (auto-cleaned)
│── zips/             # ZIP archives of HLS streams (auto-cleaned)
│── Dockerfile        # Docker configuration
│── docker-compose.yml
│── main.py           # FastAPI application
│── requirements.txt  # Python dependencies
│── README.md         # This file
│── LICENSE.md        # License file
```

## License

This project is licensed under the GNU General Public License v3 - see the [LICENSE](LICENSE.md) file for details.

## Todo

- [X] Add multi-resolution support  
- [X] Create a simple UI  
- [ ] Add multi-bitrate adaptive streaming  
- [ ] Enable cloud storage integration  
