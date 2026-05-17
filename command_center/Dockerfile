# =============================================================================
#  command_center/Dockerfile
#  Optimized for gcloud run deploy --source (Cloud Build)
# =============================================================================

FROM python:3.11-slim

# Prevents Python from writing .pyc files; forces stdout/stderr to be unbuffered
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

EXPOSE 8080

# Streamlit must bind to 0.0.0.0 and the PORT Cloud Run assigns (default 8080)
CMD ["streamlit", "run", "app.py", \
     "--server.port=8080", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
