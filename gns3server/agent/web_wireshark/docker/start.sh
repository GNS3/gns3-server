#!/bin/bash
set -e

echo "Starting GNS3 Web Wireshark container..."

# Cleanup old session files and tokens on startup
echo "Cleaning up old sessions..."
rm -rf /tmp/sessions/link-*/token.txt
rm -rf /tmp/sessions/link-*/xpra-auth-token
rm -f /tmp/xpra-auth-token

# Generate xpra auth token
echo "Generating xpra authentication token..."
XPRA_AUTH_TOKEN=$(openssl rand -hex 16)
echo "$XPRA_AUTH_TOKEN" > /tmp/xpra-auth-token
chmod 0600 /tmp/xpra-auth-token
echo "Token saved to /tmp/xpra-auth-token"

# Use display :0
DISPLAY=":0"
echo "Using display: $DISPLAY"

# Start Xvfb on :0 if not already running
if ! pgrep -f "Xvfb.*$DISPLAY" > /dev/null; then
    echo "Starting Xvfb on $DISPLAY..."
    Xvfb "$DISPLAY" -screen 0 1920x1080x24 +extension GLX +extension Composite -dpi 96 -noreset &
    sleep 2
fi

# Start xpra with HTML5 support
echo "Starting xpra on $DISPLAY..."
xpra start "$DISPLAY" \
    --html=on \
    --bind-tcp=0.0.0.0:10000 \
    --daemon=yes \
    --use-display \
    --dbus-launch=no &

# Wait for xpra to initialize
echo "Waiting for xpra to be ready..."
sleep 3

# Verify xpra is running
if ! pgrep -f "xpra.*$DISPLAY" > /dev/null; then
    echo "ERROR: xpra failed to start"
    exit 1
fi

echo "========================================"
echo "GNS3 Web Wireshark container ready!"
echo "Display: $DISPLAY"
echo "HTTP port: 10000"
echo "xpra auth token: $XPRA_AUTH_TOKEN"
echo "========================================"

# Keep container running
tail -f /dev/null
