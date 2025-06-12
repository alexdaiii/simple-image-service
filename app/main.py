import base64
import io
import logging
import mimetypes
import os
from contextlib import asynccontextmanager
from pathlib import Path

from PIL import Image
from PIL import features
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import StreamingResponse, HTMLResponse, FileResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from app.database import (
    open_database_conn_pool,
    close_database_conn_pool,
    get_session,
    init_db,
)
from app.logging import configure_logging
from app.schema import ImagePost, ImagePostReturn, ImagesGetReturn
from app.auth.cloudflare import verify_token, get_claims, allowed_emails, email_allowed
from app.utils import get_settings
from app.boto_s3 import upload_file_bytes, get_file_stream, list_bucket_items

# --- ENVIRONMENT VARIABLES ---
if os.environ.get("ENV") == "development":
    print("Loading environment variables from .env file")
    load_dotenv()

SUPPORTED_IMAGE_FORMATS = {"avif", "png", "webp", "jpeg", "jpg"}



# --- DB SETUP ---
@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_settings()  # Ensure settings are loaded
    configure_logging(get_settings().log_level)
    await open_database_conn_pool()
    await init_db()
    check_supported_formats()  # Ensure PIL supports required formats
    yield
    await close_database_conn_pool()


app = FastAPI(lifespan=lifespan, dependencies=[Depends(verify_token)])
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins_list,
    allow_origin_regex=get_settings().allowed_origins_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

log = logging.getLogger(__name__)
def check_supported_formats():

    supported = {
        "avif": features.check_module("avif"),
        "webp": features.check_module("webp"),
        "jpeg": features.check_codec("jpg"),
        "png": features.check_codec("zlib")
    }

    log.info(f"Supported formats: {supported}")

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
) 


# Serve favicon.ico from /static/favicon.ico
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def read_root(
    request: Request,
    claims: dict = Depends(get_claims),
    allowed_emails: set[str] = Depends(allowed_emails),
):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "email": claims.get("email", ""),
            "cf_auth_cookie": request.cookies.get("CF_Authorization", ""),
            "allowed_to_post": claims.get("email", "") in allowed_emails,
        },
    )


@app.post("/images", dependencies=[Depends(email_allowed)])
async def upload_image(
    data: ImagePost, session: AsyncSession = Depends(get_session)
) -> ImagePostReturn:
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

@app.get("/images/{project}/{filename}")
async def get_image(project: str, filename: str):
    # Validate filename and extension
    if "." not in filename:
        raise HTTPException(status_code=400, detail="Filename must include extension.")

    *key_parts, ext = filename.split(".")
    ext = ext.lower()
    if ext == "jpg":
        ext = "jpeg"
    if ext not in SUPPORTED_IMAGE_FORMATS:
        raise HTTPException(status_code=400, detail="Unsupported format requested.")

    # Compose the S3 key
    s3_key = f"{project}/{'/'.join(key_parts)}.{ext}"

    # Try to fetch from S3 and stream
    try:
        s3obj = get_file_stream(get_settings().aws_s3_bucket, s3_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image not found")

    content_type = s3obj.get("ContentType") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    
    headers = {
        "Cache-Control": "public, max-age=2592000, stale-while-revalidate=1209600"
    }
    return StreamingResponse(s3obj["Body"], media_type=content_type, headers=headers)

@app.get("/images")
async def get_images(continuation_token: str | None = None) -> ImagesGetReturn:
    listItems = list_bucket_items(
        get_settings().aws_s3_bucket,
        continuation_token=continuation_token
    )
    images = [
        f"{get_settings().host}/images/{item['Key']}"
        for item in listItems["Contents"]
    ]

    return ImagesGetReturn(
        images=images,
        nextContinuationToken=listItems.get("ContinuationToken", "")
    )


@app.get("/health")
async def health_check(): 
    """
    Health check endpoint to verify the service is running
    """
    return {"status": "ok", "message": "Service is running"}
