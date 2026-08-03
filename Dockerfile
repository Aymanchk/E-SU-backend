FROM python:3.12-slim

# PYTHONDONTWRITEBYTECODE - не создавать .pyc файлы
# PYTHONUNBUFFERED - выводить логи сразу, а не буферизовать
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Системные зависимости для psycopg и сборки пакетов
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Сначала зависимости, потом код.
# Так слой с pip install переиспользуется из кеша при изменении кода.
COPY requirements/ requirements/
RUN pip install --upgrade pip && \
    pip install -r requirements/development.txt

COPY . .

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "120"]
