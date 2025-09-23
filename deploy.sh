#!/bin/bash
# deploy.sh

SERVER_IP="176.108.248.61"
SERVER_USER="stateline"
PROJECT_DIR="/home/stateline/webhook-server"
GITHUB_URL="https://github.com/statelinecat/webhook-server.git"

echo "🚀 Starting deployment to $SERVER_IP"

# 1. Клонируем/обновляем проект на сервере
echo "📥 Cloning/updating repository on server..."
ssh $SERVER_USER@$SERVER_IP "
    if [ -d '$PROJECT_DIR' ]; then
        cd $PROJECT_DIR
        git pull origin main
    else
        cd /home/stateline
        git clone $GITHUB_URL webhook-server
    fi
"

# 2. Копируем .env файл (если нужно)
echo "⚙️  Copying environment file..."
scp .env $SERVER_USER@$SERVER_IP:$PROJECT_DIR/

# 3. Останавливаем старые контейнеры и запускаем новые
echo "🐳 Starting Docker containers..."
ssh $SERVER_USER@$SERVER_IP "
    cd $PROJECT_DIR
    docker-compose down
    docker-compose build --no-cache
    docker-compose up -d
"

# 4. Ждем запуска и проверяем здоровье
echo "⏳ Waiting for application to start..."
sleep 10

# 5. Проверяем статус
echo "🔍 Checking application status..."
curl -f http://$SERVER_IP:8001/api/v1/health || echo "Application health check failed"

echo "✅ Deployment completed!"
echo "🌐 Application URL: http://$SERVER_IP:8001"
echo "📊 API Docs: http://$SERVER_IP:8001/docs"