FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8090
# 1 Worker mit Threads: die laufenden Suchen leben im Prozess-Speicher
CMD ["gunicorn", "--bind", "0.0.0.0:8090", "--workers", "1", "--threads", "8", \
     "--timeout", "300", "app:app"]
