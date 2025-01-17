# Use the official Python 3.12 image based on Alpine
FROM python:3.13.1-alpine3.21

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
# Set the working directory
WORKDIR /app

COPY pyproject.toml .
COPY uv.lock .
COPY .python-version .

RUN uv sync --frozen --no-cache

COPY main.py .

# Install cron
RUN apk add --no-cache cronie

# Add crontab file in the cron directory
COPY crontab /etc/crontabs/root

# Give execution rights on the cron job
RUN chmod 0644 /etc/crontabs/root

# Create the log file to be able to run tail
RUN touch /var/log/cron.log

# Run the command on container startup
CMD ["crond", "-f", "-l", "2"]