#!/bin/bash
# Code Scanner Service Auto-Start for macOS (launchd)

set -e

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCH_AGENTS_DIR"
PLIST_NAME="com.codescanner.service"
PLIST_FILE="$LAUNCH_AGENTS_DIR/$PLIST_NAME.plist"

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
    local uv_path=$(which uv)
    local work_dir=$(pwd)

    echo "Installing service..."
    
    cat <<EOF > "$PLIST_FILE"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$uv_path</string>
        <string>run</string>
        <string>code-scanner</string>
        <string>service</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$work_dir</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/code-scanner-service.out</string>
    <key>StandardErrorPath</key>
    <string>/tmp/code-scanner-service.err</string>
</dict>
</plist>
EOF

    launchctl load "$PLIST_FILE"
    
    echo "Code Scanner service enabled and started."
    echo "Use 'code-scanner add <path>' to start monitoring projects."
}

function disable_service {
    if [ -f "$PLIST_FILE" ]; then
        launchctl unload "$PLIST_FILE"
        rm "$PLIST_FILE"
        echo "Code Scanner service disabled and removed."
    else
        echo "Service not installed."
    fi
}

function check_status {
    launchctl list | grep "$PLIST_NAME"
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
