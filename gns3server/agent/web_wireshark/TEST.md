# Web Wireshark 管理脚本 - 独立测试指南

## 快速测试

### 前提条件
- Docker 正在运行
- 虚拟环境已激活：`source venv/bin/activate`

### 测试命令

```bash
# 1. 启动会话（使用默认镜像）
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  --verbose start \
  --project-id "test-project" \
  --link-id "link-1" \
  --jwt-token "test-token"

# 2. 启动会话（使用自定义镜像）
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  --verbose start \
  --project-id "test-project" \
  --link-id "link-1" \
  --jwt-token "test-token" \
  --image "ubuntu:latest"

# 3. 查看容器
docker ps | grep gns3-wireshark
docker logs gns3-wireshark-test-project

# 4. 停止会话
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  stop \
  --project-id "test-project" \
  --link-id "link-1"

# 5. 删除容器
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  delete-container \
  --project-id "test-project"
```

### 清理（如果测试失败）

```bash
# 删除测试容器
docker ps -a | grep 'gns3-wireshark-test' | awk '{print $1}' | xargs -r docker rm -f

# 删除测试网络
docker network ls | grep 'gns3-wireshark' | awk '{print $2}' | xargs -r docker network rm
```

## 注意事项

- 默认使用 `gns3/web-wireshark:latest` 镜像（可通过 `--image` 参数指定）
- 使用 `--verbose` 查看详细日志
- 容器使用 172.28.0.0/16 网络
- xpra 端口范围：12300-12309

## 测试技巧

### 使用本地镜像测试

如果没有 `gns3/web-wireshark:latest` 镜像，可以使用其他镜像测试：

```bash
# 使用 Ubuntu 镜像测试（仅测试容器创建/删除功能）
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  --verbose start \
  --project-id "test-ubuntu" \
  --link-id "link-1" \
  --jwt-token "test-token" \
  --image "ubuntu:latest"
```

### 查看可用镜像

```bash
# 查看本地镜像
docker images

# 搜索 Wireshark 相关镜像
docker search wireshark
```
