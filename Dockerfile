# Production Multi-Service Container (FastAPI + Streamlit)
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1 \
    HEADLESS=true \
    PORT=8501 \
    API_PORT=8000 \
    HOST=0.0.0.0

# Set working directory
WORKDIR /app

# Install system utilities needed for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure videos directory exists
RUN mkdir -p backend/videos

# Expose Streamlit (8501) and FastAPI (8000)
EXPOSE 8501 8000

# Health check
HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/api/health || exit 1

# Start orchestrator
CMD ["python", "run.py"]
