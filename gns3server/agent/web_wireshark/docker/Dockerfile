FROM debian:trixie

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Set UTF-8 locale to avoid Qt warnings
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

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
    curl \
    x11-utils \
    && rm -rf /var/lib/apt/lists/*

# Create gns3 user
RUN groupadd -g 1000 gns3 && \
    useradd -u 1000 -g gns3 -m -s /bin/bash gns3

# Create sessions directory with proper permissions
RUN mkdir -p /tmp/sessions && chmod 1777 /tmp/sessions

# Create XDG runtime directory for gns3 user
RUN mkdir -p /run/user/1000 && chown -R gns3:gns3 /run/user/1000 && chmod 700 /run/user/1000

# Set XDG environment variables
ENV XDG_RUNTIME_DIR=/run/user/1000

# Set default user
USER gns3

# No EXPOSE - port will be dynamically allocated
# Keep container running
CMD ["tail", "-f", "/dev/null"]
