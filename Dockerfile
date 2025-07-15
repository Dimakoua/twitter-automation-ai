FROM python:3.9-alpine3.14

RUN apk update && apk add --no-cache firefox-esr

ENV MOZ_HEADLESS=1 DISPLAY=:99

RUN adduser -D -u 1001 appuser
USER appuser

WORKDIR /app

ENV WDM_CACHE=/app/.wdm_cache
RUN mkdir -p $WDM_CACHE && chown -R appuser:appuser $WDM_CACHE

COPY requirements.txt .

# You might need to install build dependencies temporarily for some packages.
# RUN apk add --no-cache build-base  # Uncomment if needed (and remove after pip install)
RUN pip install --no-cache-dir -r requirements.txt
# RUN apk del build-base # Uncomment and run in same command as pip install if added above.

COPY . .

CMD ["python", "src/publish_queue_messages.py"]