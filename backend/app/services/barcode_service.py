"""
Barcode / QR decoding and counterfeit-risk cross-check.

Decoding uses pyzbar (a real binding to the zbar C library) against the
actual captured barcode image — EAN-13/EAN-8/UPC-A/UPC-E/QR are all decoded
natively by zbar. Nothing here simulates a scan result.

`RegistryAdapter` is the pluggable interface the brief asks for: today it
only checks the local `product_registry` table, and always phrases a
mismatch as a verification prompt, never as proof of counterfeiting — that
determination is a human/legal one. A future official manufacturer or
government database can be wired in by implementing `lookup()` against that
real source and swapping the adapter instance, with zero changes to callers.
"""
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from pyzbar.pyzbar import decode as zbar_decode, ZBarSymbol
from sqlalchemy.orm import Session

from app.db.models import ProductRegistryEntry

SYMBOLOGY_MAP = {
    "EAN13": "EAN13",
    "EAN8": "EAN8",
    "UPCA": "UPC_A",
    "UPCE": "UPC_E",
    "QRCODE": "QR",
}


@dataclass
class DecodedBarcode:
    raw_value: str
    symbology: str


def decode_barcode(image: np.ndarray) -> DecodedBarcode | None:
    results = zbar_decode(
        image,
        symbols=[ZBarSymbol.EAN13, ZBarSymbol.EAN8, ZBarSymbol.UPCA, ZBarSymbol.UPCE, ZBarSymbol.QRCODE],
    )
    if not results:
        return None
    best = results[0]
    symbology = SYMBOLOGY_MAP.get(best.type, "UNKNOWN")
    return DecodedBarcode(raw_value=best.data.decode("utf-8", errors="replace"), symbology=symbology)


class RegistryAdapter(Protocol):
    def lookup(self, barcode: str) -> ProductRegistryEntry | None: ...


class LocalDbRegistryAdapter:
    """Checks the local `product_registry` table populated by inspectors/admins."""

    def __init__(self, db: Session):
        self.db = db

    def lookup(self, barcode: str) -> ProductRegistryEntry | None:
        return self.db.get(ProductRegistryEntry, barcode)


def cross_check(
    db: Session,
    decoded: DecodedBarcode | None,
    declared_brand: str,
    declared_manufacturer: str,
    declared_net_quantity: str | None,
) -> dict:
    if decoded is None:
        return {
            "rawValue": None,
            "symbology": None,
            "registryMatch": "NOT_SCANNED",
            "matchedProduct": None,
            "note": "No barcode was decoded from the captured image.",
        }

    adapter = LocalDbRegistryAdapter(db)
    entry = adapter.lookup(decoded.raw_value)

    if entry is None:
        return {
            "rawValue": decoded.raw_value,
            "symbology": decoded.symbology,
            "registryMatch": "NOT_FOUND",
            "matchedProduct": None,
            "note": "Barcode not found in the product registry — verification required before drawing "
            "any conclusion about the product's legitimacy.",
        }

    mismatches = []
    if declared_brand and entry.brand.strip().lower() != declared_brand.strip().lower():
        mismatches.append("brand")
    if declared_manufacturer and entry.manufacturer.strip().lower() != declared_manufacturer.strip().lower():
        mismatches.append("manufacturer")
    if declared_net_quantity and entry.declared_net_quantity.strip().lower() != declared_net_quantity.strip().lower():
        mismatches.append("net quantity")

    matched_product = {
        "name": entry.name,
        "brand": entry.brand,
        "manufacturer": entry.manufacturer,
        "declaredNetQuantity": entry.declared_net_quantity,
    }

    if mismatches:
        return {
            "rawValue": decoded.raw_value,
            "symbology": decoded.symbology,
            "registryMatch": "MISMATCH",
            "matchedProduct": matched_product,
            "note": f"Potential counterfeit risk / verification required — registry disagrees on: "
            f"{', '.join(mismatches)}. A barcode mismatch alone does not prove counterfeiting.",
        }

    return {
        "rawValue": decoded.raw_value,
        "symbology": decoded.symbology,
        "registryMatch": "MATCH",
        "matchedProduct": matched_product,
        "note": "Barcode matches the product registry.",
    }
