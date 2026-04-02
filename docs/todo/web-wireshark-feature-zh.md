# Web Wireshark 集成

## 概述

将 Wireshark 数据包捕获功能集成到 GNS3 Web UI 中，允许用户通过 noVNC 在浏览器中直接查看实时捕获数据。

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         浏览器                                   │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  GNS3 Web UI                                            │  │
│   │  - 在链路上点击"开始捕获"                               │  │
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
│  │  - DisplayManager: 追踪每个容器的显示器 (:0-:10)         │   │
│  │  - Session状态: pending → starting → ready → error       │   │
│  │  - ProjectContainerManager: project容器生命周期管理       │   │
│  │  - AnsibleRunner: 异步触发 Ansible playbook              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │ WebSocket                        │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Wireshark 容器 (Project 级)                 │   │
│  │  gns3-ws-{project_id}                                    │   │
│  │  - 项目打开时创建                                        │   │
│  │  - 项目关闭时销毁                                        │   │
│  │  - 包含多个 Wireshark 会话 (每个链路一个)                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  容器内部: xpra + noVNC Server (端口 10000)              │   │
│  │  - Session目录: /tmp/sessions/link-{uuid}/               │   │
│  │    - token: 用于 capture/stream API 的 JWT token         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Linux 用户隔离 (每个 link_id 一个用户)                   │   │
│  │                                                           │   │
│  │  link-{uuid-1} ──▶ Xvfb :0 ──▶ wireshark              │   │
│  │  link-{uuid-2} ──▶ Xvfb :1 ──▶ wireshark              │   │
│  │  link-{uuid-3} ──▶ Xvfb :2 ──▶ wireshark              │   │
│  │                                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  cgroups 资源限制 (按用户)                                │   │
│  │  - 内存: 2GB  | 进程数: 50  | CPU Shares: 10%            │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP (token 通过文件传递, 不在 CLI)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        GNS3 Server                              │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  捕获文件存储 (Project 级持久化)                          │   │
│  │  /path/to/projects/{project_id}/project-files/captures/ │   │
│  │      └── {link_capture_file}.pcap                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│              GET /v3/links/{link_id}/capture/stream            │
│              (Authorization: Bearer {user_jwt})                │
└─────────────────────────────────────────────────────────────────┘
```

## 设计原则

- **Project 级容器隔离** - 每个 project 一个容器，生命周期与 project 绑定
- **按需创建 Wireshark 会话** - 只有用户点击"View in Wireshark"时才创建会话
- **不独立开发 wireshark API** - 复用现有的 capture API 端点
- **Ansible 驱动的容器和会话管理** - 容器生命周期和 Wireshark 会话由 Ansible playbooks 处理
- **浏览器只连接 GNS3 Server** - WebSocket 代理负责转发到 Wireshark 容器
- **基于 HTTP 的数据传递** - Wireshark 通过 HTTP 获取 pcap 流，使用 token 文件（非 CLI 参数）
- **状态驱动的会话生命周期** - 前端通过 WebSocket 接收实时会话状态
- **安全的 token 处理** - JWT token 存储在会话文件中，不作为进程参数
- **统一认证** - GNS3 Server 的 JWT 是唯一认证机制；xpra 信任代理网关
- **容器是无状态的** - 容器只提供 GUI 显示，数据存储在项目目录

## 容器生命周期

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    Project 级容器生命周期                                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  [project.opened] ──▶ [container.start] ──▶ [container.running]       │
│                                                          │               │
│  [project.closed] ──▶ [container.stop] ──▶ [container.stopped]         │
│                                                                          │
│  容器内的 Wireshark 会话:                                               │
│  [session.requested] ──▶ [session.starting] ──▶ [session.ready]        │
│                                                                │         │
│  [session.closed] or [project.closed] ──▶ [session.cleanup]            │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## 会话生命周期

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           会话状态机                                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  [idle] ──▶ [pending] ──▶ [starting] ──▶ [ready] ──▶ [closing] ──▶ [idle]
│                │                │                │                │
│                │                │                │                │
│                ▼                ▼                ▼                ▼
│            用户点击        Ansible 运行      用户查看         停止捕获
│            查看Wireshark  (5-10秒)         Wireshark        或超时
│                                                                          │
│  [idle] ──▶ [error]  (如果 Ansible 失败)                                │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘

状态持久化:
- 会话状态是临时的 (GNS3 Server 重启后丢失)
- 重启后，用户必须重新点击查看 Wireshark 才能恢复
- 容器状态持久化 (在同一 project 内会话重启后仍存活)
- 捕获数据在项目目录中持久化 (所有重启后仍保留)
```

## 数据流

### 1. Project 打开 (容器创建)

```
Project 在 GNS3 中打开
   │
   └─▶ WiresharkSessionManager 检测到 project 打开
       │
       ▼
   Ansible: docker run wireshark-container-{project_id}
       │
       ▼
   容器启动，xpra 运行
   容器现在可以为 Wireshark 会话提供服务
```

### 2. 开始捕获

```
用户在 GNS3 Web UI 中点击"开始捕获"(启用 Wireshark)
   │
   └─▶ POST /v3/links/{link_id}/capture/start
       Header: Authorization: Bearer {user_jwt}
       Body: { "wireshark": true }
       │
       ▼
   GNS3 Server:
   a. 开始数据包捕获 (现有行为，数据保存到项目目录)
   b. 响应包含 wireshark_ws 端点
```

### 3. 查看 Wireshark (按需创建会话)

