import os
import uuid
from PIL import Image
import pillow_avif
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from engine import EmojiMosaicEngine

app = FastAPI(title="Emoji Mosaic Perfect Engine")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "..", "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "outputs")
DATA_DIR = os.path.join(BASE_DIR, "..", "data")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Initialize Engine
engine = EmojiMosaicEngine(os.path.join(DATA_DIR, "emojis.csv"))

# Serve outputs as static files
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")

# Task tracking
tasks = {}

EXPORT_FORMATS = {
    "png": "PNG",
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "webp": "WEBP",
    "bmp": "BMP",
    "tiff": "TIFF",
}


def build_export_path(task_id, export_format, quality_mode):
    safe_format = export_format.lower()
    safe_quality = quality_mode.lower()
    return os.path.join(OUTPUT_DIR, f"export_{task_id}_{safe_quality}.{safe_format}")


def create_export_file(source_path, export_path, export_format, quality_mode):
    with Image.open(source_path) as image:
        export_image = image.convert("RGB") if export_format.lower() in {"jpg", "jpeg", "bmp", "tiff"} else image.copy()

        if quality_mode == "low":
            new_width = max(1, export_image.width // 3)
            new_height = max(1, export_image.height // 3)
            export_image = export_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        save_kwargs = {}
        if export_format.lower() in {"jpg", "jpeg"}:
            save_kwargs = {"quality": 70, "optimize": True}
        elif export_format.lower() == "webp":
            save_kwargs = {"quality": 80, "method": 6}
        elif export_format.lower() == "png":
            save_kwargs = {"compress_level": 1 if quality_mode == "original" else 6}

        export_image.save(export_path, EXPORT_FORMATS[export_format.lower()], **save_kwargs)

def process_image(task_id, input_path, config):
    try:
        output_filename = f"perfect_{task_id}.png"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        engine.create_mosaic(input_path, output_path, config)
        tasks[task_id] = {"status": "completed", "output_url": f"/outputs/{output_filename}"}
    except Exception as e:
        print(f"Error processing {task_id}: {str(e)}")
        tasks[task_id] = {"status": f"error: {str(e)}"}

@app.post("/upload")
async def upload_image(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    quality: int = Form(3),
    emoji_size: int = Form(16)
):
    task_id = str(uuid.uuid4())
    file_ext = os.path.splitext(image.filename)[1]
    input_path = os.path.join(UPLOAD_DIR, f"{task_id}{file_ext}")
    
    with open(input_path, "wb") as f:
        f.write(await image.read())
    
    tasks[task_id] = {"status": "processing"}
    
    config = {
        "quality": quality,
        "emoji_size": emoji_size
    }
    
    background_tasks.add_task(process_image, task_id, input_path, config)
    
    return {"id": task_id, "status": "processing"}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    return tasks.get(task_id, {"status": "not_found"})


@app.get("/export/{task_id}")
async def export_image(
    task_id: str,
    format: str = Query("png"),
    quality_mode: str = Query("original"),
):
    task = tasks.get(task_id)
    if not task or task.get("status") != "completed":
        raise HTTPException(status_code=404, detail="Task not found or not completed")

    if format.lower() not in EXPORT_FORMATS:
        raise HTTPException(status_code=400, detail="Unsupported export format")

    if quality_mode.lower() not in {"low", "original"}:
        raise HTTPException(status_code=400, detail="Unsupported quality mode")

    source_path = os.path.join(OUTPUT_DIR, f"perfect_{task_id}.png")
    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="Source image not found")

    export_path = build_export_path(task_id, format, quality_mode)
    if not os.path.exists(export_path):
        create_export_file(source_path, export_path, format, quality_mode)

    return FileResponse(
        export_path,
        media_type=f"image/{'jpeg' if format.lower() in {'jpg', 'jpeg'} else format.lower()}",
        filename=os.path.basename(export_path),
    )

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        return {"message": "Emoji Mosaic Perfect Engine is running (Frontend not built yet)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5999)
