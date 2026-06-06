import io
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status
from PIL import Image

from api.core.config import settings
from api.core.dependencies import AdminUser, DBSession
from api.models.product import Product
from api.schemas.common import MessageResponse

router = APIRouter(prefix="/uploads", tags=["uploads"])

_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
_MIME_TO_EXT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


def _validate_image(data: bytes) -> str:
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        fmt = img.format
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is not a valid image")
    if fmt not in _ALLOWED_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported format '{fmt}'. Allowed: JPEG, PNG, WebP",
        )
    return _MIME_TO_EXT[fmt]


@router.post("/products/{product_id}/image", response_model=dict)
async def upload_product_image(product_id: uuid.UUID, file: UploadFile, db: DBSession, _admin: AdminUser):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB",
        )

    ext = _validate_image(content)

    upload_dir = Path(settings.upload_dir) / "products"
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4()}.{ext}"
    dest = upload_dir / filename

    import aiofiles
    async with aiofiles.open(dest, "wb") as f:
        await f.write(content)

    # Remove old image file if present
    if product.image_url:
        old_path = Path(product.image_url.lstrip("/"))
        if old_path.exists():
            old_path.unlink(missing_ok=True)

    product.image_url = f"/{settings.upload_dir}/products/{filename}"
    await db.flush()

    return {"url": product.image_url}


@router.delete("/products/{product_id}/image", response_model=MessageResponse)
async def delete_product_image(product_id: uuid.UUID, db: DBSession, _admin: AdminUser):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if not product.image_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product has no image")

    path = Path(product.image_url.lstrip("/"))
    if path.exists():
        path.unlink(missing_ok=True)

    product.image_url = None
    await db.flush()
    return MessageResponse(message="Image deleted")
