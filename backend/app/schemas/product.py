from pydantic import BaseModel


class ProductOut(BaseModel):
    barcode: str
    name: str
    brand: str
    manufacturer: str
    declaredNetQuantity: str
    category: str
    inspectionCount: int
    violationCount: int