```
用户点击"View in Wireshark"(需要 Wireshark 视图)
   │
   └─▶ WebSocket /v3/links/{link_id}/capture/wireshark
       Header: Authorization: Bearer {user_jwt}
       │
       ▼
   GNS3 Server:
   WiresharkSessionManager:
      - 检查项目的容器是否存在
      - 如果不存在，通过 Ansible 创建容器 (随 project 启动)
      - 通过 DisplayManager 分配显示器 :N (每容器范围 :0-:10)
      - 创建会话状态: pending
      - 触发 Ansible playbook (异步) 创建 wireshark 会话
       │
       ▼
   Response (通过 WebSocket 立即返回):
   {
     "type": "waiting",
     "message": "正在启动 Wireshark..."
   }
       │
       ▼
   Ansible 在容器内执行 (5-10秒):
   - 创建 Linux 用户 link-{uuid}
   - 创建会话目录 /tmp/sessions/link-{uuid}/
   - 将 JWT token 写入 /tmp/sessions/link-{uuid}/token (mode 0600)
   - 启动 xpra 会话 (如果该显示器上尚未运行)
   - 启动 wireshark 消费 capture/stream API (从文件读取 token)
   - 更新会话状态为: ready
       │
       ▼
   WebSocket 发送:
   {
     "type": "ready",
     "display": ":0",
     "xpra_ws": "ws://wireshark-container:10000"
   }
```

### 4. 前端 WebSocket 连接

```
前端在收到"ready"消息后连接 WebSocket:
   ws://gns3-server:3080/v3/links/{link_id}/capture/wireshark
   Header: Authorization: Bearer {user_jwt}

   │
   ├─▶ GNS3 Server 验证 JWT token
   │
   ├─▶ 检查会话状态:
   │      - [pending/starting]: 发送 {"type": "waiting", "message": "Starting..."}
   │      - [ready]: 发送 {"type": "ready", "display": ":0", "xpra_ws": "..."}
   │      - [error]: 发送 {"type": "error", "message": "..."}
   │
   └─▶ 如果会话状态为 [ready]:
       - 将 WebSocket 代理到 Wireshark 容器 xpra :10000
       - 无需 xpra 认证 (GNS3 Server 是可信网关)
       - noVNC iframe 通过代理连接到 xpra WebSocket
```

### 5. 停止 Wireshark 视图

```
用户点击"停止 Wireshark 视图"(关闭 Wireshark 窗口)
   │
   └─▶ POST /v3/links/{link_id}/capture/wireshark/stop
       │
       ▼
   GNS3 Server:
   WiresharkSessionManager:
      - 触发 Ansible playbook (异步) 清理会话
      - 将显示器释放回 DisplayManager
      - 设置会话状态: closing → idle
      - 容器保持运行 (为同一项目中的其他链路服务)
```

### 6. Project 关闭 (容器销毁)

```
Project 在 GNS3 中关闭
   │
   └─▶ WiresharkSessionManager 检测到 project 关闭
       │
       ▼
   对于此项目中的每个活动 Wireshark 会话:
      - Ansible: 清理会话 (用户、进程、cgroups)
       │
       ▼
   Ansible: docker stop + docker rm wireshark-container-{project_id}
       │
       ▼
   所有会话已清理，容器已销毁
   捕获数据保留在项目目录中 (持久化)
```

### 7. 异常断开连接

```
用户关闭浏览器 (noVNC WebSocket 断开)
   │
   ▼
WebSocket 处理器检测到断开 (finally 块)
   │
   ├─▶ 如果 link.capturing == true:
   │      - 会话保持运行 (捕获继续，数据已保存)
   │      - 显示器保持分配
   │      - 用户可以通过新的 WebSocket 连接重连
   │
   └─▶ 如果 link.capturing == false:
          - 立即触发清理
          - 释放显示器

心跳机制:
   - WebSocket 代理每 10 秒发送 ping
   - 如果 30 秒内没有收到 pong，则判定为断开
   - 超时后: 如果不在捕获状态则清理，否则保持会话
```

## DisplayManager

管理单个容器内 X 显示器的分配。

```python
# gns3server/compute/display_manager.py

import asyncio
import logging

log = logging.getLogger(__name__)


class DisplayManager:
    """
    为 Wireshark 会话管理 X 显示器号分配。

    每个容器都有自己的 DisplayManager，范围 :0 到 :10。
    会话结束时必须释放显示器。
    """

    def __init__(self, start: int = 0, max_displays: int = 10):
        self._start = start
        self._max = start + max_displays
        self._allocated: dict[int, str] = {}  # display -> link_id
        self._lock = asyncio.Lock()

    async def allocate(self, link_id: str) -> str:
        """
        为链路分配显示器号。

        :param link_id: 请求显示器的链路 ID
        :returns: 显示器字符串 (例如 ":0")
        :raises RuntimeError: 如果没有可用显示器
        """
        async with self._lock:
            for display in range(self._start, self._max):
                if display not in self._allocated:
                    self._allocated[display] = link_id
                    display_str = f":{display}"
                    log.info(f"为链路 {link_id} 分配了显示器 {display_str}")
                    return display_str

            raise RuntimeError(f"显示器范围 :{self._start}-:{self._max - 1} 内没有可用显示器")

    async def release(self, display: str) -> None:
        """
        释放显示器号。

        :param display: 显示器字符串 (例如 ":0")
        """
        if not display or len(display) < 2:
            return

        display_num = int(display[1:])
        async with self._lock:
            if display_num in self._allocated:
                link_id = self._allocated.pop(display_num)
                log.info(f"从链路 {link_id} 释放了显示器 {display}")

    async def get_display_link_id(self, display: str) -> str | None:
        """
        获取使用特定显示器的链路 ID。

        :param display: 显示器字符串 (例如 ":0")
        :returns: 链路 ID 或 None (如果未找到)
        """
        if not display or len(display) < 2:
            return None
        display_num = int(display[1:])
        async with self._lock:
            return self._allocated.get(display_num)

    def get_allocated_count(self) -> int:
        """返回当前已分配的显示器数量。"""
        return len(self._allocated)
```

## ProjectContainerManager

管理每个 project 的 Wireshark 容器生命周期。

