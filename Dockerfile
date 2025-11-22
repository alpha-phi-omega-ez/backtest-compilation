# Python official 3.14.0 image on debian trixie (v13)
FROM python:3.14.0-slim-trixie

# Copy uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1

# Set the working directory
WORKDIR /app

# Copy the required files
COPY uv.lock pyproject.toml process_data.py mongo.py main.py gsheet.py gdrive.py settings.py run.sh /app/

# Install the required packages
RUN uv sync --frozen --no-cache

# Run bash script that regulates when the package runs
CMD ["sh", "-c", "sh /app/run.sh"]
