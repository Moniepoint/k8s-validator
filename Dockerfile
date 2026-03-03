# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir .

ENTRYPOINT ["k8s-validator"]