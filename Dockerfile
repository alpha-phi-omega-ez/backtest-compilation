# Use the 3.14 official docker hardened python dev image with debian trixie (v13)
FROM dhi.io/python:3.14-debian13-dev AS builder

# Copy uv binary
COPY --from=dhi.io/uv:0 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1

# Set the working directory
WORKDIR /app

# Copy the required files
COPY uv.lock pyproject.toml /app/

# Install the required packages
RUN uv sync --frozen --no-cache --no-install-project

# Use the 3.14 official docker hardened python image with debian trixie (v13)
FROM dhi.io/python:3.14-debian13

# Copy the required files
COPY process_data.py mongo.py main.py gsheet.py gdrive.py settings.py scheduler.py /app/

# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv

# Set environment to use the installed packages
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Run Python scheduler that regulates when the package runs
CMD ["python", "scheduler.py"]
