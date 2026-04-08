# GNS3 Web Wireshark 容器管理指南

本文档描述如何管理 GNS3 Web Wireshark 容器，通过 Docker 网络实现与宿主机的通信，无需绑定端口。

## 架构概述

```
┌─────────────────────────────────────────────────┐
│              宿主机                               │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │   Docker Network: gns3-wireshark           │ │
│  │   (桥接网络，容器与宿主机可通信)             │ │
│  │                                             │ │
│  │  ┌──────────────────────────────────────┐ │ │
│  │  │  Container: gns3-PROJECT-ID          │ │ │
│  │  │                                      │ │ │
│  │  │  Link 1: Display :1, Port 10001     │ │ │
│  │  │  Link 2: Display :2, Port 10002     │ │ │
│  │  │  Link 3: Display :3, Port 10003     │ │ │
│  │  │  ...                                 │ │ │
│  │  └──────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

## 性能指标与资源规划

### 单个 Wireshark 实例资源占用

| 资源类型 | 占用量 | 说明 |
|---------|--------|------|
| **内存** | 150-250 MB | 取决于抓包流量和解析的协议数量 |
| **CPU** | 0.5-2% | 空闲时较低，高流量时上升 |
| **线程数** | ~30 个线程 | Wireshark 多线程架构（GUI、抓包、解析、渲染） |
| **磁盘 I/O** | 最小 | 主要是日志写入 |

### 容器资源配置建议

基于 `--pids-limit 1000` 和 `--memory="2g"` 的配置：

| Wireshark 实例数 | 预计线程占用 | 预计内存占用 | 推荐场景 |
|-----------------|-------------|-------------|---------|
| 1-3 | 120-200 线程 | 450-750 MB | 轻量级项目，小型拓扑 |
| 4-6 | 230-290 线程 | 600-1.5 GB | 中型项目，多个网络链路 |
| 7-10 | 320-410 线程 | 1-2.5 GB | 大型项目，密集抓包 |
| 10+ | >400 线程 | >2.5 GB | ⚠️ 需要增加内存限制 |

### 实际测试数据

**测试环境：** 3 个 Wireshark 实例同时运行

```
CONTAINER ID   NAME                     CPU %     MEM USAGE / LIMIT   MEM %     NET I/O          BLOCK I/O     PIDS
19363d29bd9d   gns3-PROJECT-ID          4.59%     735.6MiB / 2GiB     35.92%    386kB / 38.6MB   0B / 15.5MB   201
```

**详细进程统计：**
- 总线程数：~204
- 总进程数：~61
- 每个 Wireshark 实例：~30 线程 + 1 个父进程

### 性能优化建议

1. **内存是主要瓶颈**，而非 PID 限制
   - 默认 2GB 内存可支持 6-8 个 Wireshark 实例
   - 需要更多实例时，优先增加内存而非 PID 限制

2. **按需启动 Wireshark**
   - 只为需要抓包的链路启动 Wireshark
   - 使用完毕后及时停止会话释放资源

3. **多容器策略**
   - 对于超大型项目（10+ 链路），建议使用多个容器
   - 每个容器负责 5-8 个链路，资源隔离更稳定

4. **监控资源使用**
   ```bash
   # 实时监控容器资源
   docker stats gns3-PROJECT-ID

   # 检查容器内进程数
   docker exec gns3-PROJECT_ID bash -c "ps -eLf | wc -l"
   ```

## 1. 创建 Docker 网络

首先创建一个桥接网络，用于容器与宿主机之间的通信：

```bash
# 创建 gns3-wireshark 网络
docker network create \
  --driver bridge \
  --subnet=172.28.0.0/16 \
  gns3-wireshark
```

**说明：**
- 使用 bridge 驱动
- 子网范围：172.28.0.0/16
- 容器连接到此网络后，可通过容器IP直接访问服务

### 删除 Docker 网络

```bash
# 删除 gns3-wireshark 网络
docker network rm gns3-wireshark
```

**⚠️ 重要提示：**
- 删除网络前，必须先停止并断开所有连接到此网络的容器
- 否则会报错：`Error: network X has active endpoints`
- 强制删除网络会中断所有容器的网络连接

### 查看网络信息

```bash
# 查看所有 Docker 网络
docker network ls

# 查看 gns3-wireshark 网络详细信息
docker network inspect gns3-wireshark

# 查看连接到该网络的容器
docker network inspect gns3-wireshark -f '{{range .Containers}}{{.Name}} {{end}}'
```

### 断开容器与网络的连接

```bash
# 断开指定容器与网络的连接
CONTAINER_NAME="gns3-${PROJECT_ID}"
docker network disconnect gns3-wireshark "${CONTAINER_NAME}"
```

### 安全删除网络的完整流程

```bash
# 1. 查看网络中所有容器
docker network inspect gns3-wireshark -f '{{range .Containers}}{{.Name}} {{end}}'

# 2. 停止所有使用该网络的容器
docker stop gns3-project-1
docker stop gns3-project-2
# ... 或批量停止所有相关容器

