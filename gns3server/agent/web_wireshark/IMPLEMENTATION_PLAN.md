# Web Wireshark 集成到 GNS3 Server - 脚本驱动方案（更新版）

## 背景

通过简单的脚本驱动方式实现 Web Wireshark 集成。当 POST link/capture 时携带 `wireshark: true` 参数，调用脚本管理容器和 xpra 服务。

## 核心设计

**工作流程：**
1. 用户 POST `/v3/projects/{project_id}/links/{link_id}/capture/start` 携带 `wireshark: true`
2. API 端点从 `Authorization` header 提取 JWT token
3. 调用管理脚本，传递 JWT token、project_id、link_id（可选 capture_url）
4. 脚本自动检测 GNS3 server 地址（如果未提供 capture_url）
5. 脚本创建（或复用）容器 `gns3-wireshark-{project_id}`
6. 脚本在容器内启动 xpra 会话 `--session-name=link-{link_id}`
7. 脚本启动 Wireshark 并连接到抓包流
8. 前端通过 WebSocket 连接到 `/v3/projects/{project_id}/links/{link_id}/capture/web-wireshark`
9. gns3server 代理 WebSocket 连接到容器的 xpra 服务
10. 停止捕获时，脚本停止对应的 xpra 会话

**关键优势：**
- ✅ WebSocket 代理集成（统一访问入口）
- ✅ 脚本管理所有容器操作
- ✅ gns3server 代理 WebSocket 到容器 xpra
- ✅ 使用 session-name 区分不同 link 的会话
- ✅ 直接从 API 端点提取 JWT token（无需 Controller 方法）
- ✅ 脚本可自动检测 GNS3 server 地址（复用 gns3-copilot 逻辑）

**架构说明：**
- 前端通过 `ws://gns3server/v3/projects/{project_id}/links/{link_id}/capture/web-wireshark` 连接
- gns3server 作为 WebSocket 代理，转发到容器的 xpra 服务
- 容器端口不需要映射到宿主机，通过容器网络访问

## 实现方案

### 1. 管理脚本

**文件：** `gns3server/agent/web_wireshark/manage_wireshark.py`

