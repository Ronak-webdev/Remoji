FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 \
    wget unzip curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download OpenMoji PNGs at build time (618px color set)
RUN mkdir -p /app/emoji_pngs && \
    wget -q https://github.com/hfg-gmuend/openmoji/releases/download/15.0.0/openmoji-618x618-color.zip \
    -O /tmp/openmoji.zip && \
    unzip -q /tmp/openmoji.zip -d /app/emoji_pngs && \
    rm /tmp/openmoji.zip

COPY backend/ ./backend/
COPY data/ ./data/

# Serve React frontend as static files from FastAPI
COPY frontend/dist/ ./static/

RUN mkdir -p /app/uploads /app/outputs

EXPOSE 7860

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
