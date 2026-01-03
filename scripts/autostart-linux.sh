#!/bin/bash
# Code Scanner Service Auto-Start for Linux (systemd)

set -e

SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"
SERVICE_NAME="code-scanner-service.service"
SERVICE_FILE="$SERVICE_DIR/$SERVICE_NAME"

function show_usage {
    echo "Usage: $0 {enable|disable|status}"
    echo ""
    echo "Commands:"
    echo "  enable   Enable and start the background service"
    echo "  disable  Stop and disable the background service"
    echo "  status   Check service status"
    exit 1
}

function enable_service {
    local python_path=$(which python3)
    local uv_path=$(which uv)

    # We use 'uv run code-scanner service'
    # Ensure full path to code-scanner executable or use uv
    # Assuming running from repo with uv installed
    
    echo "Installing service..."
    
    cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Code Scanner Background Service
After=network.target

[Service]
Type=simple
ExecStart=$uv_path run code-scanner service
Restart=always
RestartSec=60
WorkingDirectory=$(pwd)

[Install]
WantedBy=default.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable "$SERVICE_NAME"
    systemctl --user start "$SERVICE_NAME"
    
    echo "Code Scanner service enabled and started."
    echo "Use 'code-scanner add <path>' to start monitoring projects."
}

function disable_service {
    if [ -f "$SERVICE_FILE" ]; then
        systemctl --user stop "$SERVICE_NAME"
        systemctl --user disable "$SERVICE_NAME"
        rm "$SERVICE_FILE"
        systemctl --user daemon-reload
        echo "Code Scanner service disabled and removed."
    else
        echo "Service not installed."
    fi
}

function check_status {
    systemctl --user status "$SERVICE_NAME"
}

case "$1" in
    enable)
        enable_service
        ;;
    disable)
        disable_service
        ;;
    status)
        check_status
        ;;
    *)
        show_usage
        ;;
esac
