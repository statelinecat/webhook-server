# Dockerfile
FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование requirements и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY src/ ./src/

# Создание директорий для данных и логов
RUN mkdir -p data logs

# Открываем порт
EXPOSE 8001

# Запуск приложения
CMD ["python", "src/main.py"]