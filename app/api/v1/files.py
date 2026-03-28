"""File management — upload/download for RFQ/PO documents."""

import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse

from ...db.session import get_db
from ...domain.enums import UserRole
from ...domain.exceptions import NotFoundError, ValidationError
from ..deps import get_current_user, require_role

router = APIRouter(prefix="/files", tags=["files"])

UPLOAD_DIR = "/opt/songchau/data/uploads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_TYPES = {".xlsx", ".xls", ".xlsm", ".pdf", ".csv", ".png", ".jpg", ".jpeg"}


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    category: str = Form("general"),
    linked_rfq: str = Form(""),
    linked_po: str = Form(""),
    conn=Depends(get_db),
    user=Depends(require_role(UserRole.admin, UserRole.procurement, UserRole.warehouse)),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_TYPES:
        raise ValidationError(f"File type '{ext}' not allowed")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise ValidationError("File too large (max 50MB)")

    # Save to disk
    year_month = datetime.now().strftime("%Y/%m")
    save_dir = os.path.join(UPLOAD_DIR, category, year_month)
    os.makedirs(save_dir, exist_ok=True)

    file_id = uuid.uuid4().hex[:12]
    safe_name = f"{file_id}_{file.filename}"
    save_path = os.path.join(save_dir, safe_name)

    with open(save_path, "wb") as f:
        f.write(content)

    # Index in DB
    row = await conn.fetchrow(
        """INSERT INTO file_metadata
           (filename, file_path, file_type, file_size, category,
            linked_rfq, linked_po, uploaded_by)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id""",
        file.filename, save_path, ext, len(content), category,
        linked_rfq or None, linked_po or None, user["id"],
    )

    return {
        "success": True,
        "id": row["id"],
        "filename": file.filename,
        "size": len(content),
        "category": category,
    }


@router.get("")
async def list_files(
    category: str = "", page: int = 1, limit: int = 50,
    conn=Depends(get_db), _=Depends(get_current_user),
):
    offset = (page - 1) * min(limit, 100)
    if category:
        rows = await conn.fetch(
            "SELECT id, filename, file_type, file_size, category, linked_rfq, linked_po, created_at "
            "FROM file_metadata WHERE category=$1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
            category, min(limit, 100), offset,
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM file_metadata WHERE category=$1", category)
    else:
        rows = await conn.fetch(
            "SELECT id, filename, file_type, file_size, category, linked_rfq, linked_po, created_at "
            "FROM file_metadata ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            min(limit, 100), offset,
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM file_metadata")
    return {"data": [dict(r) for r in rows], "total": total, "page": page}


@router.get("/download/{file_id}")
async def download_file(
    file_id: int, conn=Depends(get_db), _=Depends(get_current_user),
):
    row = await conn.fetchrow("SELECT * FROM file_metadata WHERE id = $1", file_id)
    if not row:
        raise NotFoundError("File", str(file_id))
    if not os.path.exists(row["file_path"]):
        raise NotFoundError("File on disk", str(file_id))
    return FileResponse(row["file_path"], filename=row["filename"])