```python
# gns3server/compute/project_container_manager.py

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class ProjectContainer:
    """表示项目的 Wireshark 容器。"""
    project_id: str
    container_id: str
    container_ip: str
    display_manager: 'DisplayManager'
    state: str = "running"  # starting, running, stopping, stopped


class ProjectContainerManager:
    """
    管理基于每个 project 的 Wireshark 容器。

    职责:
    - 项目打开时创建容器
    - 项目关闭时销毁容器
    - 追踪容器状态和 IP
    - 为每个容器提供 DisplayManager
    """

    def __init__(self, container_image: str = "gns3/wireshark-server:latest"):
        self._containers: dict[str, ProjectContainer] = {}  # project_id -> container
        self._container_image = container_image
        self._lock = asyncio.Lock()
        self._ansible_inventory = "/etc/ansible/hosts"
        self._ansible_playbooks_dir = "/etc/ansible/playbooks"

    async def on_project_opened(self, project_id: str) -> ProjectContainer:
        """
        当项目打开时调用。
        为项目创建 Wireshark 容器。
        """
        async with self._lock:
            if project_id in self._containers:
                return self._containers[project_id]

            container = await self._create_container(project_id)
            self._containers[project_id] = container
            log.info(f"为项目 {project_id} 创建了 Wireshark 容器")
            return container

    async def on_project_closed(self, project_id: str) -> None:
        """
        当项目关闭时调用。
        销毁项目的 Wireshark 容器。
        """
        async with self._lock:
            if project_id not in self._containers:
                return

            container = self._containers.pop(project_id)
            await self._destroy_container(container)
            log.info(f"销毁了项目 {project_id} 的 Wireshark 容器")

    async def get_container(self, project_id: str) -> Optional[ProjectContainer]:
        """获取项目的容器，如果未运行则返回 None。"""
        return self._containers.get(project_id)

    async def _create_container(self, project_id: str) -> ProjectContainer:
        """通过 Ansible 创建新的 Wireshark 容器。"""
        # 运行 Ansible playbook 创建和启动容器
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                [
                    "ansible-playbook",
                    f"{self._ansible_playbooks_dir}/wireshark_container_create.yml",
                    "-e", json.dumps({"project_id": project_id}),
                    "-i", self._ansible_inventory,
                ],
                capture_output=True,
                text=True,
                timeout=120,
            ),
        )

        if result.returncode != 0:
            raise RuntimeError(f"创建容器失败: {result.stderr}")

        # 获取容器 IP
        container_ip = await self._get_container_ip(project_id)

        return ProjectContainer(
            project_id=project_id,
            container_id=f"gns3-ws-{project_id}",
            container_ip=container_ip,
            display_manager=DisplayManager(start=0, max_displays=10),
            state="running"
        )

    async def _destroy_container(self, container: ProjectContainer) -> None:
        """通过 Ansible 销毁容器。"""
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                [
                    "ansible-playbook",
                    f"{self._ansible_playbooks_dir}/wireshark_container_delete.yml",
                    "-e", json.dumps({"project_id": container.project_id}),
                    "-i", self._ansible_inventory,
                ],
                capture_output=True,
                text=True,
                timeout=60,
            ),
        )

    async def _get_container_ip(self, project_id: str) -> str:
        """通过 Ansible 获取容器 IP。"""
        # 查询容器 IP 的实现
        pass
```

## WiresharkSessionManager

在 GNS3 Server 端管理 Wireshark 会话生命周期。

