# Web Wireshark 管理脚本 - 独立测试指南

## 快速测试

### 前提条件
- Docker 正在运行
- 虚拟环境已激活：`source venv/bin/activate`

### 基础测试命令

```bash
# 1. 启动会话（使用所有默认值）
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  --verbose start \
  --project-id "5af0fe00-f39d-4985-8669-7e8c512d729c" \
  --link-id "f233f27f-7432-49c3-9aa2-50e326a10eec" \
  --jwt-token "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc3NTc4MjI5MywidmVyIjowfQ.gFHuLijX86YOdmMYNckRJNiCbTTfYzGnE6RWJUlmQdk"

# 2. 使用自定义镜像
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  --verbose start \
  --project-id "af0fe00-f39d-4985-8669-7e8c512d729c" \
  --link-id "f233f27f-7432-49c3-9aa2-50e326a10eec" \
  --jwt-token "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc3NTc4MjI5MywidmVyIjowfQ.gFHuLijX86YOdmMYNckRJNiCbTTfYzGnE6RWJUlmQdk" \
  --image "gns3/web-wireshark:test"

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

## 资源参数配置

### 内存配置

```bash
# 默认 2GB 内存
--memory "2g"

# 自定义内存
--memory "4g"      # 4GB
--memory "512m"    # 512MB
--memory "1g" \
--memory-swap "2g"  # 1GB 内存 + 2GB 交换
```

### CPU 配置

```bash
# 默认 1 个 CPU 核心
--cpus 1.0

# 自定义 CPU
--cpus 0.5    # 50% CPU
--cpus 2.0    # 2 个 CPU 核心
--cpus 4.0    # 4 个 CPU 核心
```

### 进程数限制

```bash
# 默认最多 1000 个进程
--pids-limit 1000

# 自定义限制
--pids-limit 500     # 最多 500 个进程
--pids-limit 2000    # 最多 2000 个进程
```

### 完整示例（自定义资源）

```bash
# 使用自定义资源配置
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  --verbose start \
  --project-id "test-project" \
  --link-id "link-1" \
  --jwt-token "test-token" \
  --image "ubuntu:latest" \
  --memory "4g" \
  --memory-swap "6g" \
  --cpus 2.0 \
  --pids-limit 2000
```

## 参数对照表

| 参数 | 默认值 | 说明 | 示例 |
|------|--------|------|------|
| --image | gns3/web-wireshark:latest | Docker 镜像 | ubuntu:latest |
| --memory | 2g | 内存限制 | 4g, 512m |
| --memory-swap | 与 memory 相同 | 内存交换限制 | 4g, 8g |
| --cpus | 1.0 | CPU 核心数 | 0.5, 2.0 |
| --pids-limit | 1000 | 进程数限制 | 500, 2000 |

## 清理（如果测试失败）

```bash
# 删除测试容器
docker ps -a | grep 'gns3-wireshark-test' | awk '{print $1}' | xargs -r docker rm -f

# 删除测试网络
docker network ls | grep 'gns3-wireshark' | awk '{print $2}' | xargs -r docker network rm
```

## 注意事项

- 默认使用 `gns3/web-wireshark:latest` 镜像
- 使用 `--verbose` 查看详细日志
- 容器使用 172.28.0.0/16 网络
- xpra 端口范围：12300-12309
- **已修复**: CPU 现在正确分配为 1.0 核（之前错误地为 0.1 核）
- **已添加**: 健康检查 (xpra list)
- **已添加**: 日志配置 (json-file, max-size=10m, max-file=3)