```python
#!/usr/bin/env python3
"""
Web Wireshark 管理脚本
负责创建容器、启动 xpra 会话、管理 Wireshark 进程
"""

import sys
import json
import argparse
import time
import logging
from typing import Optional
from docker import DockerClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 默认 GNS3 server 地址
DEFAULT_GNS3_URL = "http://127.0.0.1:3080"


class WebWiresharkManager:
    def __init__(self):
        self.docker = DockerClient(base_url="unix:///var/run/docker.sock")
        self.network_name = "gns3-wireshark"

    def _get_gns3_url_from_controller(self) -> Optional[str]:
        """从 Controller 实例获取 GNS3 server URL

        参考 gns3-copilot 的实现方式
        """
        try:
            from gns3server.controller import Controller
            controller = Controller.instance()
            local_compute = controller.get_compute("local")

            url = f"{local_compute.protocol}://{local_compute.host}:{local_compute.port}"
            logger.info(f"Got GNS3 URL from Controller: {url}")
            return url
        except ImportError as e:
            logger.debug(f"Cannot import Controller: {e}")
            return None
        except AttributeError as e:
            logger.debug(f"Controller instance not available: {e}")
            return None
        except KeyError as e:
            logger.debug(f"Local compute not found in Controller: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error getting URL from Controller: {e}")
            return None

    def _get_gns3_url_from_config(self) -> Optional[str]:
        """从 Config 配置获取 GNS3 server URL

        参考 gns3-copilot 的实现方式
        """
        try:
            from gns3server.config import Config
            server_config = Config.instance().settings.Server
            url = f"{server_config.protocol.value}://{server_config.host}:{server_config.port}"
            logger.info(f"Got GNS3 URL from Config: {url}")
            return url
        except ImportError as e:
            logger.debug(f"Cannot import Config: {e}")
            return None
        except AttributeError as e:
            logger.debug(f"Config settings not available: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error getting URL from Config: {e}")
            return None

    def detect_gns3_url(self) -> str:
        """自动检测 GNS3 server 地址

        优先级顺序：
        1. Controller.instance().compute("local")
        2. Config.instance().settings.Server
        3. 默认值 http://127.0.0.1:3080

        Returns:
            GNS3 server URL 字符串
        """
        logger.debug("Auto-detecting GNS3 server URL...")

        # 策略 1: 从 Controller 获取
        url = self._get_gns3_url_from_controller()
        if url:
            return url

        # 策略 2: 从 Config 获取
        url = self._get_gns3_url_from_config()
        if url:
            return url

        # 策略 3: 使用默认值
        logger.warning(f"Using fallback default URL: {DEFAULT_GNS3_URL}")
        return DEFAULT_GNS3_URL

    def ensure_network(self):
        """确保 Docker 网络存在"""
        try:
            self.docker.networks.get(self.network_name)
            logger.info(f"Network {self.network_name} already exists")
        except:
            logger.info(f"Creating network {self.network_name}")
            self.docker.networks.create(
                self.network_name,
                driver="bridge",
                subnet="100.64.0.0/22"
            )

    def get_or_create_container(self, project_id: str):
        """获取或创建项目的 Web Wireshark 容器"""
        container_name = f"gns3-wireshark-{project_id}"

        try:
            container = self.docker.containers.get(container_name)
            if container.status != "running":
                logger.info(f"Starting existing container {container_name}")
                container.start()
            return container
        except:
            # 创建新容器
            logger.info(f"Creating new container {container_name}")
            container = self.docker.containers.run(
                "gns3/web-wireshark:latest",
                name=container_name,
                detach=True,
                network=self.network_name,
                mem_limit="2g",
                cpu_quota=100000,
                pids_limit=1000,
                restart_policy={"Name": "unless-stopped"},
                environment={
                    "XDG_RUNTIME_DIR": "/run/user/1000",
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8"
                }
            )
            return container

    def start_wireshark_session(
        self,
        project_id: str,
        link_id: str,
        jwt_token: str,
        capture_stream_url: Optional[str] = None
    ) -> dict:
        """启动 Web Wireshark 会话

        Args:
            project_id: 项目 ID
            link_id: 链路 ID
            jwt_token: JWT 认证令牌
            capture_stream_url: 抓包流 URL（可选，如果未提供则自动检测）
        """
        logger.info(f"Starting Web Wireshark session for link {link_id}")

        # 如果未提供 capture_stream_url，自动构造
        if not capture_stream_url:
            gns3_url = self.detect_gns3_url()
            capture_stream_url = f"{gns3_url}/v3/projects/{project_id}/links/{link_id}/capture/stream"
            logger.info(f"Auto-detected capture stream URL: {capture_stream_url}")

        container = self.get_or_create_container(project_id)

        # 分配 display 和端口
        # 使用 link_id 的 hash 来分配固定的 display 和端口
        link_hash = abs(hash(link_id)) % 10
        display = 100 + link_hash
        port = 12300 + link_hash

        # 启动 xpra 会话
        session_name = f"link-{link_id}"
        logger.info(f"Starting xpra session {session_name} on display :{display}")

        xpra_cmd = (
            f"xpra start :{display} "
            f"--xvfb='Xvfb -screen 0 1920x1080x24 +extension RANDR' "
            f"--html=on "
            f"--bind-tcp=0.0.0.0:{port} "
            f"--session-name={session_name} "
            f"--daemon=yes "
            f"--dbus-launch=no "
            f"--resize-display=yes"
        )

        exit_code, output = container.exec_run(xpra_cmd, detach=True)
        if exit_code != 0:
            logger.error(f"Failed to start xpra: {output}")
            raise RuntimeError(f"Failed to start xpra session: {output}")

        # 等待 xpra 初始化
        time.sleep(2)

        # 启动 Wireshark 并连接抓包流
        wireshark_cmd = (
            f"curl -N -H 'Authorization: Bearer {jwt_token}' "
            f"'{capture_stream_url}' | "
            f"wireshark -i - -k -display :{display}"
        )

        logger.info(f"Starting Wireshark with capture stream: {capture_stream_url}")

        # 在后台启动 Wireshark
        exit_code, output = container.exec_run(
            f"bash -c \"{wireshark_cmd}\"",
            detach=True,
            stdin=True
        )

        if exit_code != 0:
            logger.error(f"Failed to start Wireshark: {output}")
            raise RuntimeError(f"Failed to start Wireshark: {output}")

        # 获取容器 IP
        container.reload()
        networks = container.attrs["NetworkSettings"]["Networks"]
        container_ip = networks.get(self.network_name, {}).get("IPAddress", "")

        if not container_ip:
            logger.error(f"Container {container.name} has no IP in network {self.network_name}")
            raise RuntimeError(f"Container has no IP address")

        result = {
            "link_id": link_id,
            "display": display,
            "port": port,
            "url": f"http://{container_ip}:{port}",
            "container_name": container.name,
            "session_name": session_name,
            "capture_stream_url": capture_stream_url
        }

        logger.info(f"Web Wireshark session started successfully: {result['url']}")
        return result

    def stop_wireshark_session(self, project_id: str, link_id: str):
        """停止单个 Web Wireshark 会话"""
        logger.info(f"Stopping Web Wireshark session for link {link_id}")
        try:
            container_name = f"gns3-wireshark-{project_id}"
            container = self.docker.containers.get(container_name)

            # 获取 display 编号
            link_hash = abs(hash(link_id)) % 10
            display = 100 + link_hash

            # 停止 xpra 会话
            logger.info(f"Stopping xpra session :{display}")
            exit_code, output = container.exec_run(f"xpra stop :{display}", detach=True)

            if exit_code == 0:
                logger.info(f"Web Wireshark session stopped successfully")
            else:
                logger.warning(f"xpra stop returned exit code {exit_code}: {output}")

        except Exception as e:
            logger.error(f"Error stopping session: {e}")

    def stop_all_sessions(self, project_id: str):
        """停止项目的所有 Web Wireshark 会话"""
        logger.info(f"Stopping all Web Wireshark sessions for project {project_id}")
        try:
            container_name = f"gns3-wireshark-{project_id}"
            container = self.docker.containers.get(container_name)

            # 停止所有 xpra 会话（display 100-109）
            for display in range(100, 110):
                try:
                    exit_code, output = container.exec_run(f"xpra stop :{display}", detach=True)
                    if exit_code == 0:
                        logger.info(f"Stopped xpra session :{display}")
                except:
                    # 忽略不存在的会话
                    pass

            logger.info(f"All Web Wireshark sessions stopped for project {project_id}")

        except Exception as e:
            logger.error(f"Error stopping all sessions: {e}")

    def stop_container(self, project_id: str):
        """停止 Web Wireshark 容器"""
        logger.info(f"Stopping Web Wireshark container for project {project_id}")
        try:
            container_name = f"gns3-wireshark-{project_id}"
            container = self.docker.containers.get(container_name)

            if container.status == "running":
                container.stop(timeout=10)
                logger.info(f"Container {container_name} stopped successfully")
            else:
                logger.info(f"Container {container_name} already stopped")

        except Exception as e:
            logger.error(f"Error stopping container: {e}")

    def delete_container(self, project_id: str):
        """删除 Web Wireshark 容器"""
        logger.info(f"Deleting Web Wireshark container for project {project_id}")
        try:
            container_name = f"gns3-wireshark-{project_id}"
            container = self.docker.containers.get(container_name)

            # 先停止容器
            if container.status == "running":
                container.stop(timeout=5)

            # 删除容器
            container.remove()
            logger.info(f"Container {container_name} deleted successfully")

        except Exception as e:
            logger.error(f"Error deleting container: {e}")


def main():
    parser = argparse.ArgumentParser(description="Web Wireshark 管理脚本")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # start 命令
    start_parser = subparsers.add_parser("start", help="启动 Web Wireshark 会话")
    start_parser.add_argument("--project-id", required=True, help="项目 ID")
    start_parser.add_argument("--link-id", required=True, help="链路 ID")
    start_parser.add_argument("--jwt-token", required=True, help="JWT 认证令牌")
    start_parser.add_argument("--capture-url", help="抓包流 URL（可选，未提供则自动检测）")

    # stop 命令
    stop_parser = subparsers.add_parser("stop", help="停止单个 Web Wireshark 会话")
    stop_parser.add_argument("--project-id", required=True, help="项目 ID")
    stop_parser.add_argument("--link-id", required=True, help="链路 ID")

    # stop-sessions 命令
    stop_sessions_parser = subparsers.add_parser("stop-sessions", help="停止项目的所有 xpra 会话")
    stop_sessions_parser.add_argument("--project-id", required=True, help="项目 ID")

    # stop-container 命令
    stop_container_parser = subparsers.add_parser("stop-container", help="停止 Web Wireshark 容器")
    stop_container_parser.add_argument("--project-id", required=True, help="项目 ID")

    # delete-container 命令
    delete_container_parser = subparsers.add_parser("delete-container", help="删除 Web Wireshark 容器")
    delete_container_parser.add_argument("--project-id", required=True, help="项目 ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    manager = WebWiresharkManager()

    try:
        if args.command == "start":
            manager.ensure_network()
            result = manager.start_wireshark_session(
                args.project_id,
                args.link_id,
                args.jwt_token,
                getattr(args, 'capture_url', None)  # 可选参数
            )
            print(json.dumps(result))

        elif args.command == "stop":
            manager.stop_wireshark_session(args.project_id, args.link_id)

        elif args.command == "stop-sessions":
            manager.stop_all_sessions(args.project_id)

        elif args.command == "stop-container":
            manager.stop_container(args.project_id)

        elif args.command == "delete-container":
            manager.delete_container(args.project_id)

    except Exception as e:
        logger.error(f"Error: {e}")
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
```