```python
# gns3server/compute/wireshark_session_manager.py

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import aiohttp

log = logging.getLogger(__name__)


class SessionState(Enum):
    IDLE = "idle"
    PENDING = "pending"
    STARTING = "starting"
    READY = "ready"
    CLOSING = "closing"
    ERROR = "error"


@dataclass
class WiresharkSession:
    """表示链路的 Wireshark 查看会话。"""

    link_id: str
    project_id: str
    display: str
    state: SessionState = SessionState.PENDING
    error_message: str = ""
    ansible_task: Optional[asyncio.Task] = None
    created_at: float = field(default_factory=asyncio.get_event_loop().time)


class WiresharkSessionManager:
    """
    管理数据包捕获链路的 Wireshark 会话。

    职责:
    - 与 ProjectContainerManager 协调容器生命周期
    - 通过 ProjectContainer 的 DisplayManager 分配显示器
    - 触发 Ansible playbooks 进行会话创建/清理
    - 追踪会话状态
    - 为 WebSocket 处理器提供会话信息
    """

    def __init__(self, container_host: str = "wireshark-container"):
        self._sessions: dict[str, WiresharkSession] = {}  # link_id -> session
        self._project_containers: ProjectContainerManager = ProjectContainerManager()
        self._container_host = container_host
        self._lock = asyncio.Lock()
        self._ansible_inventory = "/etc/ansible/hosts"
        self._ansible_playbooks_dir = "/etc/ansible/playbooks"

    async def on_project_opened(self, project_id: str) -> None:
        """当项目打开时调用。创建 Wireshark 容器。"""
        await self._project_containers.on_project_opened(project_id)

    async def on_project_closed(self, project_id: str) -> None:
        """当项目关闭时调用。销毁 Wireshark 容器。"""
        # 清理此项目的所有会话
        sessions_to_close = [
            link_id for link_id, session in self._sessions.items()
            if session.project_id == project_id
        ]
        for link_id in sessions_to_close:
            await self.close_session(link_id)

        await self._project_containers.on_project_closed(project_id)

    async def create_session(self, link_id: str, project_id: str, user_token: str) -> WiresharkSession:
        """
        创建新的 Wireshark 会话。

        :param link_id: 要创建会话的链路 ID
        :param project_id: 项目 ID
        :param user_token: 用于 capture/stream 访问的 JWT token
        :returns: WiresharkSession 对象
        """
        async with self._lock:
            # 检查会话是否已存在
            if link_id in self._sessions:
                session = self._sessions[link_id]
                if session.state in (SessionState.PENDING, SessionState.STARTING):
                    return session
                elif session.state == SessionState.READY:
                    return session

            # 获取或创建项目容器
            container = await self._project_containers.get_container(project_id)
            if not container:
                # 项目容器不存在，创建它
                container = await self._project_containers.on_project_opened(project_id)

            # 从容器的 DisplayManager 分配显示器
            display = await container.display_manager.allocate(link_id)

            # 创建会话
            session = WiresharkSession(
                link_id=link_id,
                project_id=project_id,
                display=display,
                state=SessionState.PENDING,
            )
            self._sessions[link_id] = session

            # 异步 Ansible playbook 在容器中创建会话
            session.ansible_task = asyncio.create_task(
                self._run_create_playbook(link_id, project_id, user_token, display)
            )

            asyncio.create_task(self._poll_session_ready(link_id))

            return session

    async def _run_create_playbook(
        self, link_id: str, project_id: str, user_token: str, display: str
    ) -> None:
        """异步运行 Ansible playbook 创建 Wireshark 会话。"""
        try:
            session = self._sessions.get(link_id)
            if not session:
                return

            session.state = SessionState.STARTING

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    [
                        "ansible-playbook",
                        f"{self._ansible_playbooks_dir}/wireshark_session_create.yml",
                        "-e", json.dumps({
                            "link_id": link_id,
                            "project_id": project_id,
                            "user_token": user_token,
                            "display": display,
                        }),
                        "-i", self._ansible_inventory,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                ),
            )

            if result.returncode != 0:
                log.error(f"Ansible 创建失败: {result.stderr}")
                if link_id in self._sessions:
                    self._sessions[link_id].state = SessionState.ERROR
                    self._sessions[link_id].error_message = f"创建失败: {result.stderr}"
            else:
                log.info(f"为链路 {link_id} 创建了 Wireshark 会话")

        except asyncio.TimeoutError:
            log.error(f"Ansible playbook 超时: {link_id}")
            if link_id in self._sessions:
                self._sessions[link_id].state = SessionState.ERROR
                self._sessions[link_id].error_message = "创建超时"
        except Exception as e:
            log.error(f"运行 Ansible playbook 时出错: {e}")
            if link_id in self._sessions:
                self._sessions[link_id].state = SessionState.ERROR
                self._sessions[link_id].error_message = str(e)

    async def _poll_session_ready(self, link_id: str, timeout: float = 30) -> None:
        """轮询会话就绪状态。"""
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < timeout:
            if link_id not in self._sessions:
                return

            session = self._sessions[link_id]
            if session.state == SessionState.READY or session.state == SessionState.ERROR:
                return

            if session.state == SessionState.STARTING and session.ansible_task:
                if session.ansible_task.done():
                    if session.state != SessionState.ERROR:
                        if await self._check_xpra_running(link_id, session.display):
                            session.state = SessionState.READY
                        else:
                            session.state = SessionState.ERROR
                            session.error_message = "会话创建失败"
                    return

            await asyncio.sleep(0.5)

        if link_id in self._sessions:
            self._sessions[link_id].state = SessionState.ERROR
            self._sessions[link_id].error_message = "会话创建超时"

    async def _check_xpra_running(self, link_id: str, display: str) -> bool:
        """通过 Ansible status playbook 检查 xpra 会话是否运行。"""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    [
                        "ansible-playbook",
                        f"{self._ansible_playbooks_dir}/wireshark_session_status.yml",
                        "-e", json.dumps({"link_id": link_id, "display": display}),
                        "-i", self._ansible_inventory,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                ),
            )
            if result.returncode == 0:
                return "status: running" in result.stdout
        except Exception:
            pass
        return False

    async def close_session(self, link_id: str) -> None:
        """关闭 Wireshark 会话。"""
        async with self._lock:
            if link_id not in self._sessions:
                return

            session = self._sessions[link_id]
            session.state = SessionState.CLOSING

        asyncio.create_task(
            self._run_cleanup_playbook(link_id, session.project_id, session.display)
        )

    async def _run_cleanup_playbook(self, link_id: str, project_id: str, display: str) -> None:
        """异步运行 Ansible playbook 清理 Wireshark 会话。"""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    [
                        "ansible-playbook",
                        f"{self._ansible_playbooks_dir}/wireshark_session_cleanup.yml",
                        "-e", json.dumps({"link_id": link_id, "display": display}),
                        "-i", self._ansible_inventory,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                ),
            )

            if result.returncode != 0:
                log.warning(f"Ansible 清理失败 {link_id}: {result.stderr}")

        except Exception as e:
            log.error(f"运行清理 playbook 时出错: {e}")
        finally:
            # 释放显示器
            container = await self._project_containers.get_container(project_id)
            if container:
                await container.display_manager.release(display)

            # 删除会话
            async with self._lock:
                if link_id in self._sessions:
                    del self._sessions[link_id]

    async def get_session(self, link_id: str) -> Optional[WiresharkSession]:
        """通过链路 ID 获取会话。"""
        return self._sessions.get(link_id)

    async def get_session_state(self, link_id: str) -> SessionState:
        """获取链路的会话状态。"""
        session = self._sessions.get(link_id)
        return session.state if session else SessionState.IDLE

    def get_xpra_ws_url(self, session: WiresharkSession) -> str:
        """获取会话的 xpra WebSocket URL。"""
        container = self._project_containers.get_container(session.project_id)
        if container:
            return f"ws://{container.container_ip}:10000"
        return f"ws://{self._container_host}:10000"
```

## WebSocket 处理器

通过基于状态的消息处理浏览器 WebSocket 连接。

