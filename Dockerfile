# Use the latest uv image with python 3.13 and alpine
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Set the working directory
WORKDIR /app

# Copy the required files
COPY uv.lock pyproject.toml process_data.py mongo.py main.py gsheet.py gdrive.py settings.py run.sh /app/

# Install the required packages
RUN uv sync --frozen --no-cache

# Run bash script that regulates when the package runs
CMD ["sh", "-c", "sh /app/run.sh"]