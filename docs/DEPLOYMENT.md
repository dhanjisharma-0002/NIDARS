# NIDARS — Production Deployment & Operations Guide

This guide details deployment options for NIDARS across Windows development, Linux VPS, and Cloud hosting environments.

---

## 1. Local Windows Development Setup

### Prerequisites
* Windows 11 / 10 64-bit
* Python 3.14+ (or Python 3.11–3.13)
* MySQL Server 8.0 running on `localhost:3306`

### Setup Instructions
1. Clone the repository and navigate into the folder:
   ```cmd
   cd C:\Users\DELL\NIDARS
   ```
2. Create and activate a Python virtual environment:
   ```cmd
   python -m venv venv
   .\venv\Scripts\activate
   ```
3. Install dependencies:
   ```cmd
   pip install -r requirements.txt
   ```
4. Configure `.env` from template:
   ```cmd
   copy .env.example .env
   ```
   *(Update MySQL credentials in `.env`)*
5. Apply database migrations:
   ```cmd
   python app.py db-upgrade
   ```
6. Run the application:
   ```cmd
   python app.py
   ```
   Open `http://127.0.0.1:5000` in your web browser.

---

## 2. Linux VPS Production Deployment (Ubuntu 22.04 / 24.04)

### A. System Packages & Python Setup
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip mysql-server nginx git
```

### B. MySQL Database Setup
```bash
sudo mysql -e "CREATE DATABASE nidars_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mysql -e "CREATE USER 'nidars_user'@'localhost' IDENTIFIED BY 'StrongProductionPassword!';"
sudo mysql -e "GRANT ALL PRIVILEGES ON nidars_db.* TO 'nidars_user'@'localhost'; FLUSH PRIVILEGES;"
```

### C. Application Setup & Migrations
```bash
cd /var/www/nidars
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

cp .env.example .env
# Edit .env with production database credentials and SECRET_KEY
python app.py db-upgrade
```

### D. Systemd Service (`/etc/systemd/system/nidars.service`)
```ini
[Unit]
Description=NIDARS Gunicorn WSGI Application
After=network.target mysql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/nidars
Environment="PATH=/var/www/nidars/venv/bin"
Environment="FLASK_ENV=production"
ExecStart=/var/www/nidars/venv/bin/gunicorn --workers 4 --bind 127.0.0.1:8000 wsgi:app

[Install]
WantedBy=multi-user.target
```
Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable nidars
sudo systemctl start nidars
```

### E. Nginx Reverse Proxy Configuration (`/etc/nginx/sites-available/nidars`)
```nginx
server {
    listen 80;
    server_name nidars.yourdomain.com;

    location /static/ {
        alias /var/www/nidars/static/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
Enable site and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/nidars /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx
```

### F. SSL Certificate (Let's Encrypt)
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d nidars.yourdomain.com
```

---

## 3. Cloud Container / PaaS Deployment (e.g. Render / Railway)
* **Build Command:** `pip install -r requirements.txt && python app.py db-upgrade`
* **Start Command:** `gunicorn wsgi:app`
* **Environment Variables:**
  * `FLASK_ENV=production`
  * `SECRET_KEY=...`
  * `DATABASE_URL=mysql+pymysql://user:pass@host:3306/nidars_db?charset=utf8mb4`
  * `OSRM_BASE_URL=https://router.project-osrm.org`
  * `OVERPASS_BASE_URL=https://overpass-api.de/api/interpreter`