```python
# gns3server/api/routes/controller/links.py (添加部分)

import asyncio
import json
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from uuid import UUID

# Wireshark 会话管理器实例
wireshark_session_manager = WiresharkSessionManager()


@router.websocket("/v3/links/{link_id}/capture/wireshark")
async def wireshark_websocket(websocket: WebSocket, link_id: UUID):
    """
    Wireshark 查看的 WebSocket 端点。

    协议:
    1. 客户端在 header 中携带 JWT token 连接
    2. Server 验证 token 和链路所有权
    3. Server 按需创建 Wireshark 会话
    4. Server 发送状态消息:
       - {"type": "waiting", "message": "正在启动 Wireshark..."}
       - {"type": "ready", "display": ":0", "xpra_ws": "ws://..."}
       - {"type": "error", "message": "..."}
    5. 就绪后，双向代理到 xpra WebSocket
    6. 心跳: 每 10 秒 ping，30 秒无响应则断开
    """
    # 1. 验证 JWT token
    token = websocket.headers.get("Authorization", "").replace("Bearer ", "")
    if not await validate_jwt_token(token, str(link_id)):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # 2. 获取链路和项目信息
    link = await get_link_by_id(str(link_id))
    if not link:
        await websocket.close(code=4004, reason="Link not found")
        return

    project_id = link.project.id

    # 3. 按需创建或获取会话
    session = await wireshark_session_manager.create_session(
        str(link_id),
        project_id,
        token
    )

    # 4. 发送当前状态
    if session.state == SessionState.PENDING or session.state == SessionState.STARTING:
        await websocket.send_json({
            "type": "waiting",
            "message": "正在启动 Wireshark，请稍候..."
        })
    elif session.state == SessionState.ERROR:
        await websocket.send_json({
            "type": "error",
            "message": session.error_message
        })
        await websocket.close(code=4002, reason=session.error_message)
        return

    # 5. 如果尚未就绪，则等待 (最多 15 秒)
    if session.state != SessionState.READY:
        for _ in range(30):  # 30 * 0.5s = 15s
            await asyncio.sleep(0.5)
            session = await wireshark_session_manager.get_session(str(link_id))
            if not session:
                await websocket.close(code=4004, reason="Session not found")
                return
            if session.state == SessionState.READY:
                break
            elif session.state == SessionState.ERROR:
                await websocket.send_json({
                    "type": "error",
                    "message": session.error_message
                })
                await websocket.close(code=4002, reason=session.error_message)
                return
        else:
            await websocket.close(code=4003, reason="Session ready timeout")
            return

    # 6. 发送就绪消息
    await websocket.send_json({
        "type": "ready",
        "display": session.display,
        "xpra_ws": wireshark_session_manager.get_xpra_ws_url(session)
    })

    # 7. 启动心跳
    heartbeat_task = asyncio.create_task(_heartbeat_loop(websocket))

    # 8. 代理到 xpra
    try:
        xpra_ws_url = wireshark_session_manager.get_xpra_ws_url(session)
        async with websockets.connect(xpra_ws_url) as xpra_ws:
            proxy_task = asyncio.create_task(_proxy_loop(websocket, xpra_ws))

            done, pending = await asyncio.wait(
                [proxy_task, heartbeat_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    except websockets.WebSocketException as e:
        log.error(f"xpra WebSocket 错误: {e}")
    finally:
        # 检查链路是否仍在捕获
        link = await get_link_by_id(str(link_id))
        if link and not link.capturing:
            await wireshark_session_manager.close_session(str(link_id))


async def _heartbeat_loop(websocket: WebSocket, interval: float = 10, timeout: float = 30):
    """发送 ping，若无 pong 则断开连接。"""
    try:
        while True:
            await asyncio.sleep(interval)
            try:
                await websocket.ping()
                await asyncio.wait_for(websocket.wait_for_pong(), timeout=timeout)
            except asyncio.TimeoutError:
                log.warning("WebSocket 心跳超时")
                break
            except Exception:
                break
    except asyncio.CancelledError:
        pass


async def _proxy_loop(browser_ws: WebSocket, xpra_ws, buffer_size: int = 8192):
    """浏览器和 xpra 之间的双向代理。"""
    async def forward_from_browser():
        try:
            while True:
                data = await browser_ws.receive_bytes()
                await xpra_ws.send(data)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    async def forward_to_browser():
        try:
            while True:
                data = await xpra_ws.recv()
                if isinstance(data, str):
                    await browser_ws.send_text(data)
                else:
                    await browser_ws.send_bytes(data)
        except websockets.WebSocketException:
            pass
        except Exception:
            pass

    await asyncio.gather(
        forward_from_browser(),
        forward_to_browser(),
    )
```

## 捕获流消费

Wireshark 通过 token 文件 (非 CLI) 从 GNS3 Server 的流 API 获取 pcap 数据。

```bash
# 在 Wireshark 容器内，以 link-{uuid} 用户执行
# Token 从文件读取，不作为命令行参数传递

su - link-${LINK_ID} -c 'DISPLAY=${DISPLAY} wireshark \
  -i <(curl -N -H "Authorization: Bearer $(cat /tmp/sessions/link-${LINK_ID}/token)" \
    http://gns3-server:3080/v3/links/${LINK_ID}/capture/stream) &'
```

**相比原始设计的安全改进:**

| 方面 | 原始 (不安全) | 更新后 (安全) |
|--------|---------------------|------------------|
| Token 位置 | CLI 参数 | 会话文件 `/tmp/sessions/link-{uuid}/token` |
| Token 可见性 | `ps aux` 显示 token | Token 只能被用户进程读取 |
| Shell 历史 | Token 在历史记录中 | Token 不在历史记录中 |
| 清理 | 可能留下痕迹 | 会话清理时文件删除 |

## API (扩展现有捕获 API)

### 启用 Wireshark 的开始捕获

```http
POST /v3/links/{link_id}/capture/start

Request:
{
  "wireshark": true   // 可选，启用 wireshark 视图
}

Response (Link 对象 + 新增字段):
{
  "link_id": "xxx",
  "capturing": true,
  "wireshark_ws": "ws://gns3-server:3080/v3/links/{link_id}/capture/wireshark"
}
```

### 停止捕获

```http
POST /v3/links/{link_id}/capture/stop

Request:
{
  "wireshark": true   // 可选，清理 wireshark 会话
}

Response: 204 No Content
```

### Wireshark WebSocket 协议

```http
ws://gns3-server:3080/v3/links/{link_id}/capture/wireshark
Authorization: Bearer {jwt_token}
```

**服务端到客户端消息:**

```json
// 等待会话就绪
{"type": "waiting", "message": "正在启动 Wireshark，请稍候..."}

// 会话就绪
{"type": "ready", "display": ":0", "xpra_ws": "ws://wireshark-container:10000"}

// 会话创建失败
{"type": "error", "message": "启动 Wireshark 失败: Ansible 错误"}
```

**客户端使用示例 (JavaScript):**

