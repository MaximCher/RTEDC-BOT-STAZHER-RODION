FROM python:3.11-slim

ENV TZ=Europe/Moscow

WORKDIR /app

# System deps for building wheels + pdf parsing + chromium/selenium + fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    tzdata \
    chromium-driver \
    chromium \
    fonts-liberation \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf-xlib-2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

CMD ["python", "-m", "src.main"]

