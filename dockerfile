FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Создание директорий
RUN mkdir -p data logs

EXPOSE 8001

# Правильный запуск - используем модуль src
CMD ["python", "-m", "src.main"]