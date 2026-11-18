FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get update && apt-get install -y --no-install-recommends iproute2 \
    && rm -rf /var/lib/apt/lists/*
COPY app ./app
COPY tests ./tests
COPY docker/entrypoint.py /opt/ai-entrypoint.py
EXPOSE 8090
ENTRYPOINT ["python", "/opt/ai-entrypoint.py"]