# 3. 删除网络
docker network rm gns3-wireshark
```

## 2. 启动容器

```bash
# 设置项目ID
PROJECT_ID="5af0fe00-f39d-4985-8669-7e8c512d729c"

# 启动容器
docker run -d \
  --name "gns3-5af0fe00-f39d-4985-8669-7e8c512d729c" \
  --memory="2g" \
  --memory-swap="2g" \
  --cpus="1.0" \
  --pids-limit 1000 \
  --log-driver json-file \
  --log-opt max-size="10m" \
  --log-opt max-file="3" \
  --network gns3-wireshark \
  --health-cmd="xpra list || exit 1" \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  --restart unless-stopped \
  gns3/web-wireshark:test
```

**参数说明：**
- `--name`: 容器名称，格式为 `gns3-PROJECT-ID`
- `--network`: 连接到 gns3-wireshark 网络
- `-d`: 后台运行

## 3. 启动 Wireshark 实例

根据 Link ID 启动不同的 Wireshark 实例，每个实例对应一个独立的 Display 和 Port。

### 3.1 启动单个 Link 的 Wireshark

```bash
# 8a14355e-4a62-406c-98de-acf5ec9394de
# f233f27f-7432-49c3-9aa2-50e326a10eec
# a0d9132c-0f65-4ff8-9e5f-1c8061f70bdd

# 启动 xpra 会话
docker exec gns3-5af0fe00-f39d-4985-8669-7e8c512d729c \
  xpra start ":101" \
  --xvfb="Xvfb -screen 0 1920x1080x24 +extension RANDR" \
  --html=on \
  --bind-tcp=0.0.0.0:12345 \
  --session-name="link-8a14355e-4a62-406c-98de-acf5ec9394de" \
  --daemon=yes \
  --dbus-launch=no \
  --resize-display=yes


docker exec gns3-5af0fe00-f39d-4985-8669-7e8c512d729c \
  xpra start ":102" \
  --xvfb="Xvfb -screen 0 1920x1080x24 +extension RANDR" \
  --html=on \
  --bind-tcp=0.0.0.0:12346 \
  --session-name="link-f233f27f-7432-49c3-9aa2-50e326a10eec" \
  --daemon=yes \
  --dbus-launch=no \
  --resize-display=yes


docker exec gns3-5af0fe00-f39d-4985-8669-7e8c512d729c \
  xpra start ":103" \
  --xvfb="Xvfb -screen 0 1920x1080x24 +extension RANDR" \
  --html=on \
  --bind-tcp=0.0.0.0:12347 \
  --session-name="link-a0d9132c-0f65-4ff8-9e5f-1c8061f70bdd" \
  --daemon=yes \
  --dbus-launch=no \
  --resize-display=yes

# 等待 xpra 初始化
sleep 3

# 启动 Wireshark 应用程序
docker exec -d "${CONTAINER_NAME}" \
  sh -c "DISPLAY=:${DISPLAY_ID} wireshark &"

# 等待 Wireshark 启动
sleep 2

# 验证 Wireshark 是否运行
docker exec "${CONTAINER_NAME}" \
  ps aux | grep wireshark | grep -v grep

# 验证 xpra 是否成功启动
docker exec "${CONTAINER_NAME}" \
  xpra list | grep ":${DISPLAY_ID}"
```

### 3.2 将 GNS3 抓包流传递给 Wireshark

在容器中运行

```bash
docker exec gns3-5af0fe00-f39d-4985-8669-7e8c512d729c \
    bash -c 'curl -N -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc3NTcyMjMwMCwidmVyIjowfQ.gCv42XkJu9AeoUssVCOjp1aJdqoYSEsXLWHk00C8PZk" \
      "http://192.168.1.140:3080/v3/projects/5af0fe00-f39d-4985-8669-7e8c512d729c/links/8a14355e-4a62-406c-98de-acf5ec9394de/capture/stream" | \
      wireshark -i - -k -display :101'

docker exec gns3-5af0fe00-f39d-4985-8669-7e8c512d729c \
    bash -c 'curl -N -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc3NTcyMjMwMCwidmVyIjowfQ.gCv42XkJu9AeoUssVCOjp1aJdqoYSEsXLWHk00C8PZk" \
      "http://192.168.1.140:3080/v3/projects/5af0fe00-f39d-4985-8669-7e8c512d729c/links/f233f27f-7432-49c3-9aa2-50e326a10eec/capture/stream" | \
      wireshark -i - -k -display :102'

docker exec gns3-5af0fe00-f39d-4985-8669-7e8c512d729c \
    bash -c 'curl -N -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc3NTcyMjMwMCwidmVyIjowfQ.gCv42XkJu9AeoUssVCOjp1aJdqoYSEsXLWHk00C8PZk" \
      "http://192.168.1.140:3080/v3/projects/5af0fe00-f39d-4985-8669-7e8c512d729c/links/a0d9132c-0f65-4ff8-9e5f-1c8061f70bdd/capture/stream" | \
      wireshark -i - -k -display :103'
