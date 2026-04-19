# Ubuntu 24.04 GNS3 Development Environment Setup

## Simplified Development Environment Setup

### 1. Add PPA

```bash
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:gns3/ppa
sudo apt update
```

### 2. Install Dependencies

Binary tools (Dynamips, VPCS, uBridge, etc.) are automatically installed as gns3-server dependencies

```bash
sudo apt install gns3-server tshark
```

### 3. Remove gns3-server While Keeping Dependencies

If you only want to run the server from source:

```bash
# Remove main package only, keep dependencies
sudo apt remove gns3-server

# Mark dependencies as manual to prevent autoremove deletion
sudo apt-mark manual ubridge dynamips vpcs libvirt
```

### 4. Install and Start Docker

```bash
sudo apt install docker.io
sudo systemctl enable --now docker
```

#### Configure Docker Mirror Accelerator (China Mainland)

If Docker Hub is inaccessible, configure mirror accelerators:

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me"
  ]
}
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
```

Verify:

```bash
docker info | grep -i mirror
```

### 5. Add User to Groups

```bash
# If running as gns3 user (created by PPA install):
sudo usermod -aG ubridge,docker,kvm gns3

# If running as your own user, add yourself to these groups:
sudo usermod -aG ubridge,docker,kvm $USER

# Then logout and login again for group membership to take effect
```

### 6. Install Python venv

```bash
sudo apt install python3.12-venv
```

### 7. Run Development Version from Source

Clone the repository (official or your fork):

```bash
# Official repository
git clone https://github.com/GNS3/gns3-server.git

# Or your forked repository
git clone https://github.com/yourname/gns3-server.git
cd gns3-server
git checkout your-branch
```

Setup virtual environment and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate

# For China mainland users, use mirror:
# pip install -e . -i https://mirrors.aliyun.com/pypi/simple/

pip install -e . && gns3-wireshark-setup
pip install -e .[ai-copilot]
pip install -e .[dev]
```

Run the server:

```bash
python3 -m gns3server
```

## Optional: Install AI Copilot Development Dependencies

```bash
python3 -m pip install .[ai-copilot,dev]
```

## Optional: Expand LVM Root Partition

If the root partition is low on space but the volume group has unallocated space:

Check LVM status:

```bash
sudo lvm pvdisplay
sudo lvm vgdisplay
sudo lvm lvdisplay
```

Extend the root LV using all free space:

```bash
sudo lvm lvextend -l +100%FREE /dev/mapper/ubuntu--vg-ubuntu--lv
sudo resize2fs /dev/mapper/ubuntu--vg-ubuntu--lv
```

Verify:

```bash
df -h
```