### 2. Link 捕获增强

**文件：** `gns3server/controller/link.py`

在 `Link` 类中添加：

```python
import os
import sys
import asyncio
import json
import logging

log = logging.getLogger(__name__)

class Link:
    # 现有代码...

    async def start_capture(
        self,
        data_link_type="DLT_EN10MB",
        capture_file_name=None,
        wireshark=False,  # 新增参数
        jwt_token=None    # 新增参数
    ):
        """开始链路抓包"""
        # 现有捕获逻辑...
        self._capturing = True
        self._capture_file_name = capture_file_name
        self._project.emit_notification("link.updated", self.asdict())

        # 如果需要 Web Wireshark
        if wireshark:
            await self._start_web_wireshark(jwt_token)

    async def _start_web_wireshark(self, jwt_token: str):
        """启动 Web Wireshark

        Args:
            jwt_token: JWT 认证令牌
        """
        if not jwt_token:
            log.error("JWT token is required for Web Wireshark")
            return

        try:
            # 调用管理脚本（不传递 capture_url，让脚本自动检测）
            script_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "agent",
                "web_wireshark",
                "manage_wireshark.py"
            )

            # 确保脚本路径存在
            if not os.path.exists(script_path):
                log.error(f"Web Wireshark script not found: {script_path}")
                return

            log.info(f"Starting Web Wireshark for link {self.id}")

            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                script_path,
                "start",
                "--project-id", self._project.id,
                "--link-id", self.id,
                "--jwt-token", jwt_token
                # 不传递 --capture-url，让脚本自动检测
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                log.error(f"Failed to start Web Wireshark: {stderr.decode()}")
                return

            # 解析结果
            try:
                result = json.loads(stdout.decode())

                # 发送通知
                self._project.emit_notification("link.web_wireshark_started", {
                    "link_id": self.id,
                    "url": result["url"]
                })

                log.info(f"Web Wireshark started for link {self.id}: {result['url']}")

            except json.JSONDecodeError as e:
                log.error(f"Failed to parse script output: {e}")

        except Exception as e:
            log.error(f"Error starting Web Wireshark: {e}")

    async def stop_capture(self):
        """停止抓包"""
        # 停止 Web Wireshark
        if self._capturing:
            await self._stop_web_wireshark()

        # 现有停止逻辑...
        self._capturing = False
        self._project.emit_notification("link.updated", self.asdict())

    async def _stop_web_wireshark(self):
        """停止 Web Wireshark"""
        try:
            script_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "agent",
                "web_wireshark",
                "manage_wireshark.py"
            )

            if not os.path.exists(script_path):
                log.warning(f"Web Wireshark script not found: {script_path}")
                return

            log.info(f"Stopping Web Wireshark for link {self.id}")

            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                script_path,
                "stop",
                "--project-id", self._project.id,
                "--link-id", self.id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                log.info(f"Web Wireshark stopped for link {self.id}")
            else:
                log.warning(f"Failed to stop Web Wireshark: {stderr.decode()}")

        except Exception as e:
            log.error(f"Error stopping Web Wireshark: {e}")
```

