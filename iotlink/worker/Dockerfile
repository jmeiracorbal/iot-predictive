FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY worker.py /app/worker.py
USER 65532:65532
CMD ["python", "-B", "/app/worker.py"]
