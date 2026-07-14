# ==========================================
# Stage 1: Build the React Frontend
# ==========================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Copy package files and install dependencies
COPY frontend/package*.json ./
RUN npm install

# Copy source and build
COPY frontend/ ./
RUN npm run build

# ==========================================
# Stage 2: Build the Python Backend & App
# ==========================================
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DOCKER_ENV=true \
    OLLAMA_BASE_URL=http://host.docker.internal:11434

# Install system dependencies required for OpenCV, PyMuPDF, marker (libmagic), and native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libmagic1 \
    tesseract-ocr \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (Force CPU-only PyTorch to save 4GB of CUDA bloat)
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r backend/requirements.txt

# Copy backend source code
COPY backend/ ./backend/

# Pre-download Reranker model into the Docker image cache
RUN python -c "from sentence_transformers import CrossEncoder; \
    print('Pre-downloading BGE-Reranker...'); CrossEncoder('BAAI/bge-reranker-large')"

# Pre-download Marker/Surya PDF models by running it on a tiny dummy PDF
RUN python -c "pdf=b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n5 0 obj\n<< /Length 44 >>\nstream\nBT\n/F1 24 Tf\n100 700 Td\n(Offline Cache Test) Tj\nET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000223 00000 n \n0000000311 00000 n \ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n405\n%%EOF'; \
open('dummy.pdf', 'wb').write(pdf)" && \
    marker_single dummy.pdf marker_out && \
    rm -rf dummy.pdf marker_out

# Copy the built frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist/ ./frontend/dist/

# Expose FastAPI port
EXPOSE 8000

# Set working directory to backend so relative paths work as expected
WORKDIR /app/backend

# Command to run the application (Headless, no PyWebView)
CMD ["python", "main.py"]
