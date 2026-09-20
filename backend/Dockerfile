FROM python:3.11-slim

# System deps: libzbar for barcode decoding, libgl/glib for OpenCV headless,
# and build tools some PaddlePaddle/Ultralytics wheels need at install time.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libzbar0 \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Headless Chromium for the E-Commerce Listing feature's JS-rendered fetch
# (app/services/ecommerce_service.py). --with-deps also installs the OS
# packages Chromium needs to actually run headless on a bare Linux image.
# If this step is skipped or fails, the feature falls back automatically to
# a plain HTTP fetch — it's not a hard requirement to boot the API.
RUN playwright install --with-deps chromium

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
