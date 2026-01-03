FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    flask==3.0.1 \
    gunicorn \
    sqlalchemy==2.0.25 \
    psycopg[binary]==3.1.18

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:8002", "app:app"]
