from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models import Product
from app.schemas import ProductOut

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=list[ProductOut])
def list_products(
    brand: str | None = None,
    max_price: float | None = None,
    min_ram: int | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Product)
    if brand:
        stmt = stmt.where(Product.brand.ilike(brand))
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    if min_ram is not None:
        stmt = stmt.where(Product.ram >= min_ram)
    return list(db.scalars(stmt.order_by(Product.price).limit(100)).all())


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: str, db: Session = Depends(get_db)):
    from uuid import UUID
    from fastapi import HTTPException
    try:
        pid = UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid product ID")
    product = db.get(Product, pid)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
