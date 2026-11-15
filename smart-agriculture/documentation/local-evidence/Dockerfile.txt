
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY lambda_function.py .

ENV DATABASE_PATH=/data/smart_agriculture.db
ENV AWS_DEFAULT_REGION=eu-central-1

RUN mkdir -p /data

EXPOSE 5000

CMD ["python", "app.py"]
