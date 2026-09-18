# Backend Dockerfile
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render dynamically injects the PORT env var; start.py binds to os.environ.get("PORT", 8000)
EXPOSE 8000

CMD ["python", "start.py"]