### 3. API Schema 更新

**文件：** `gns3server/schemas/controller/links.py`

添加 `wireshark` 字段：

```python
class LinkCapture(BaseModel):
    data_link_type: str = "DLT_EN10MB"
    capture_file_name: Optional[str] = None
    wireshark: bool = False  # 新增字段
```

### 4. API 路由更新

**文件：** `gns3server/api/routes/controller/links.py`

更新捕获启动端点，从 Request 中提取 JWT token：

```python
from fastapi import Request

@router.post("/{link_id}/capture/start",
             response_model=schemas.Link,
             dependencies=[Depends(has_privilege("Link.Capture"))])
async def start_capture(
    link_data: schemas.LinkCapture,
    http_request: Request,  # 添加 Request 参数
    link: Link = Depends(dep_link)
) -> schemas.Link:
    """Start a packet capture on a link"""

    # 从 Authorization header 提取 JWT token
    auth_header = http_request.headers.get("Authorization", "")
    jwt_token = auth_header.replace("Bearer ", "") if auth_header else None

    await link.start_capture(
        data_link_type=link_data.data_link_type,
        capture_file_name=link_data.capture_file_name,
        wireshark=link_data.wireshark,
        jwt_token=jwt_token  # 传递 token
    )
    return link.asdict()
```

