"""
Seeds the database on first run: loads the YAML rule set into
`compliance_rules`, records the initial rule version, creates one demo
account per role (so the four login options on the frontend are actually
usable out of the box), and adds a couple of product registry entries so the
barcode cross-check has something real to compare against.

Run explicitly: `python -m app.db.seed` (also called automatically from
app/main.py on startup in development).
"""
import yaml
from pathlib import Path
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.db.models import (
    ComplianceRuleORM,
    RuleVersionHistory,
    User,
    ProductRegistryEntry,
    FontSizeStandardORM,
)
from app.core.security import hash_password

RULES_YAML_PATH = Path(__file__).resolve().parent.parent / "rules" / "legal_metrology_rules.yaml"
FONT_SIZE_YAML_PATH = Path(__file__).resolve().parent.parent / "rules" / "font_size_standards.yaml"

DEMO_USERS = [
    {"official_id": "insp001", "full_name": "R. Sharma", "role": "INSPECTOR", "password": "Inspector@123"},
    {"official_id": "sinsp001", "full_name": "K. Nair", "role": "SENIOR_INSPECTOR", "password": "SeniorInsp@123"},
    {"official_id": "admin001", "full_name": "System Administrator", "role": "ADMINISTRATOR", "password": "Admin@123"},
    {"official_id": "reg001", "full_name": "A. Verma", "role": "REGULATOR", "password": "Regulator@123"},
]

DEMO_PRODUCTS = [
    {
        "barcode": "8901030895555",
        "name": "Refined Sunflower Oil 1L",
        "brand": "SunGold",
        "manufacturer": "SunGold Edible Oils Pvt Ltd",
        "declared_net_quantity": "1 l",
        "category": "Packaged Food",
    },
    {
        "barcode": "8904004400123",
        "name": "Herbal Face Wash 100g",
        "brand": "Nirvana Herbals",
        "manufacturer": "Nirvana Herbals Pvt Ltd",
        "declared_net_quantity": "100 g",
        "category": "Cosmetics",
    },
]


def load_rules_from_yaml(db: Session) -> None:
    with open(RULES_YAML_PATH) as f:
        data = yaml.safe_load(f)

    version = data["version"]
    for rule in data["rules"]:
        existing = db.get(ComplianceRuleORM, rule["rule_id"])
        if existing:
            continue
        db.add(
            ComplianceRuleORM(
                rule_id=rule["rule_id"],
                name=rule["name"],
                description=rule["description"],
                applicable_category=rule["applicable_category"],
                requirement=rule["requirement"],
                validation_type=rule["validation_type"],
                severity=rule["severity"],
                source=rule["source"],
                version=version,
                effective_date=data["effective_date"],
                enabled=rule.get("enabled", True),
                params=rule.get("params", {}),
            )
        )

    if not db.get(RuleVersionHistory, version):
        db.add(
            RuleVersionHistory(
                version=version,
                source="Local YAML rule repository (app/rules/legal_metrology_rules.yaml)",
                change_summary="Initial rule set load.",
            )
        )
    db.commit()


def load_font_size_standards_from_yaml(db: Session) -> None:
    """ETL step for the font-size checking feature's configurable minimum-
    height standards — mirrors load_rules_from_yaml above."""
    with open(FONT_SIZE_YAML_PATH) as f:
        data = yaml.safe_load(f)

    version = data["version"]
    for standard in data["standards"]:
        existing = db.get(FontSizeStandardORM, standard["standard_id"])
        if existing:
            continue
        db.add(
            FontSizeStandardORM(
                standard_id=standard["standard_id"],
                name=standard["name"],
                keyword=standard.get("keyword", ""),
                min_height_mm=standard["min_height_mm"],
                source=standard["source"],
                version=version,
                enabled=standard.get("enabled", True),
            )
        )
    db.commit()


def seed_users(db: Session) -> None:
    for u in DEMO_USERS:
        if db.query(User).filter_by(official_id=u["official_id"]).first():
            continue
        db.add(
            User(
                official_id=u["official_id"],
                full_name=u["full_name"],
                role=u["role"],
                hashed_password=hash_password(u["password"]),
            )
        )
    db.commit()


def seed_products(db: Session) -> None:
    for p in DEMO_PRODUCTS:
        if db.get(ProductRegistryEntry, p["barcode"]):
            continue
        db.add(ProductRegistryEntry(**p))
    db.commit()


def run() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        load_rules_from_yaml(db)
        load_font_size_standards_from_yaml(db)
        seed_users(db)
        seed_products(db)
    finally:
        db.close()


if __name__ == "__main__":
    run()
    print("Seed complete. Demo credentials:")
    for u in DEMO_USERS:
        print(f"  {u['role']:<18} official_id={u['official_id']:<10} password={u['password']}")
