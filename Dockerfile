# Use an official Python 3.9 image as the base
FROM python:3.9-slim

# Install essential tools and system dependencies for Selenium and Firefox
RUN apt-get update && apt-get install -y \
    git \
    curl \
    unzip \
    wget \
    gnupg \
    build-essential \
    libnss3 \
    libgconf-2-4 \
    libxss1 \
    libappindicator3-1 \
    fonts-liberation \
    firefox-esr \
    xdg-utils \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
# Create a non-root user
RUN useradd --create-home --uid 1001 appuser
USER appuser

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY --chown=appuser:appuser . .

# Command to run the application
CMD ["python", "src/publish_queue_messages.py"]
