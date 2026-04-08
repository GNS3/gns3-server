FROM debian:trixie

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Add xpra official repository
RUN apt-get update && apt-get install -y \
    ca-certificates \
    wget \
    gnupg \
    && wget -O "/usr/share/keyrings/xpra.asc" https://xpra.org/xpra.asc \
    && echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/xpra.asc] https://xpra.org trixie main" > /etc/apt/sources.list.d/xpra.list \
    && apt-get update

# Install xpra and dependencies
RUN apt-get install -y \
    wireshark-common \
    wireshark \
    xpra \
    xvfb \
    x11-utils \
    && rm -rf /var/lib/apt/lists/*

# Create sessions directory with proper permissions
RUN mkdir -p /tmp/sessions && chmod 1777 /tmp/sessions

# No EXPOSE - port will be dynamically allocated
# Keep container running
CMD ["tail", "-f", "/dev/null"]
