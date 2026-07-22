# Build context = repository root (see docker-compose.yml)
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ ./shared/
COPY config/ ./config/
COPY services/key_orchestration_manager/app/ ./app/
EXPOSE 8084
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8084"]
