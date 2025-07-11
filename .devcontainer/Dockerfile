# Use an official Python 3.9 image as the base
FROM python:3.9-slim

# Install essential tools and system dependencies
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
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
    libasound2 \
    libgbm1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for VS Code (best practice)
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid $USER_GID $USERNAME \
  && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME

# Set working directory
WORKDIR /workspace

# Switch to non-root user
USER $USERNAME
