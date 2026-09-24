FROM python:3.11-slim

# Install system dependencies including Tesseract OCR for Linux
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download en_core_web_sm

# Copy application code
COPY . .

# Environment defaults
ENV FLASK_APP=app.py
ENV FLASK_DEBUG=0
ENV PORT=10000
ENV HOST=0.0.0.0
ENV TESSERACT_PATH=/usr/bin/tesseract
ENV SECRET_KEY=caretrack-ai-production-secret-key-render-2026
ENV FIELD_ENCRYPTION_KEY=h_G-L7B0l38yK6qf3vS2Hh782wR4-r85kC-v_1E4-j0=

EXPOSE 10000

# Run pre-flight database setup once, then start gunicorn
CMD ["sh", "-c", "python init_db.py && exec gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 2 --timeout 120 wsgi:app"]