添加 WebSocket 代理端点：

```python
from fastapi import WebSocket
import aiohttp

@router.websocket("/{link_id}/capture/web-wireshark")
async def web_wireshark_websocket(
    websocket: WebSocket,
    link_id: str,
    project_id: str
):
    """
    WebSocket 代理端点，转发到容器的 xpra HTML5 客户端

    路径：ws://host/v3/projects/{project_id}/links/{link_id}/capture/web-wireshark
    """
    from gns3server.agent.gns3_copilot.gns3_client.connector_factory import _detect_url_for_api

    await websocket.accept()
    log.info(f"New WebSocket connection for project {project_id}, link {link_id}")

    try:
        # 获取容器信息
        container_name = f"gns3-wireshark-{project_id}"

        # 计算 xpra 端口
        link_hash = abs(hash(link_id)) % 10
        xpra_port = 12300 + link_hash

        # 获取容器 IP
        from gns3server.compute.docker import Docker
        docker_manager = Docker.instance()

        container_info = await docker_manager.query(
            "GET",
            f"containers/{container_name}/json"
        )

        networks = container_info["NetworkSettings"]["Networks"]
        container_ip = None

        # 查找 gns3-wireshark 网络
        for network_name, network_config in networks.items():
            if "wireshark" in network_name.lower():
                container_ip = network_config["IPAddress"]
                break

        if not container_ip:
            log.error(f"Container {container_name} not found in wireshark network")
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return

        # 构造容器 WebSocket URL
        container_ws_url = f"ws://{container_ip}:{xpra_port}"
        log.info(f"Proxying WebSocket to container: {container_ws_url}")

        # 双向转发
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(container_ws_url) as container_ws:

                async def forward_client_to_container():
                    """从客户端转发到容器"""
                    try:
                        while True:
                            data = await websocket.receive_text()
                            await container_ws.send_str(data)
                    except Exception as e:
                        log.error(f"Error forwarding client to container: {e}")

                async def forward_container_to_client():
                    """从容器转发到客户端"""
                    try:
                        async for msg in container_ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await websocket.send_text(msg.data)
                            elif msg.type == aiohttp.WSMsgType.BINARY:
                                await websocket.send_bytes(msg.data)
                    except Exception as e:
                        log.error(f"Error forwarding container to client: {e}")

                # 并行运行两个转发任务
                await asyncio.gather(
                    forward_client_to_container(),
                    forward_container_to_client(),
                    return_exceptions=True
                )

    except WebSocketDisconnect:
        log.info(f"WebSocket disconnected for link {link_id}")
    except Exception as e:
        log.error(f"Error in WebSocket proxy for link {link_id}: {e}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=str(e))
```

### 5. 清理逻辑

**清理策略：**

1. **项目关闭时**：停止所有 xpra 会话，停止容器（保留容器便于快速重启）
2. **项目删除时**：停止所有 xpra 会话，删除容器
3. **服务器启动时**：智能清理僵尸容器

**容器命名：** `gns3-wireshark-{project_id}` （精确标识，避免误删）

#### 5.1 Project 类清理方法

**文件：** `gns3server/controller/project.py`

