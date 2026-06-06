# ═══════════════════════════════════════════════════════════════════════════════
# Dockerfile — Backend
# ═══════════════════════════════════════════════════════════════════════════════

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
# We use torch CPU by default for the docker image to keep it lightweight.
# GPU passthrough requires nvidia-container-toolkit and a different base image.
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Start command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
