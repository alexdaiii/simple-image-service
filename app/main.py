import base64
import io
import logging
import os
from contextlib import asynccontextmanager

from PIL import Image
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

from app.database import (
    open_database_conn_pool,
    close_database_conn_pool,
    get_session,
    init_db,
)
from app.logging import configure_logging
from app.schema import ImagePost, ImagePostReturn
from app.security import verify_token
from app.utils import get_settings, upload_file_bytes, get_file_bytes

# --- ENVIRONMENT VARIABLES ---
if os.environ.get("ENV") == "development":
    print("Loading environment variables from .env file")
    load_dotenv()


# --- DB SETUP ---
@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_settings()  # Ensure settings are loaded
    configure_logging(get_settings().log_level)
    await open_database_conn_pool()
    await init_db()
    yield
    await close_database_conn_pool()


SUPPORTED_IMAGE_FORMATS = {"avif", "png", "webp", "jpeg", "jpg"}

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins_list,
    allow_origin_regex=get_settings().allowed_origins_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


log = logging.getLogger(__name__)


@app.post("/images", dependencies=[Depends(verify_token)])
async def upload_image(data: ImagePost, session: AsyncSession = Depends(get_session)) -> ImagePostReturn:
    # Decode base64
    try:
        img_bytes = base64.b64decode(data.image)
        with Image.open(io.BytesIO(img_bytes)) as img:
            img.verify()

        with Image.open(io.BytesIO(img_bytes)) as img:
            img = Image.open(io.BytesIO(img_bytes))
            fmt = img.format.lower()
            mime = img.get_format_mimetype()
            log.debug(f"Image format detected: {fmt}, MIME type: {mime}")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 or image format")
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in SUPPORTED_IMAGE_FORMATS:
        raise HTTPException(status_code=400, detail="Unsupported image format")

    width, height = img.size
    log.debug(f"Image dimensions: {width}x{height}. Bytes size: {len(img_bytes)}")
    if len(img_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large")

    # S3 path and upload
    s3_key = f"{data.project}/{data.key}.{fmt}"
    s3_bucket = get_settings().aws_s3_bucket
    uploaded = upload_file_bytes(img_bytes, s3_bucket, s3_key, mime)
    if not uploaded:
        raise HTTPException(status_code=500, detail="Failed to upload to S3")

    await session.execute(
        text(
            """
INSERT INTO images (
    project, key, width, height, size, format, s3_path
) VALUES (
    :project, :key, :width, :height, :size, :format, :s3_path
) ON CONFLICT (project, key) DO UPDATE SET
    width = EXCLUDED.width,
    height = EXCLUDED.height,
    size = EXCLUDED.size,
    format = EXCLUDED.format,
    s3_path = EXCLUDED.s3_path
"""
        ),
        {
            "project": data.project,
            "key": data.key,
            "width": width,
            "height": height,
            "size": len(img_bytes),
            "format": fmt,
            "s3_path": s3_key,
        },
    )

    return ImagePostReturn(
        url=f"{get_settings().host}/images/{data.project}/{data.key}.{fmt}",
        width=width,
        height=height,
        size=len(img_bytes),
    )


@app.get("/images/{project}/{filename}", dependencies=[Depends(verify_token)])
async def get_image(
    project: str,
    filename: str,
    width: int = Query(None, gt=0),
    height: int = Query(None, gt=0),
    session: AsyncSession = Depends(get_session),
):
    if "." not in filename:
        log.debug(f"Filename without extension: {filename}")
        raise HTTPException(status_code=400, detail="Filename must include extension.")

    *key_parts, fmt = filename.split(".")
    key = ".".join(key_parts)
    fmt = fmt.lower()

    if fmt not in SUPPORTED_IMAGE_FORMATS:
        log.debug(f"Unsupported format requested: {fmt}")
        raise HTTPException(status_code=400, detail="Unsupported format requested.")

    db_fmt = "jpeg" if fmt == "jpg" else fmt

    image_not_found = HTTPException(status_code=404, detail="Image not found")

    # Look up in DB
    result = await session.execute(
        text(
            "SELECT format, s3_path FROM images WHERE project = :project AND key = :key"
        ),
        {"project": project, "key": key},
    )
    row = result.first()
    log.debug(f"DB lookup result: {row}")
    if not row:
        raise image_not_found
    stored_format, s3_path = row
    if stored_format != db_fmt:
        raise image_not_found

    # Fetch from S3
    s3_bucket = get_settings().aws_s3_bucket
    img_bytes = get_file_bytes(s3_bucket, s3_path)
    if not img_bytes:
        raise image_not_found

    # Open and optionally resize
    bio = io.BytesIO(img_bytes)
    with Image.open(bio) as img:
        orig_mime = img.get_format_mimetype()
        if width or height:
            img.thumbnail((width or img.width, height or img.height))
            out = io.BytesIO()
            img.save(out, format=img.format)
            out.seek(0)
            response_bytes = out
        else:
            bio.seek(0)
            response_bytes = bio

    return StreamingResponse(response_bytes, media_type=orig_mime)


@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify the service is running
    """
    return {"status": "ok", "message": "Service is running"}