```javascript
const ws = new WebSocket(
  `ws://gns3-server:3080/v3/links/${linkId}/capture/wireshark`,
  [],
  { headers: { Authorization: `Bearer ${jwtToken}` } }
);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === 'waiting') {
    showWaitingUI(msg.message);
  } else if (msg.type === 'ready') {
    // 通过 GNS3 Server 代理连接 noVNC 到 xpra (无需密码)
    connectNoVNC(msg.xpra_ws);
  } else if (msg.type === 'error') {
    showErrorUI(msg.message);
    ws.close();
  }
};

function connectNoVNC(xpraWsUrl) {
  // xpra HTML 客户端通过 GNS3 Server WebSocket 代理连接
  // GNS3 Server 已通过 JWT 完成了用户认证
  const rfb = new RFB(document.getElementById('vnc-canvas'), xpraWsUrl);
}
```

## Ansible Playbooks

### Playbook 1: 创建 Wireshark 容器 (Project 级)

**文件:** `wireshark_container_create.yml`

**传递给 Ansible 的变量:**

| 变量 | 描述 |
|----------|-------------|
| `project_id` | 项目 UUID |

```yaml
---
- name: Create Wireshark Container for Project
  hosts: wireshark_hosts
  gather_facts: no
  vars:
    container_name: "gns3-ws-{{ project_id }}"
  tasks:
    - name: Check if container already exists
      shell: docker ps -a --format '{{.Names}}' | grep -x "{{ container_name }}"
      register: container_exists
      ignore_errors: yes

    - name: Create and start container
      shell: |
        docker run -d \
          --name {{ container_name }} \
          --hostname wireshark-{{ project_id[:8] }} \
          --memory=4g \
          --cpus=2 \
          gns3/wireshark-server:latest \
          /start.sh
      when: container_exists.stdout == ""

    - name: Wait for container to be ready
      wait_for:
        port: 10000
        timeout: 30
      when: container_exists.stdout == ""
```

### Playbook 2: 删除 Wireshark 容器 (Project 级)

**文件:** `wireshark_container_delete.yml`

```yaml
---
- name: Delete Wireshark Container for Project
  hosts: wireshark_hosts
  gather_facts: no
  vars:
    container_name: "gns3-ws-{{ project_id }}"
  tasks:
    - name: Stop and remove container
      shell: docker rm -f {{ container_name }} || true
