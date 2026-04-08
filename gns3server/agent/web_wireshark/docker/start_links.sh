#!/bin/bash

PROJECT_ID="5af0fe00-f39d-4985-8669-7e8c512d729c"
CONTAINER_NAME="gns3-${PROJECT_ID}"

LINKS=(
    "d79f156b-702c-455b-a725-d485733b7630"
    "bc1bd67b-774c-4138-a1dd-62da39f56a80"
    "8a14355e-4a62-406c-98de-acf5ec9394de"
)

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container $CONTAINER_NAME is not running. Starting..."
    docker run -d --name "$CONTAINER_NAME" gns3/web-wireshark:test tail -f /dev/null
    sleep 2
    echo "Container started."
fi

echo "Container: $CONTAINER_NAME"
echo ""

for i in "${!LINKS[@]}"; do
    LINK_ID="${LINKS[$i]}"
    DISPLAY_NUM=$((i + 1))
    PORT=$((10000 + DISPLAY_NUM))

    echo "========================================"
    echo "Starting link $DISPLAY_NUM"
    echo "Link ID: $LINK_ID"
    echo "Display: :$DISPLAY_NUM"
    echo "Port: $PORT"
    echo "========================================"

    docker exec -e LINK_ID="$DISPLAY_NUM" "$CONTAINER_NAME" /start.sh
    sleep 1
done

echo ""
echo "All links started."
echo "Use 'docker logs $CONTAINER_NAME' to view xpra status."
