FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app PORT=9000
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/kms_mock/app/ ./app/
EXPOSE 9000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
