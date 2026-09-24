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
ENV PORT=5000
ENV HOST=0.0.0.0
ENV TESSERACT_PATH=/usr/bin/tesseract

EXPOSE 5000

# Start production server using gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