```python
import time

class Project:
    def __init__(self, ...):
        # 现有代码...
        self._web_wireshark_container_created = False  # 标记容器是否已创建

    async def _cleanup_web_wireshark_xpra_sessions(self):
        """
        清理所有 Web Wireshark xpra 会话（不删除容器）

        在项目关闭时调用，停止所有 xpra 会话和 Wireshark 进程
        但保留容器，便于项目重新打开时快速复用
        """
        try:
            if not self._web_wireshark_container_created:
                return

            log.info(f"Stopping xpra sessions for project '{self.name}' ({self.id})")

            # 调用脚本停止所有会话
            script_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "agent",
                "web_wireshark",
                "manage_wireshark.py"
            )

            if not os.path.exists(script_path):
                log.warning(f"Web Wireshark script not found: {script_path}")
                return

            # 停止所有会话
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                script_path,
                "stop-sessions",
                "--project-id", self.id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                log.info(f"Web Wireshark xpra sessions stopped successfully")
            else:
                log.warning(f"Failed to stop xpra sessions: {stderr.decode()}")

        except Exception as e:
            # 不抛出异常，避免影响项目关闭流程
            log.warning(f"Failed to cleanup xpra sessions for project '{self.name}': {e}")

    async def _stop_web_wireshark_container(self):
        """
        停止 Web Wireshark 容器（但不删除）

        在项目关闭时调用，停止容器以释放内存
        但保留容器，便于项目重新打开时快速启动
        """
        try:
            if not self._web_wireshark_container_created:
                return

            container_name = f"gns3-wireshark-{self.id}"
            log.info(f"Stopping Web Wireshark container '{container_name}' for project '{self.name}'")

            script_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "agent",
                "web_wireshark",
                "manage_wireshark.py"
            )

            if not os.path.exists(script_path):
                return

            # 停止容器
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                script_path,
                "stop-container",
                "--project-id", self.id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                log.info(f"Web Wireshark container stopped successfully")
            else:
                log.warning(f"Failed to stop container: {stderr.decode()}")

        except Exception as e:
            log.warning(f"Failed to stop container for project '{self.name}': {e}")

    async def _cleanup_web_wireshark_container(self):
        """
        删除 Web Wireshark 容器

        在项目删除时调用，停止并删除容器
        """
        try:
            if not self._web_wireshark_container_created:
                return

            container_name = f"gns3-wireshark-{self.id}"
            log.info(f"Deleting Web Wireshark container '{container_name}' for project '{self.name}'")

            script_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "agent",
                "web_wireshark",
                "manage_wireshark.py"
            )

            if not os.path.exists(script_path):
                return

            # 删除容器
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                script_path,
                "delete-container",
                "--project-id", self.id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                log.info(f"Web Wireshark container deleted successfully")
                self._web_wireshark_container_created = False
            else:
                log.warning(f"Failed to delete container: {stderr.decode()}")

        except Exception as e:
            log.warning(f"Failed to delete container for project '{self.name}': {e}")

    async def close(self):
        """关闭项目"""
        # 现有代码...

        # 1. 停止所有 xpra 会话
        await self._cleanup_web_wireshark_xpra_sessions()

        # 2. 停止容器（保留，便于快速重启）
        await self._stop_web_wireshark_container()

        # 清理 GNS3 Copilot AgentService
        await self._cleanup_copilot_agent()

        # 现有代码...

    async def delete(self):
        """删除项目"""
        # 现有代码...

        # 删除 Web Wireshark 容器
        await self._cleanup_web_wireshark_container()

        # 现有代码...
```

#### 5.2 服务器启动时清理

**文件：** `gns3server/controller/controller.py` 或新建清理模块

```python
async def cleanup_web_wireshark_containers_on_startup():
    """
    服务器启动时智能清理 Web Wireshark 容器

    清理策略：
    1. 删除僵尸容器（项目不存在）
    2. 停止孤立容器（项目已关闭）
    3. 保留活跃容器（项目已打开）
    """
    try:
        from gns3server.agent.web_wireshark.manage_wireshark import WebWiresharkManager

        manager = WebWiresharkManager()
        docker = manager.docker

        # 获取所有 gns3-wireshark- 开头的容器
        containers = docker.containers.list(
            all=True,
            filters={"name": "gns3-wireshark-"}
        )

        log.info(f"Found {len(containers)} Web Wireshark containers to check")

        for container in containers:
            # 提取 project_id
            # 容器名格式：gns3-wireshark-{project_id}
            project_id = container.name.replace("gns3-wireshark-", "")

            try:
                # 检查项目是否存在
                project = controller.get_project(project_id)

                # 项目存在
                if project.status == "opened":
                    # 项目已打开，保持容器运行
                    log.info(f"Container {container.name} belongs to active project, keeping it running")

                    # 确保容器在运行
                    if container.status != "running":
                        log.info(f"Starting container {container.name} for active project")
                        container.start()

                else:
                    # 项目已关闭，停止容器但保留
                    if container.status == "running":
                        log.info(f"Stopping container {container.name} (project is closed)")
                        container.stop()
                    else:
                        log.info(f"Container {container.name} already stopped (project is closed)")

            except ControllerNotFoundError:
                # 项目不存在，删除僵尸容器
                log.warning(f"Project {project_id} not found, removing zombie container {container.name}")
                try:
                    if container.status == "running":
                        container.stop()
                    container.remove()
                    log.info(f"Removed zombie container {container.name}")
                except Exception as e:
                    log.error(f"Failed to remove zombie container {container.name}: {e}")

    except Exception as e:
        log.error(f"Error during Web Wireshark container cleanup on startup: {e}")
```

