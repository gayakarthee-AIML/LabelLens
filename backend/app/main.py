import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.api.routers import auth, inspections, rules, products, dashboard, users, font_size
from app.db import seed

settings = get_settings()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("labellens")

app = FastAPI(
    title="LabelLens API",
    description="AI-assisted Legal Metrology compliance and inspection platform.",
    version="0.1.0",
)


@app.middleware("http")
async def catch_unhandled_exceptions(request: Request, call_next):
    """
    Registering a handler via @app.exception_handler(Exception) does NOT fix
    this (verified, not assumed) — FastAPI/Starlette specifically routes a
    handler for the bare `Exception` class to the outermost
    ServerErrorMiddleware, which sits *outside* CORSMiddleware, so its
    response still skips CORS headers.

    This middleware fixes it for real: it fully catches the exception
    itself and returns a normal Response, so nothing ever escapes to
    ServerErrorMiddleware. As long as this middleware is registered BEFORE
    app.add_middleware(CORSMiddleware, ...) below (Starlette wraps
    later-added middleware more outer), CORSMiddleware sees this as an
    ordinary response and attaches the CORS header the same way it would
    for a 200. Without this, every unhandled backend bug shows up in the
    browser as a misleading "CORS blocked" error instead of the real 500 —
    which is exactly what happened during development (see backend/README.md).
    The full traceback is still logged server-side either way.
    """
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected server error occurred. Check the API server logs for the full traceback."},
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(inspections.router, prefix=API_PREFIX)
app.include_router(rules.router, prefix=API_PREFIX)
app.include_router(products.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(font_size.router, prefix=API_PREFIX)


@app.on_event("startup")
def on_startup():
    if settings.environment == "development":
        # Convenience for local/Colab runs: creates tables and seeds demo
        # users/rules/products if they don't already exist. In a real
        # deployment, use Alembic migrations (see backend/alembic/) instead
        # and seed production accounts through a controlled admin process.
        seed.run()


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "labellens-api"}
