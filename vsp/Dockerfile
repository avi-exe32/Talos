# =============================================================================
#  vsp/Dockerfile
#  Optimized for gcloud run deploy --source (Cloud Build)
# =============================================================================

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Uvicorn binds to 0.0.0.0 on PORT 8080 (Cloud Run standard)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
