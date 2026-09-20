from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    cors_origins: str = "http://localhost:5173"

    database_url: str = "postgresql+psycopg2://labellens:labellens@localhost:5432/labellens"
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "labellens-evidence"
    s3_region: str = "us-east-1"

    # Per the brief, LabelLens only extracts English and Hindi (the two
    # languages Legal Metrology declarations are required/most commonly
    # printed in for this deployment) — kept configurable via env var rather
    # than hardcoded in ocr_service.py so a future deployment can extend it.
    paddleocr_langs: str = "en,hi"
    yolo_weights_path: str = "./app/services/weights/label_regions.pt"

    gov_rule_feed_enabled: bool = False
    gov_rule_feed_url: str = ""

    kafka_enabled: bool = False
    kafka_bootstrap_servers: str = "localhost:9092"

    # Product categories for which QR/barcode scanning is required and
    # cross-checked. Per the brief, barcode/QR scanning applies only to
    # electronic products — comma-separated so it can be tuned without a
    # code change. Category strings are matched case-insensitively.
    electronic_categories: str = "Electronics,Electronics Accessory,Electronic Appliance"

    # Standard ID-1 card dimensions (a debit/credit/Aadhaar-style card) in
    # millimetres, used as the default reference object for the font-size
    # calibration feature. ISO/IEC 7810 ID-1 size.
    reference_card_width_mm: float = 85.60
    reference_card_height_mm: float = 53.98

    # --- E-commerce listing compliance feature ---
    # Multimodal AI is used ONLY for extraction/understanding of unstructured
    # listing content (page text, product images) — never to decide
    # compliance. The deterministic rule_engine.py always makes the final
    # PASS/FAIL/NEEDS_VERIFICATION call, exactly as it does for physical
    # inspections. Disabled by default (no key) rather than pointed at a
    # fabricated endpoint — see app/services/multimodal_service.py.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    ecommerce_fetch_timeout_seconds: int = 15
    ecommerce_max_images: int = 6

    # Real e-commerce product pages usually render price/description/gallery
    # via client-side JS, which a plain HTTP GET never sees. When true (the
    # default), the ecommerce fetch renders the page with a headless browser
    # (Playwright) first, falling back to a plain HTTP GET automatically if
    # Playwright/Chromium isn't installed. See ecommerce_service.py.
    ecommerce_use_headless_browser: bool = True
    ecommerce_render_timeout_seconds: int = 20

    @property
    def multimodal_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def paddleocr_lang_list(self) -> list[str]:
        return [l.strip() for l in self.paddleocr_langs.split(",") if l.strip()]

    @property
    def electronic_category_list(self) -> list[str]:
        return [c.strip().lower() for c in self.electronic_categories.split(",") if c.strip()]

    def is_electronic_category(self, category: str | None) -> bool:
        if not category:
            return False
        return category.strip().lower() in self.electronic_category_list


@lru_cache
def get_settings() -> Settings:
    return Settings()
