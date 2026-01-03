FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    django==5.0.1 \
    gunicorn \
    psycopg[binary]==3.1.18

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:8001", "project.wsgi:application"]
