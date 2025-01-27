# Use the latest uv image with python 3.13 and alpine
FROM ghcr.io/astral-sh/uv:python3.13-alpine

# Set the working directory
WORKDIR /app

COPY uv.lock pyproject.toml process_data.py mongo.py main.py gsheet.py gdrive.py /app/

RUN uv sync --frozen --no-cache

# Install cron
RUN apk add --no-cache busybox-suid cron

# Add crontab file in the cron directory
COPY crontab /etc/crontabs/root

RUN chmod +x /app/main.py

# Give execution rights on the cron job
RUN chmod 0644 /etc/crontabs/root

# Run the command on container startup
CMD ["crond", "-f"]