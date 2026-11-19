from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.database.connection import get_db
from app.models import Policy, Product
from app.schemas import (
    PolicyCreate, PolicyOut, PolicyUpdate, ProductCreate, ProductOut, ProductUpdate,
)
from app.services.pdf_ingest import (
    MAX_CHUNKS, MAX_PDF_BYTES, PdfIngestError, chunk_text, extract_pdf_text,
)

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)])


# ------------------------------- Products -------------------------------- #
@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: UUID, payload: ProductUpdate, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is None:  # never null out a required column
            continue
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/products/{product_id}")
def delete_product(product_id: UUID, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"deleted": True}


# ------------------------------- Policies -------------------------------- #
@router.get("/policies", response_model=list[PolicyOut])
def list_policies(db: Session = Depends(get_db)):
    return list(db.scalars(select(Policy).order_by(Policy.category, Policy.title)).all())


@router.post("/policies", response_model=PolicyOut, status_code=201)
def create_policy(payload: PolicyCreate, db: Session = Depends(get_db)):
    policy = Policy(
        title=payload.title.strip(),
        category=payload.category.strip().lower(),
        content=payload.content.strip(),
        is_active=True,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.patch("/policies/{policy_id}", response_model=PolicyOut)
def update_policy(policy_id: UUID, payload: PolicyUpdate, db: Session = Depends(get_db)):
    policy = db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        setattr(policy, key, value.strip().lower() if key == "category" else value)
    db.commit()
    db.refresh(policy)
    return policy


@router.delete("/policies/{policy_id}")
def delete_policy(policy_id: UUID, db: Session = Depends(get_db)):
    policy = db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    db.delete(policy)
    db.commit()
    return {"deleted": True}


@router.post("/policies/upload-pdf", status_code=201)
def upload_policy_pdf(
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=150),
    category: str = Form(..., min_length=1, max_length=80),
    replace_existing: bool = Form(True),
    db: Session = Depends(get_db),
):
    data = file.file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail=f"PDF is larger than {MAX_PDF_BYTES // (1024 * 1024)} MB")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File is not a valid PDF")

    try:
        text = extract_pdf_text(data)
    except PdfIngestError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="No readable text found. Scanned/image-only PDFs need OCR, which is not supported.",
        )
    if len(chunks) > MAX_CHUNKS:
        raise HTTPException(status_code=422, detail=f"PDF is too long (more than {MAX_CHUNKS} sections).")

    title = title.strip()
    category = category.strip().lower()

    replaced = 0
    if replace_existing:
        result = db.execute(
            delete(Policy).where(
                (Policy.title == title) | Policy.title.startswith(f"{title} (part ", autoescape=True)
            )
        )
        replaced = result.rowcount or 0

    rows = []
    for i, chunk in enumerate(chunks, 1):
        row_title = title if len(chunks) == 1 else f"{title} (part {i}/{len(chunks)})"
        rows.append(Policy(title=row_title, category=category, content=chunk, is_active=True))
    db.add_all(rows)
    db.commit()
    return {"title": title, "category": category, "chunks_created": len(rows), "replaced_existing_rows": replaced}