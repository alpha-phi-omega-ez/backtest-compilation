# Use the latest uv image with python 3.13 and alpine
FROM ghcr.io/astral-sh/uv:python3.13-alpine

# Set the working directory
WORKDIR /app

COPY uv.lock, .python-version, pyproject.toml ./

RUN uv sync --frozen --no-cache

COPY main.py .

# Install cron
RUN apk add --no-cache cronie

# Add crontab file in the cron directory
COPY crontab /etc/crontabs/root

# Give execution rights on the cron job
RUN chmod 0644 /etc/crontabs/root

# Run the command on container startup
CMD ["crond", "-f", "-l", "2"]