在 `Controller` 启动时调用：

```python
class Controller:
    async def load(self):
        """加载控制器"""
        # 现有代码...

        # 清理 Web Wireshark 僵尸容器
        await cleanup_web_wireshark_containers_on_startup()

        # 现有代码...
```

### 6. 管理脚本添加清理命令

**文件：** `gns3server/agent/web_wireshark/manage_wireshark.py`

添加 cleanup 命令：

```python
def main():
    parser = argparse.ArgumentParser(description="Web Wireshark 管理脚本")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # start 命令
    start_parser = subparsers.add_parser("start", help="启动 Web Wireshark 会话")
    start_parser.add_argument("--project-id", required=True, help="项目 ID")
    start_parser.add_argument("--link-id", required=True, help="链路 ID")
    start_parser.add_argument("--jwt-token", required=True, help="JWT 认证令牌")
    start_parser.add_argument("--capture-url", help="抓包流 URL（可选，未提供则自动检测）")

    # stop 命令
    stop_parser = subparsers.add_parser("stop", help="停止 Web Wireshark 会话")
    stop_parser.add_argument("--project-id", required=True, help="项目 ID")
    stop_parser.add_argument("--link-id", required=True, help="链路 ID")

    # cleanup 命令（新增）
    cleanup_parser = subparsers.add_parser("cleanup", help="清理 Web Wireshark 容器")
    cleanup_parser.add_argument("--project-id", required=True, help="项目 ID")
    cleanup_parser.add_argument("--force", action="store_true", help="强制删除，即使容器正在运行")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    manager = WebWiresharkManager()

    try:
        if args.command == "start":
            manager.ensure_network()
            result = manager.start_wireshark_session(
                args.project_id,
                args.link_id,
                args.jwt_token,
                getattr(args, 'capture_url', None)
            )
            print(json.dumps(result))

        elif args.command == "stop":
            manager.stop_wireshark_session(args.project_id, args.link_id)

        elif args.command == "cleanup":
            manager.cleanup_container(args.project_id, force=getattr(args, 'force', False))

    except Exception as e:
        logger.error(f"Error: {e}")
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


class WebWiresharkManager:
    # 现有代码...

    def cleanup_container(self, project_id: str, force: bool = False):
        """
        清理 Web Wireshark 容器

        Args:
            project_id: 项目 ID
            force: 是否强制删除（即使容器正在运行）
        """
        container_name = f"gns3-wireshark-{project_id}"

        try:
            container = self.docker.containers.get(container_name)

            logger.info(f"Stopping container {container_name}")
            container.stop(timeout=5)

            logger.info(f"Removing container {container_name}")
            container.remove()

            logger.info(f"Container {container_name} cleaned up successfully")

        except Exception as e:
            if force:
                # 强制删除：尝试直接删除容器
                try:
                    container = self.docker.containers.get(container_name)
                    container.remove(force=True)
                    logger.info(f"Container {container_name} force removed")
                except:
                    # 如果容器不存在，认为已经清理完成
                    logger.info(f"Container {container_name} not found, assuming already cleaned")
            else:
                logger.error(f"Error cleaning up container {container_name}: {e}")
                raise
```

### 清理场景

**1. 项目关闭时**
```
用户关闭项目
  ↓
Project.close()
  ↓
_cleanup_web_wireshark_container()
  ↓
脚本 cleanup 命令
  ↓
停止并删除容器
```

**2. 项目删除时**
```
用户删除项目
  ↓
Project.delete()
  ↓
先调用 close()
  ↓
_cleanup_web_wireshark_container()
  ↓
删除项目目录
```

**3. 服务器关闭时**
```
gns3-server 关闭
  ↓
Controller.unload()
  ↓
遍历所有项目
  ↓
每个项目调用 close()
  ↓
_cleanup_web_wireshark_container()
```

**4. 异常处理**
```
清理失败
  ↓
捕获异常
  ↓
记录警告日志
  ↓
不影响项目关闭流程
  ↓
继续执行其他清理
```

### 资源泄漏防护

