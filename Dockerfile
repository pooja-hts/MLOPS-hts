# Use official Python image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy rest of the project
COPY . .

# Create data directory (to ensure it's there)
RUN mkdir -p data/raw

# Default command (will be overridden in cloudbuild.yaml)
CMD ["scrapy", "crawl", "lulu"]
