#!/bin/bash
# COMO EXECUTAR
# chmod +x deploy_flask_apps.sh
# ./deploy_flask_apps.sh

# COMO VERIFICAR
# systemctl status oracle_kill
# systemctl status flask_queries

set -e

echo "=== DEPLOY AUTOMÁTICO FLASK APPS ==="

deploy_app () {
    APP_NAME=$1
    APP_DIR=$2
    PORT=$3
    SERVICE_NAME=$4

    echo ""
    echo ">>> Deployando $APP_NAME"

    cd $APP_DIR

    # 1. Criar venv se não existir
    if [ ! -d "venv" ]; then
        echo "Criando virtualenv..."
        python3 -m venv venv
    fi

    # 2. Instalar dependências
    echo "Instalando dependências..."
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt

    # 3. Ajustar app.py (porta + produção)
    echo "Configurando porta $PORT..."
    sed -i "/app.run(/c\    app.run(host=\"127.0.0.1\", port=$PORT, debug=False)" app.py

    # 4. Criar service systemd
    echo "Criando service $SERVICE_NAME..."
    sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null <<EOF
[Unit]
Description=$APP_NAME Flask App
After=network.target

[Service]
User=ti
Group=www-data
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python app.py
Restart=always
RestartSec=5
Environment=FLASK_ENV=production

[Install]
WantedBy=multi-user.target
EOF

    # 5. Ativar service
    sudo systemctl daemon-reload
    sudo systemctl enable $SERVICE_NAME
    sudo systemctl restart $SERVICE_NAME

    echo ">>> $APP_NAME DEPLOYADO com sucesso 🚀"
}

# ========================
# APPS
# ========================

deploy_app \
"Oracle Kill Sessions Monitor" \
"/var/www/html/OracleKillSessionsMonitor" \
5001 \
"oracle_kill"

deploy_app \
"Flask Queries" \
"/var/www/html/query-generator/flask_queries" \
5002 \
"flask_queries"

echo ""
echo "=== DEPLOY FINALIZADO ==="
echo "OracleKill: http://192.168.10.41:5001"
echo "FlaskQueries: http://192.168.10.41:5002"
