# Base image
# This will be the ARM64 variant on your M1 Mac
FROM python:3.9-slim

# Install common dependencies needed for Chromium
RUN apt-get update && apt-get install -y \
    git \
    wget \
    gnupg \
    curl \
    unzip \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libappindicator3-1 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libnspr4 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm-dev \
    libgtk-3-0 \
    ca-certificates \
    libasound2 \
    libatspi2.0-0 \
    libcairo2 \
    libdbus-1-3 \
    libexpat1 \
    libglib2.0-0 \
    libpango-1.0-0 \
    libudev1 \
    libvulkan1 \
    libx11-6 \
    libxcb1 \
    libxext6 \
    libxfixes3 \
    libxkbcommon0 \
    libcurl4 \
    chromium-driver \
    # Install Chromium browser instead of Google Chrome
    chromium \
    # Remove --no-install-recommends for chromium for broader compatibility,
    # or be very selective with dependencies
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Add non-root user
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid $USER_GID $USERNAME && \
    useradd --uid $USER_UID --gid $USER_GID -m $USERNAME

RUN chmod 777 /usr/bin/chromedriver || true
# Set workdir and user
WORKDIR /workspace
USER $USERNAME