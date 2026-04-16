FROM python:3.11-slim

# System deps: XML parsing libs + all Chromium runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libxshmfence1 \
    libx11-xcb1 \
    libcups2 \
    libxfixes3 \
    fonts-liberation \
    fonts-unifont \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium browser only (deps handled above)
RUN playwright install chromium

RUN python -m nltk.downloader averaged_perceptron_tagger_eng
COPY . .

EXPOSE 5000

# 1 worker: Chromium is memory-heavy; single worker prevents OOM
# Timeout 60s: Playwright rendering takes longer than a plain HTTP fetch
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "60", "app:app"]
