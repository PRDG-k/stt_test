# --- Stage 1: Build & Sync ---
FROM ghcr.io/astral-sh/uv:latest AS builder

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
# Copy only lock and pyproject to cache layers
COPY pyproject.toml uv.lock ./
# Install dependencies (frozen)
RUN uv sync --frozen --no-dev

# --- Stage 2: Runtime ---
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (ffmpeg for audio conversion)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy uv for runtime usage (optional but helpful)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependencies and source code
COPY --from=builder /app/.venv /app/.venv
COPY . .

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "app.main"]
