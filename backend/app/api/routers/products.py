from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import ProductRegistryEntry, Inspection, User
from app.api.deps import get_current_user

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/{barcode}")
def get_product(barcode: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    entry = db.get(ProductRegistryEntry, barcode)
    if not entry:
        raise HTTPException(status_code=404, detail="Product not found in registry")

    inspections = db.query(Inspection).filter(Inspection.barcode_raw_value == barcode).all()
    violation_count = sum(1 for i in inspections if i.status == "NON_COMPLIANT")

    return {
        "barcode": entry.barcode,
        "name": entry.name,
        "brand": entry.brand,
        "manufacturer": entry.manufacturer,
        "declaredNetQuantity": entry.declared_net_quantity,
        "category": entry.category,
        "inspectionCount": len(inspections),
        "violationCount": violation_count,
    }


@router.get("/{barcode}/history")
def get_product_history(barcode: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inspections = (
        db.query(Inspection)
        .filter(Inspection.barcode_raw_value == barcode)
        .order_by(Inspection.created_at.desc())
        .all()
    )
    return [
        {
            "id": i.id,
            "status": i.status,
            "inspectorName": i.inspector_name,
            "createdAt": i.created_at.isoformat(),
        }
        for i in inspections
    ]
