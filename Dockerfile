# Base image for ARM64 (python:3.9-slim will pull ARM64 on M1 Mac)
FROM python:3.9-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    chromium \
    chromium-driver \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libappindicator3-1 \
    libgtk-3-0 \
    libu2f-udev \
    firefox-esr \
    xdg-utils \
    # Clean up apt lists to reduce image size
    && rm -rf /var/lib/apt/lists/*

ARG USERNAME=appuser
ARG USER_UID=1001
ARG USER_GID=1001
RUN groupadd --gid $USER_GID $USERNAME && \
    useradd --uid $USER_UID --gid $USER_GID -m $USERNAME

RUN chmod 777 /usr/bin/chromedriver || true
# Set workdir for the user
WORKDIR /app

# Create directories that will be used for volume mounts and set their permissions for the non-root user.
# This ensures that when volumes are mounted, the mount points have the correct ownership.
RUN mkdir -p /app/twitter_queue /app/media_files /app/.wdm_cache && \
    chown -R $USERNAME:$USERNAME /app/twitter_queue /app/media_files /app/.wdm_cache && \
    chmod -R +rw /app/twitter_queue /app/media_files /app/.wdm_cache

USER $USERNAME

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /home/$USERNAME/.local/share/undetected_chromedriver && \
    chown -R $USERNAME:$USERNAME /home/$USERNAME/.local

COPY . .

CMD ["python", "src/scheduler.py"]