**定期清理僵尸容器：**
```python
def cleanup_zombie_containers():
    """
    清理没有对应项目的僵尸容器

    可以定期调用此函数（如通过 cron 或系统启动时）
    """
    manager = WebWiresharkManager()
    docker = manager.docker

    # 获取所有 gns3- 开头的容器
    containers = docker.containers.list(all=True, filters={"name": "gns3-"})

    for container in containers:
        # 提取 project_id
        project_id = container.name.replace("gns3-", "")

        # 检查项目是否存在
        try:
            from gns3server.controller import Controller
            controller = Controller.instance()
            controller.get_project(project_id)
            # 项目存在，跳过
            continue
        except:
            # 项目不存在，删除容器
            logger.warning(f"Found zombie container {container.name}, removing...")
            try:
                container.remove(force=True)
                logger.info(f"Removed zombie container {container.name}")
            except Exception as e:
                logger.error(f"Failed to remove zombie container {container.name}: {e}")
```

## 关键特性

### GNS3 URL 自动检测

脚本使用三级回退策略自动检测 GNS3 server 地址（与 gns3-copilot 一致）：

1. **从 Controller 获取** - `Controller.instance().compute("local")`
2. **从 Config 获取** - `Config.instance().settings.Server`
3. **回退到默认值** - `http://127.0.0.1:3080`

### 灵活的 URL 传递

- **自动模式**：不传递 `--capture-url`，脚本自动检测并构造 URL
- **手动模式**：传递 `--capture-url`，脚本使用提供的 URL

```bash
# 自动模式（推荐）
python3 manage_wireshark.py start \
  --project-id xxx \
  --link-id yyy \
  --jwt-token zzz

# 手动模式（特殊场景）
python3 manage_wireshark.py start \
  --project-id xxx \
  --link-id yyy \
  --jwt-token zzz \
  --capture-url "http://custom-server:3080/v3/projects/xxx/links/yyy/capture/stream"
```

## 关键文件

### 需要创建的文件
- `gns3server/agent/web_wireshark/manage_wireshark.py` - 管理脚本

### 需要修改的文件
- `gns3server/controller/link.py` - 添加 wireshark 参数和脚本调用
- `gns3server/schemas/controller/links.py` - 添加 wireshark 字段
- `gns3server/api/routes/controller/links.py` - 从 Request 提取 JWT token

## 测试验证

### 1. 手动测试脚本
```bash
# 测试自动检测模式
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  start \
  --project-id "test-project-123" \
  --link-id "link-456" \
  --jwt-token "your-jwt-token"

# 测试手动指定 URL
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  start \
  --project-id "test-project-123" \
  --link-id "link-456" \
  --jwt-token "your-jwt-token" \
  --capture-url "http://192.168.1.100:3080/v3/projects/test-project-123/links/link-456/capture/stream"

# 测试停止
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  stop \
  --project-id "test-project-123" \
  --link-id "link-456"
```

### 2. API 测试
```bash
curl -X POST "http://localhost:3080/v3/projects/{project_id}/links/{link_id}/capture/start" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {jwt_token}" \
  -d '{
    "data_link_type": "DLT_EN10MB",
    "wireshark": true
  }'
```

### 3. 访问 Web UI
```bash
# 脚本返回的 URL 格式
http://100.64.0.x:12300

# 直接在浏览器中访问
```

## 脚本依赖

**requirements.txt:**
```txt
docker>=6.0.0
```

## 部署说明

1. **安装脚本依赖**
```bash
pip3 install docker
```

2. **设置脚本权限**
```bash
chmod +x gns3server/agent/web_wireshark/manage_wireshark.py
```

3. **测试脚本**
```bash
# 手动测试启动和停止
python3 gns3server/agent/web_wireshark/manage_wireshark.py start --help
python3 gns3server/agent/web_wireshark/manage_wireshark.py stop --help
```

4. **重启 gns3-server**
```bash
systemctl restart gns3-server
```

## 优势

1. **极简架构** - 只需要一个脚本 + 一个 WebSocket 代理
2. **统一入口** - 前端统一连接到 gns3server，无需直接访问容器
3. **WebSocket 代理** - gns3server 代理 WebSocket 连接到容器 xpra
4. **独立管理** - 脚本独立管理容器和进程
5. **易于调试** - 可以单独测试脚本
6. **松耦合** - gns3server 只调用脚本，不关心实现
7. **灵活扩展** - 可以轻松修改脚本行为
8. **无需额外方法** - 直接从 API 端点提取 JWT token
9. **智能检测** - 自动检测 GNS3 server 地址（与 gns3-copilot 一致）
10. **向后兼容** - 支持手动指定 URL（特殊场景）