```

**参数说明：**
- `curl -N`：禁用缓冲，实时传输数据
- `-H "Authorization: Bearer ${GNS3_JWT_TOKEN}"`：添加 JWT 认证头
- `/v3/projects/{project_id}/links/{link_id}/capture/stream`：GNS3 抓包流接口
- `docker exec -i`：保持 stdin 打开，传递管道数据
- `wireshark -i - -k`：从标准输入读取 pcap 数据并立即开始抓包

**注意事项：**
1. 确保 Wireshark 已经在指定的 Display 上运行
2. JWT Token 需要有访问该项目的权限
3. 如果遇到权限问题，检查 GNS3 服务器的认证配置



## 4. 获取容器 IP 地址

```bash
# 获取容器的 IP 地址
CONTAINER_NAME="gns3-${PROJECT_ID}"
CONTAINER_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "${CONTAINER_NAME}")

echo "Container IP: ${CONTAINER_IP}"
```

## 5. 访问 Wireshark Web 界面

在浏览器中访问：

```
http://<容器IP>:<端口>
```

**示例：**
- Link 1: http://172.28.0.2:10001
- Link 2: http://172.28.0.2:10002
- Link 3: http://172.28.0.2:10003

## 6. 管理命令

### 6.1 查看所有活动的 xpra 会话

```bash
docker exec "${CONTAINER_NAME}" xpra list
```

### 6.2 停止指定 Link 的会话

```bash
LINK_ID=1
DISPLAY_ID=$LINK_ID

docker exec "${CONTAINER_NAME}" xpra stop ":${DISPLAY_ID}"
```

### 6.3 查看容器日志

```bash
docker logs "${CONTAINER_NAME}"
```

### 6.4 查看容器内进程

```bash
docker exec "${CONTAINER_NAME}" ps aux | grep -E "Xvfb|xpra"
```

### 6.5 进入容器 Shell

```bash
docker exec -it "${CONTAINER_NAME}" /bin/bash
```

### 6.6 停止容器

```bash
docker stop "${CONTAINER_NAME}"
```

### 6.7 删除容器

```bash
docker rm "${CONTAINER_NAME}"
```

## 9. 故障排查

### 9.1 检查容器是否运行

```bash
docker ps | grep "${CONTAINER_NAME}"
```

### 9.2 检查网络连接

```bash
# 从宿主机 ping 容器
docker exec "${CONTAINER_NAME}" ping -c 3 172.28.0.1

# 检查端口监听
docker exec "${CONTAINER_NAME}" netstat -tlnp | grep xpra
```

### 9.3 查看 xpra 日志

```bash
docker exec "${CONTAINER_NAME}" ls -la /tmp/sessions/
```

### 9.4 重启特定会话

```bash
LINK_ID=1
DISPLAY_ID=$LINK_ID

# 停止会话
docker exec "${CONTAINER_NAME}" xpra stop ":${DISPLAY_ID}"

# 清理会话文件
docker exec "${CONTAINER_NAME}" rm -rf "/tmp/sessions/link-${LINK_ID}"

# 重新启动（参考前面的启动命令）
```

### 9.5 线程创建错误 (QThread::start: Thread creation error)

**错误信息：**
```
QThread::start: Thread creation error (Resource temporarily unavailable)
```

**原因分析：**
- Docker 容器的 PID 限制（`--pids-limit`）实际限制的是线程数
- 每个 Wireshark 实例需要约 30 个线程
- 默认限制 200 可能不足以支持多个 Wireshark 实例

**解决方案：**

```bash
# 检查当前线程使用情况
docker exec "${CONTAINER_NAME}" bash -c "ps -eLf | wc -l"

# 增加 PID 限制（推荐设置为 1000）
docker update --pids-limit 1000 "${CONTAINER_NAME}"

# 验证新限制
docker inspect "${CONTAINER_NAME}" --format '{{.HostConfig.PidsLimit}}'
```

**预防措施：**
- 启动容器时设置合理的 PID 限制：`--pids-limit 1000`
- 参考"性能指标与资源规划"章节确定合适的配置

### 9.6 XDG_RUNTIME_DIR 警告

**警告信息：**
```
Warning: XDG_RUNTIME_DIR is not defined
 and '/run/user/1000' does not exist
 using '/tmp'
```

**说明：**
- 这是警告而非错误，Xpra 会回退使用 `/tmp`
- 可能影响某些依赖 XDG 规范的功能

**解决方案：**
确保使用最新的 Docker 镜像，已包含以下修复：
- 创建 `/run/user/1000` 目录
- 设置 `XDG_RUNTIME_DIR` 环境变量

如需手动修复：
```bash
docker exec "${CONTAINER_NAME}" mkdir -p /run/user/1000
docker exec "${CONTAINER_NAME}" bash -c "export XDG_RUNTIME_DIR=/run/user/1000"
```
