server {
    if ($host = hook.statelinecat.ru) {
        return 301 https://$host$request_uri;
    } # managed by Certbot


    listen 80;
    server_name hook.statelinecat.ru;
    return 301 https://$host$request_uri;


}

server {
    listen 443 ssl http2;
    server_name hook.statelinecat.ru;

    # Используем тот же сертификат, что и для statelinecat.ru
    ssl_certificate /etc/letsencrypt/live/hook.statelinecat.ru/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/hook.statelinecat.ru/privkey.pem; # managed by Certbot


    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

}
