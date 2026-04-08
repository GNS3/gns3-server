# Web Wireshark 集成

## 概述

将 Wireshark 数据包捕获功能集成到 GNS3 Web UI 中，允许用户通过 noVNC 在浏览器中直接查看实时捕获数据。

## 安装

```bash
# 拉取 Docker 镜像（独立操作）
docker pull ghcr.io/gns3/web-wireshark:latest
```

**模块位置:** `gns3server/compute/web_wireshark/`

**注意：** 此功能是 gns3server 核心的一部分，无需额外的 Python 依赖包。

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         浏览器                                  │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  GNS3 Web UI                                             │  │
│   │  - 在链路上点击"开始捕获"                                 │  │
│   │  - "在 Wireshark 中查看"打开 noVNC iframe              │  │
│   │  - 通过 WebSocket接收"就绪"事件                         │  │
│   └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ WebSocket (ws://gns3-server:3080)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       GNS3 Server (端口 3080)                   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  WiresharkSessionManager                                 │   │
│  │  - DisplayManager: 跟踪每个容器的显示器 (:0-:50)         │   │
│  │  - 会话状态: pending → starting → ready → error        │   │
│  │  - ProjectContainerManager: 项目容器生命周期               │   │
│  │  - Docker API: 直接容器/会话管理                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Wireshark 容器 (项目级)                      │   │
│  │  gns3-ws-{project_id}                                    │   │
│  │  - 项目打开时创建                                         │   │
│  │  - 项目关闭时销毁                                         │   │
│  │  - 包含多个 Wireshark 会话 (每链路一个)                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  容器内: xpra + noVNC 服务器 (端口 10000)                  │   │
│  │  - 会话目录: /tmp/sessions/link-{uuid}/                   │   │
│  │    - token: 用于 capture/stream API 的 JWT                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Linux 用户隔离 (每链路一个用户)                          │   │
│  │  link-{uuid-1} ──▶ Xvfb :0 ──▶ wireshark                │   │
│  │  link-{uuid-2} ──▶ Xvfb :1 ──▶ wireshark                │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP (token 通过文件)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        GNS3 Server                              │
│  捕获文件存储: /path/to/projects/{id}/captures/                 │
│  流 API: GET /v3/links/{link_id}/capture/stream                │
└─────────────────────────────────────────────────────────────────┘
```

## 设计原则

- **分布式架构** - 使用 GNS3 现有的 Docker 管理模式
- **项目级容器隔离** - 每个项目一个容器
- **按需创建 Wireshark 会话** - 仅在用户点击"在 Wireshark 中查看"时创建
- **Docker API 直接管理** - 无需 Ansible 或 SSH
- **浏览器仅连接到 GNS3 Server** - WebSocket 代理处理转发
- **安全的 token 处理** - JWT token 存储在会话文件中，不通过 CLI

## 容器生命周期

```
┌──────────────────────────────────────────────────────────────────────────┐
│  项目打开 ──▶ 容器启动 ──▶ 容器运行                                      │
│  项目关闭 ──▶ 容器停止                                                   │
│                                                                          │
│  容器内:                                                                 │
│  会话请求 ──▶ 会话启动 ──▶ 会话就绪                                      │
│  会话关闭 ──▶ 会话清理                                                   │
└──────────────────────────────────────────────────────────────────────────┘
```

## 会话状态机

```
[idle] ──▶ [pending] ──▶ [starting] ──▶ [ready] ──▶ [closing] ──▶ [idle]
                │                │                │
                ▼                ▼                ▼
            用户点击       Docker exec       用户查看
            查看Wireshark  (5-10秒)        Wireshark

[idle] ──▶ [error]  (如果 Docker 操作失败)
```

## 数据流

### 1. 项目打开
```
项目打开 → Docker API 创建容器 → 容器启动 xpra
```

### 2. 开始捕获
```
POST /v3/links/{link_id}/capture/start
  Body: { "wireshark": true }
→ 开始数据包捕获（现有行为）
→ 响应包含 wireshark_ws 端点
```

### 3. 在 Wireshark 中查看
```
用户点击"在 Wireshark 中查看"
  │
  └─▶ WebSocket /v3/links/{link_id}/capture/wireshark
      │
      ▼
  GNS3 Server:
  - 通过 Docker API 检查/创建容器
  - 分配显示器 :N (DisplayManager)
  - 创建会话状态: pending
  - Docker exec: 创建用户、写入 token、启动 xpra/wireshark
      │
      ▼
  WebSocket 发送: {"type": "ready", "display": ":0"}
```

### 4. 前端连接
```
浏览器收到"ready" → 通过 GNS3 Server 代理连接 noVNC 到 xpra
```

### 5. 停止查看 / 项目关闭
```
停止查看: Docker exec 清理 → 释放显示器 → 容器保持运行
项目关闭: 清理所有会话 → docker stop + rm 容器
```

## 核心组件

### DisplayManager
- 管理每个容器的 X 显示器分配 (:0 到 :10)
- 每个 Wireshark 会话使用一个显示器

### ProjectContainerManager
- 通过 Docker API 创建/销毁容器
- 每个项目一个容器
- 跟踪容器状态和 IP

### WiresharkSessionManager
- 通过 Docker exec 创建/关闭会话
- 跟踪每个链路的状态
- 与 DisplayManager 协调

### WebSocket 处理器
- 验证 JWT token
- 发送状态消息 (waiting/ready/error)
- 将浏览器代理到 xpra WebSocket

## 安全

| 关注点 | 缓解措施 |
|--------|----------|
| CLI 中的 JWT token | Token 存储在会话文件中，权限 0600 |
| `ps aux` 中的 token 可见性 | Token 文件仅对会话用户可读 |
| 浏览器直接访问容器 | 所有访问通过 GNS3 Server WebSocket 代理 |
| 未授权的 WebSocket | JWT 验证 + 链路所有权检查 |
| 资源滥用 | cgroups 限制内存（2GB）和进程数（50） |
| SSH 密钥管理 | 不需要 - 使用 Docker API |

### 信任模型
```
浏览器 ──▶ GNS3 Server (JWT 验证) ──▶ Wireshark 容器
              所有流量通过 GNS3 Server 代理
```

## 分布式架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    GNS3 Controller                              │
│         WiresharkSessionManager (协调)                          │
└─────────────────────────────────────────────────────────────────┘
                    │
                    │ HTTP API
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
┌─────────┐   ┌─────────┐   ┌─────────┐
│Compute 1│   │Compute 2│   │Compute 3│
│ Docker  │   │ Docker  │   │ Docker  │
│ Manager │   │ Manager │   │ Manager │
└─────────┘   └─────────┘   └─────────┘
```

每个计算节点:
- 运行自己的 gns3-server 实例
- 有本地 `/var/run/docker.sock` 访问
- 通过 Docker API 管理 Wireshark 容器

## Wireshark 容器

### Dockerfile
```dockerfile
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y wireshark xpra xvfb curl python3
RUN mkdir -p /tmp/sessions && chmod 1777 /tmp/sessions
COPY start.sh /start.sh
EXPOSE 10000
CMD ["/start.sh"]
```

### start.sh
```bash
#!/bin/bash
xpra start :0 --html=on --bind-tcp=0.0.0.0:10000 --auth=allow --daemonize
tail -f /dev/null
```

### 容器结构
```
/
├── tmp/sessions/link-{uuid}/token   # JWT (0600)
├── usr/bin/wireshark
├── usr/bin/xpra
└── usr/bin/xvfb-run
```

## 本地开发与测试

### 本地构建容器
```bash
cd gns3server/compute/web_wireshark/
docker build -t gns3/web-wireshark:local .
```

### 测试容器
```bash
# 运行容器
docker run -d --name ws-test \
  -p 10000:10000 \
  gns3/web-wireshark:local

# 验证 xpra 运行状态
docker exec ws-test ps aux | grep xpra

# 测试 WebSocket 端点
curl -s http://localhost:10000
```

### 推送到仓库（准备就绪后）
```bash
# 为 GitHub Container Registry 打标签
docker tag gns3/web-wireshark:local ghcr.io/gns3/web-wireshark:latest

# 推送
docker push ghcr.io/gns3/web-wireshark:latest
```

## 前端集成指南

### 0. 检查系统能力（可选）

显示 Wireshark 选项前，检查系统是否具备所需组件：

```javascript
// GET /v3/capabilities/web-wireshark
// 响应:
{
  "available": true,
  "docker": true,
  "wireshark": true,
  "xpra": true,
  "xvfb": true,
  "missing": []
}

// 如果 available 为 false，则隐藏 Wireshark UI 选项
```

### 1. 启用 Wireshark 捕获

```javascript
// POST /v3/projects/{project_id}/links/{link_id}/capture/start
{
  "wireshark": true
}
```

**响应包含 `wireshark` 字段:**
```json
{
  "link_id": "xxx",
  "capturing": true,
  "wireshark": true
}
```

### 2. UI 需求

#### 显示"在 Wireshark 中查看"按钮条件：
- 系统具备 Wireshark 能力（来自步骤 0）
- `link.capturing === true`
- `link.wireshark === true`

#### 按钮行为：
- 在链路上下文菜单或工具栏中显示
- 点击后打开 noVNC iframe 或模态框

### 3. WebSocket 连接

**端点:**
```
ws://gns3-server:3080/v3/projects/{project_id}/links/{link_id}/capture/wireshark?token={jwt_token}
```

**认证:** 通过查询参数传递 JWT token（与其他 GNS3 WebSocket 端点相同）

### 4. WebSocket 协议

#### 服务器 → 客户端消息:

**等待（会话启动中）:**
```json
{"type": "waiting", "message": "正在启动 Wireshark..."}
```

**就绪（Wireshark 已运行）:**
```json
{
  "type": "ready",
  "display": ":0",
  "display": ":0"
}
```

**错误:**
```json
{"type": "error", "message": "启动 Wireshark 失败"}
```

### 5. noVNC 集成

收到 `{"type": "ready"}` 后：

1. 连接到 GNS3 Server WebSocket 端点
2. 使用相同的 WebSocket 连接进行 noVNC RFB 协议通信
3. 在 iframe 或模态框中显示

#### 通过代理连接 noVNC:
```javascript
// noVNC 通过 GNS3 Server 代理连接
const vncUrl = `ws://gns3-server:3080/v3/projects/${project_id}/links/${link_id}/capture/wireshark/vnc?token=${jwtToken}`;

// 使用 noVNC 的 RFB 协议连接
const rfb = new RFB(vncUrl, 'Wireshark', { credentials: { password: '' } });
```

### 6. 完整流程

```
1. 用户点击"开始捕获"并启用 Wireshark
   └── POST /capture/start {wireshark: true}

2. 用户点击"在 Wireshark 中查看"
   └── 打开 WebSocket /capture/wireshark?token=...

3. WebSocket 收到:
   └── {type: "waiting", message: "..."}
       └── 显示"启动中..."UI

4. WebSocket 收到:
   └── {type: "ready", display: ":0"}
       └── 浏览器使用相同 WebSocket 进行 VNC 协议通信
       └── 在浏览器中显示 Wireshark

5. 用户关闭/停止查看
   └── WebSocket 断开
   └── 服务器停止 Wireshark 会话
```

### 7. noVNC 库

使用 [noVNC](https://github.com/novnc/noVNC) - 通过 GNS3 Server 代理端点连接到 xpra WebSocket。

## API 参考

### 1. 检查系统能力

检查系统是否支持 Web Wireshark 功能。

```http
GET /v3/capabilities/web-wireshark
```

**请求：**
```
无需请求体
```

**响应 (200 OK)：**
```json
{
  "available": true,
  "docker": true,
  "wireshark": true,
  "xpra": true,
  "xvfb": true,
  "missing": []
}
```

| 字段 | 类型 | 描述 |
|------|------|------|
| available | boolean | 所有必需组件都已安装 |
| docker | boolean | Docker 守护进程可访问 |
| wireshark | boolean | Wireshark CLI 已安装 |
| xpra | boolean | Xpra 已安装 |
| xvfb | boolean | Xvfb 已安装 |
| missing | string[] | 缺失的组件名称列表 |

**错误响应 (401 未授权)：**
```json
{"detail": "Not authenticated"}
```

---

### 2. 启用 Wireshark 的开始捕获

开始数据包捕获并启用 Wireshark 集成。

```http
POST /v3/projects/{project_id}/links/{link_id}/capture/start
```

**请求体：**
```json
{
  "data_link_type": "DLT_C_HDLC",
  "capture_file_name": "capture_001",
  "wireshark": true
}
```

| 字段 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| data_link_type | string | 否 | "DLT_EN10MB" | 捕获的数据链路类型 |
| capture_file_name | string | 否 | 自动生成 | 捕获文件名 |
| wireshark | boolean | 否 | false | 启用 Wireshark 集成 |

**响应 (201 Created)：**
```json
{
  "link_id": "582524e6-c7be-4c0b-9921-77e25a344752",
  "project_id": "5af0fe00-f39d-4985-8669-7e8c512d729c",
  "capturing": true,
  "wireshark": true,
  "capture_file_name": "capture_001",
  "capture_file_path": "/path/to/projects/5af0fe00/captures/capture_001",
  "link_type": "ethernet",
  "nodes": [...]
}
```

**错误响应：**
- 401 Unauthorized: 未认证
- 404 Not Found: 项目或链路不存在
- 403 Forbidden: 权限不足

---

### 3. 停止捕获

停止数据包捕获（自动禁用 Wireshark）。

```http
POST /v3/projects/{project_id}/links/{link_id}/capture/stop
```

**请求：**
```
无需请求体
```

**响应 (204 No Content)：**
```
空响应体
```

---

### 4. WebSocket - 在 Wireshark 中查看

打开 WebSocket 连接，在浏览器中查看 Wireshark。

```http
ws://gns3-server:3080/v3/projects/{project_id}/links/{link_id}/capture/wireshark?token={jwt_token}
```

**认证：** 通过查询参数传递 JWT token

#### 服务器 → 客户端消息：

**步骤 1：等待（会话启动中）**
```json
{"type": "waiting", "message": "正在启动 Wireshark..."}
```

**步骤 2：就绪（Wireshark 已运行）**
```json
{
  "type": "ready",
  "display": ":0",
  "display": ":0"
}
```

| 字段 | 类型 | 描述 |
|------|------|------|
| type | string | 消息类型："waiting", "ready", "error" |
| display | string | X 显示编号（如 ":0"） |
| display | string | X 显示编号（如 ":0"） |
| message | string | 人类可读的状态消息 |
| error | string | 错误详情（仅在 error 类型时存在） |

**步骤 3：错误（如果发生故障）**
```json
{
  "type": "error",
  "message": "Wireshark 不可用：缺少 wireshark"
}
```

**WebSocket 关闭码：**
- 1008: 链路未找到或未开始捕获
- 1011: 服务器内部错误

---

### 5. noVNC 集成

浏览器连接到同一个 WebSocket 端点。GNS3 Server 代理连接到容器的 xpra。

```javascript
// 连接到 GNS3 Server WebSocket（与查看捕获相同的端点）
const ws = new WebSocket(
  `ws://gns3-server:3080/v3/projects/${projectId}/links/${linkId}/capture/wireshark?token=${jwtToken}`
);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === 'waiting') {
    // 显示"启动中..."UI
  }

  if (msg.type === 'ready') {
    // msg.display 包含 X 显示编号
    // WebSocket 现在已代理到 xpra - 与 noVNC 一起使用
    const rfb = new RFB(ws, 'Wireshark');
    rfb.connect();
  }
};
```

## 实现状态

| 组件 | 状态 | 备注 |
|------|------|------|
| ProjectContainerManager | ✅ 完成 | Docker API 容器生命周期 |
| DisplayManager | ✅ 完成 | 每容器显示器分配 |
| WiresharkSessionManager | ✅ 完成 | 会话状态机 + Docker exec |
| WebSocket 处理器 | ✅ 完成 | 带状态协议的 FastAPI WebSocket |
| Dockerfile + start.sh | ✅ 完成 | 容器镜像 |
| 链路 API 修改 | ✅ 完成 | 在 start/stop 中添加 wireshark=true |
| 前端集成 | 📄 文档已提供 | 见"前端集成指南"章节 |

## 故障排除

| 问题 | 诊断 | 解决方案 |
|------|------|----------|
| WebSocket 4001 | JWT 无效 | 刷新 token |
| WebSocket 4004 | 未找到会话 | 先点击"在 Wireshark 中查看" |
| "waiting" 一直不变 | Docker exec 卡住 | 检查 Docker 日志 |
| "error" 消息 | 会话创建失败 | 验证容器可达 |
| 黑屏 | Wireshark 未启动 | 检查容器内进程 |
| 未找到容器 | 项目容器未创建 | 检查项目是否打开 |
| 没有可用端口 | 所有端口（10000-10099）都被占用 | 减少并发项目数 |

## 限制

- **并发项目数：** 最多 100 个项目同时使用 Wireshark（端口 10000-10099）
- **每项目会话数：** 每个项目最多 51 个并发 Wireshark 会话（display 0-50）

## 未来增强

1. **会话恢复** - 在 GNS3 Server 重启后持久化会话状态
2. **多查看器** - 允许多个浏览器查看同一会话（只读）
3. **会话录制** - 保存 Wireshark 交互以供回放
4. **资源监控** - 跟踪和限制 Wireshark 资源使用
