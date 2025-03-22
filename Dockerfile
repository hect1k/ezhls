FROM python:3.11-slim-bookworm

WORKDIR /app

# Install Rust and essential build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cargo \
    ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=5000

EXPOSE 5000

CMD ["sh", "-c", "fastapi run --host 0.0.0.0 --port ${PORT}"]