```

### Playbook 3: 创建 Wireshark 会话 (Link 级)

**文件:** `wireshark_session_create.yml`

**传递给 Ansible 的变量:**

| 变量 | 描述 |
|----------|-------------|
| `link_id` | 链路 UUID |
| `project_id` | 项目 UUID |
| `user_token` | 用于 capture/stream 访问的用户 JWT token |
| `display` | 分配的 X 显示器号 (例如 :0) |

```yaml
---
- name: Create Wireshark Session for Link
  hosts: wireshark_hosts
  gather_facts: no
  vars:
    gns3_server: "{{ gns3_server_url | default('http://gns3-server:3080') }}"
    session_dir: "/tmp/sessions/link-{{ link_id }}"
    container_name: "gns3-ws-{{ project_id }}"
  tasks:
    - name: Create session directory
      shell: docker exec {{ container_name }} mkdir -p {{ session_dir }} && \
                       docker exec {{ container_name }} chmod 1777 {{ session_dir }}

    - name: Write JWT token to file (secure, not CLI)
      shell: |
        docker exec {{ container_name }} tee {{ session_dir }}/token > /dev/null <<< "{{ user_token }}"
        docker exec {{ container_name }} chmod 0600 {{ session_dir }}/token

    - name: Create Linux user for link
      shell: docker exec {{ container_name }} useradd -r -s /usr/sbin/nologin link-{{ link_id }} || true

    - name: Create cgroup for resource limits
      shell: |
        docker exec {{ container_name }} sh -c '
          mkdir -p /sys/fs/cgroup/memory/link-{{ link_id }} || true
          mkdir -p /sys/fs/cgroup/pids/link-{{ link_id }} || true
          echo 2147483648 > /sys/fs/cgroup/memory/link-{{ link_id }}/memory.limit_in_bytes || true
          echo 50 > /sys/fs/cgroup/pids/link-{{ link_id }}/pids.max || true
        '

    - name: Start xpra session (no local auth - GNS3 Server is trusted gateway)
      shell: |
        docker exec -d {{ container_name }} bash -c '
          su - link-{{ link_id }} -s /bin/bash -c "DISPLAY={{ display }} xpra start {{ display }}
            --html=on
            --bind-tcp=0.0.0.0:10000
            --auth=allow
            --socket-permissions=0700
            --dpi=96" || true
        '

    - name: Wait for xpra to be ready
      wait_for:
        port: 10000
        timeout: 10

    - name: Start wireshark (token read from file, not CLI)
      shell: |
        docker exec -d {{ container_name }} bash -c '
          TOKEN_FILE={{ session_dir }}/token
          su - link-{{ link_id }} -s /bin/bash -c "DISPLAY={{ display }} bash -c \x27
            while [ ! -f $TOKEN_FILE ]; do sleep 0.5; done
            wireshark -i <(curl -N -H \"Authorization: Bearer \$(cat $TOKEN_FILE)\" \
              {{ gns3_server }}/v3/links/{{ link_id }}/capture/stream) \
              -o \"gui.window_title:Link:{{ link_id}}\" &
          \x27"
        '
```

### Playbook 4: 清理 Wireshark 会话 (Link 级)

**文件:** `wireshark_session_cleanup.yml`

```yaml
---
- name: Cleanup Wireshark Session
  hosts: wireshark_hosts
  gather_facts: no
  vars:
    session_dir: "/tmp/sessions/link-{{ link_id }}"
    container_name: "gns3-ws-{{ project_id }}"
  tasks:
    - name: Stop wireshark process
      shell: docker exec {{ container_name }} pkill -9 -u "link-{{ link_id }}" wireshark || true

    - name: Stop xpra session
      shell: docker exec {{ container_name }} su - link-{{ link_id }} -s /bin/bash -c "DISPLAY={{ display }} xpra stop {{ display }}" || true

    - name: Cleanup cgroups
      shell: |
        docker exec {{ container_name }} sh -c '
          rmdir /sys/fs/cgroup/memory/link-{{ link_id }} 2>/dev/null || true
          rmdir /sys/fs/cgroup/pids/link-{{ link_id }} 2>/dev/null || true
        '

    - name: Remove Linux user
      shell: docker exec {{ container_name }} userdel "link-{{ link_id }}" || true

    - name: Remove session directory (includes token file)
      shell: docker exec {{ container_name }} rm -rf {{ session_dir }}
```

### Playbook 5: 检查会话状态

**文件:** `wireshark_session_status.yml`

```yaml
---
- name: Check Wireshark Session Status
  hosts: wireshark_hosts
  gather_facts: no
  vars:
    session_dir: "/tmp/sessions/link-{{ link_id }}"
    container_name: "gns3-ws-{{ project_id }}"
  tasks:
    - name: Check if user exists
      shell: docker exec {{ container_name }} id "link-{{ link_id }}" 2>/dev/null && echo "exists" || echo "not_found"
      register: user_check

    - name: Check if xpra session is running
      shell: docker exec {{ container_name }} ps aux | grep -v grep | grep "xpra.*{{ display }}" | grep "link-{{ link_id }}" || true
      register: xpra_check

    - name: Check if wireshark is running
      shell: docker exec {{ container_name }} ps aux | grep -v grep | grep "wireshark" | grep "link-{{ link_id }}" || true
      register: wireshark_check

    - name: Check if session directory exists
      shell: docker exec {{ container_name }} test -d {{ session_dir }} && echo "exists" || echo "not_found"
      register: session_dir_check

    - name: Set session status
      set_fact:
        session_status:
          link_id: "{{ link_id }}"
          display: "{{ display }}"
          user_exists: "{{ 'exists' in user_check.stdout }}"
          xpra_running: "{{ xpra_check.stdout != '' }}"
          wireshark_running: "{{ wireshark_check.stdout != '' }}"
          session_dir_exists: "{{ 'exists' in session_dir_check.stdout }}"
          status: "{{ 'running' if ('exists' in user_check.stdout and wireshark_check.stdout != '') else 'stopped' }}"
```

### Inventory 示例

```ini
[wireshark_hosts]
wireshark-01 ansible_host=192.168.1.100 ansible_user=root

[wireshark_hosts:vars]
gns3_server_url=http://192.168.1.50:3080
```

### 执行示例

```bash
# 为项目创建容器
ansible-playbook wireshark_container_create.yml \
  -e "project_id=76ead2b0-fd00-407c-b5db-abc83445886e"

# 删除项目容器
ansible-playbook wireshark_container_delete.yml \
  -e "project_id=76ead2b0-fd00-407c-b5db-abc83445886e"

# 为链路创建会话
ansible-playbook wireshark_session_create.yml \
  -e "link_id=76ead2b0-fd00-407c-b5db-abc83445886e" \
  -e "project_id=76ead2b0-fd00-407c-b5db-abc83445886e" \
  -e "user_token=eyJhbGc..." \
  -e "display=:0"

# 清理会话
ansible-playbook wireshark_session_cleanup.yml \
  -e "link_id=76ead2b0-fd00-407c-b5db-abc83445886e" \
  -e "project_id=76ead2b0-fd00-407c-b5db-abc83445886e" \
  -e "display=:0"

# 检查状态
ansible-playbook wireshark_session_status.yml \
  -e "link_id=76ead2b0-fd00-407c-b5db-abc83445886e" \
  -e "project_id=76ead2b0-fd00-407c-b5db-abc83445886e" \
  -e "display=:0"
```

## 组件职责

| 组件 | 职责 |
|-----------|------|
| GNS3 Server | 捕获数据提供者 (持久化存储)、WebSocket 代理、会话管理器 |
| ProjectContainerManager | 容器生命周期 (每个 project 创建/删除) |
| WiresharkSessionManager | 会话生命周期 (每个 link 创建/清理) |
| DisplayManager | 追踪每容器 X 显示器号 (:0-:10) |
| `capture/stream` API | 通过 HTTP 向授权消费者流式传输 pcap 数据 |
| WebSocket 代理 | 将浏览器连接转发到 Wireshark 容器 |
| Ansible | 在主机上处理容器和会话操作 |
| Wireshark 容器 | Project 级容器，通过 xpra 托管多个 Wireshark 会话 |
| xpra | 管理多个 X 会话，提供 WebSocket/VNC |
| noVNC | 通过代理桥接 xpra X 会话到浏览器 |
| Linux 用户 (按 link_id) | 按会话隔离进程、文件、资源 |
| cgroups | 按用户强制执行资源限制 |
| 会话文件 | 安全存储 JWT token (不在 CLI 中) |

## 安全

| 关注点 | 缓解措施 |
|---------|------------|
| JWT token 在 CLI 中 | Token 存储在会话文件中，mode 0600，Wireshark 进程读取 |
| Token 在 shell 历史中 | Token 写入文件而不是使用 shell 历史 |
| Token 在 `ps aux` 中可见 | Token 文件只能被 `link-{uuid}` 用户读取 |
| 浏览器直接访问容器 | 所有访问通过 GNS3 Server WebSocket 代理 |
| 未授权的 WebSocket 连接 | JWT 验证 + 链路所有权检查 |
| Wireshark 资源滥用 | cgroups 限制每个用户的内存 (2GB) 和进程数 (50) |
| xpra 未授权访问 | `--auth=allow` 信任来自 GNS3 Server 的连接 (网络隔离) |
| Token 过期 | Token 在会话创建时传递；Wireshark 使用直到会话结束 |
| 容器隔离 | 每个 project 一个容器提供 project 级隔离 |

### 信任模型

```
┌─────────────────────────────────────────────────────────────────┐
│                        信任边界                                  │
│                                                                  │
│  ┌─────────────┐     JWT 验证         ┌──────────────────┐      │
│  │   浏览器    │ ─────────────────────► │   GNS3 Server   │      │
│  │             │      在此点验证         │  (WebSocket)    │      │
│  └─────────────┘                        └────────┬─────────┘      │
│                                                   │               │
│  浏览器不能直接访问容器。                          │ GNS3 Server  │
│  所有流量都通过 GNS3 Server 代理。                 │ 是可信网关    │
│                                                   │               │
│                                                   ▼               │
│                                          ┌──────────────────┐     │
│                                          │ Wireshark        │     │
│                                          │ Container        │     │
│                                          │ (project-level)  │     │
│                                          └──────────────────┘     │
└─────────────────────────────────────────────────────────────────┘

xpra 使用 --auth=allow，意味着:
- GNS3 Server 是唯一能访问 xpra 端口的实体
- GNS3 Server 已经通过 JWT 完成了用户认证
- 容器网络应该被防火墙限制为只允许 GNS3 Server 访问
```

## 会话生命周期详情

| 事件 | 操作 | 状态转换 |
|-------|--------|------------------|
| Project 打开 | Ansible 创建容器 | container: stopped → running |
| 用户点击查看 Wireshark | 分配显示器，触发 Ansible 创建 | session: idle → pending |
| Ansible 开始运行 | xpra 和 wireshark 进程启动中 | pending → starting |
| Ansible 成功完成 | 会话可以查看 | starting → ready |
| Ansible 失败 | 会话错误 | starting → error |
| 用户连接 noVNC | WebSocket 代理到 xpra | (无状态变化) |
| 用户断开 noVNC | 如果仍在捕获，会话保持运行 | (无状态变化) |
| 用户点击停止 Wireshark 视图 | 触发 Ansible 清理 | any → closing |
| 清理完成 | 释放显示器，删除会话 | closing → idle |
| Project 关闭 | Ansible 销毁容器，清理所有会话 | container: running → stopped |
| GNS3 Server 重启 | 容器存活 (project 仍打开) | container 保持运行 |
| 容器重启 | 下次访问 project 时重新创建容器 | container: stopped → running |

## 捕获存储

- GNS3 Server 将捕获保存到项目目录 (现有行为)
  - 路径: `/path/to/projects/{project_id}/project-files/captures/`
- Wireshark 从 `capture/stream` API 消费实时流
- 用户可以随时通过现有下载 API 下载完整捕获文件
- **Wireshark 容器不持久化捕获数据 (无状态查看器)**
- 捕获文件独立于容器生命周期持久化

## Wireshark 容器

### Dockerfile

```dockerfile
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    wireshark \
    xpra \
    xvfb \
    curl \
    openssh-server \
    python3 \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# SSH configuration for Ansible access
RUN mkdir /var/run/sshd

# Create sessions directory
RUN mkdir -p /tmp/sessions && chmod 1777 /tmp/sessions

# Container startup script
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Expose ports
EXPOSE 10000 22

CMD ["/start.sh"]
```

### start.sh

```bash
#!/bin/bash
# /start.sh - Container entrypoint

# Start SSH for Ansible access
service ssh start

# Start xpra in daemon mode
xpra start :0 --html=on --bind-tcp=0.0.0.0:10000 --auth=allow --daemonize

# Keep container running
tail -f /dev/null
```

### 容器组件

| 组件 | 用途 |
|-----------|---------|
| wireshark | 从 GNS3 Server 渲染 pcap 流的 GUI |
| xpra | 多用户 X 会话管理、WebSocket 支持 |
| xvfb | 无头 X 的虚拟帧缓冲 |
| curl | 获取 pcap 流的 HTTP 客户端 |
| openssh-server | Ansible 远程执行 |

### 运行容器

```bash
# 容器由 Ansible 创建/销毁
# 示例 docker run (由 Ansible 执行):
docker run -d \
  --name gns3-ws-{project_id} \
  --hostname wireshark-{project_id[:8]} \
  --memory=4g \
  --cpus=2 \
  gns3/wireshark-server:latest \
  /start.sh
```

### 容器内部结构

```
/
├── tmp/
│   └── sessions/
│       └── link-{uuid}/
│           └── token          # JWT token for capture/stream API (0600)
├── sys/fs/cgroup/             # cgroups mounts
└── usr/bin/
    ├── wireshark
    ├── xpra
    └── xvfb-run
```

## 实现状态

| 组件 | 状态 | 备注 |
|-----------|--------|-------|
| ProjectContainerManager | TODO | 容器生命周期管理 |
| DisplayManager | TODO | 每容器显示器分配 (:0-:10) |
| WiresharkSessionManager | TODO | 会话状态机 + Ansible 运行器 |
| WebSocket 处理器 | TODO | 带状态协议的 FastAPI WebSocket |
| Ansible Playbooks | TODO | 容器和会话 playbooks |
| Dockerfile + start.sh | TODO | 容器镜像和启动脚本 |
| Link API 修改 | TODO | 在 start/stop 中添加 wireshark=true |
| 前端集成 | TODO | 连接到 WebSocket，显示 noVNC |

## 故障排除

| 问题 | 诊断 | 解决方案 |
|-------|-----------|----------|
| WebSocket 以 4001 关闭 | JWT token 无效 | 刷新 token，检查链路所有权 |
| WebSocket 以 4004 关闭 | 会话未找到 | 先点击"View in Wireshark" |
| 消息类型一直是 "waiting" | Ansible 未完成 | 检查 Ansible 日志 |
| 消息类型是 "error" | 会话创建失败 | 检查错误消息，验证容器可达 |
| noVNC 连接但显示黑屏 | Wireshark 未启动 | 通过状态 playbook 检查 wireshark 进程 |
| xpra 连接被拒绝 | 容器未运行 | 检查 project 是否打开 |
| Wireshark 中未显示捕获 | Token 过期或 API 问题 | Token 有效性绑定到会话生命周期 |
| 容器未找到 | 项目容器未创建 | 检查 project 是否打开 |

## 未来增强

1. **AWX/Tower 集成** - 用 AWX API 替换 subprocess 调用以获得更好的编排
2. **会话恢复** - 持久化会话状态以在 GNS3 Server 重启后存活
3. **多查看器** - 允许多个浏览器查看同一 Wireshark 会话 (只读模式)
4. **会话录制** - 保存 Wireshark 交互以供回放
5. **容器镜像变体** - 不同项目类型使用不同镜像 (安全版、基本版等)
