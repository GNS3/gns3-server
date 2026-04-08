# GNS3 Web Wireshark Container

This container provides Wireshark access via xpra HTML5 client.

## Build Container

```bash
cd /home/yueguobin/myCode/GNS3/gns3-server/gns3server/agent/web_wireshark/docker
docker build -t gns3/web-wireshark:local .
```

## Test Container

```bash
# Run container with dynamic port allocation
docker run -d --name ws-test -P gns3/web-wireshark:local

# Get the assigned port
docker port ws-test

# Get xpra auth token
docker exec ws-test cat /tmp/xpra-auth-token

# Check logs
docker logs ws-test

# Verify xpra is running
docker exec ws-test ps aux | grep xpra

# Access xpra HTML5 client
# Open browser: http://localhost:<PORT>/?token=<TOKEN>
```

## Clean Up

```bash
# Stop and remove container
docker stop ws-test
docker rm ws-test
```

## xpra HTML5 Client

The xpra HTML5 client is served automatically by xpra's built-in HTTP server.
When you access the container's port in a browser, you'll see the xpra HTML5 interface.

## Files

- `Dockerfile` - Container image definition
- `start.sh` - Container startup script
- `README.md` - This file
