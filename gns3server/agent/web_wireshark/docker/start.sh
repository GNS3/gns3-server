#!/bin/bash
set -e

echo "Starting GNS3 Web Wireshark container..."

# Get link_id from environment or use default
LINK_ID="${LINK_ID:-0}"
DISPLAY_NUM="${LINK_ID}"
DISPLAY=":${DISPLAY_NUM}"
PORT=$((10000 + LINK_ID))

echo "Link ID: $LINK_ID"
echo "Display: $DISPLAY"
echo "Port: $PORT"

# Cleanup old session for this link
echo "Cleaning up old sessions for link $LINK_ID..."
rm -rf /tmp/sessions/link-${LINK_ID}

# Start Xvfb on display :N if not already running
if ! pgrep -f "Xvfb.*${DISPLAY}" > /dev/null; then
    echo "Starting Xvfb on $DISPLAY..."
    Xvfb "$DISPLAY" -screen 0 1920x1080x24 +extension GLX +extension Composite -dpi 96 -noreset &
    sleep 2
fi

# Start xpra session for this link
echo "Starting xpra session for link $LINK_ID on $DISPLAY..."
xpra start "$DISPLAY" \
    --html=on \
    --bind-tcp=127.0.0.1:${PORT} \
    --session-name="link-${LINK_ID}" \
    --daemon=yes \
    --use-display \
    --dbus-launch=no &

# Wait for xpra to initialize
echo "Waiting for xpra to be ready..."
sleep 3

# Verify xpra is running
if ! pgrep -f "xpra.*${DISPLAY}" > /dev/null; then
    echo "ERROR: xpra failed to start for link $LINK_ID"
    exit 1
fi

echo "========================================"
echo "GNS3 Web Wireshark ready for link $LINK_ID"
echo "Display: $DISPLAY"
echo "Container port: $PORT"
echo "========================================"

# Keep container running
tail -f /dev/null
