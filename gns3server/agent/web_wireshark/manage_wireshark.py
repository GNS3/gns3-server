#!/usr/bin/env python3
"""
Web Wireshark 管理脚本
负责创建容器、启动 xpra 会话、管理 Wireshark 进程

使用 Docker HTTP API (通过 aiohttp) 而不是 docker SDK
遵循 GNS3 的架构模式
"""

import sys
import json
import argparse
import logging
import asyncio
import re
from typing import Optional

import aiohttp

from gns3server.utils import parse_version

logger = logging.getLogger(__name__)

# 默认 GNS3 server 地址
DEFAULT_GNS3_URL = "http://127.0.0.1:3080"

# Docker API 配置
DOCKER_SOCKET = "/var/run/docker.sock"
DOCKER_MINIMUM_API_VERSION = "1.40"
DOCKER_PREFERRED_API_VERSION = "1.44"


class DockerHTTPClient:
    """Docker HTTP API 客户端，使用 aiohttp 通过 Unix socket 连接"""

    def __init__(self):
        self._connector = None
        self._session = None
        self._connected = False
        self._api_version = DOCKER_MINIMUM_API_VERSION

    async def _get_connector(self):
        """获取 Unix socket 连接器"""
        if self._connector is None or self._connector.closed:
            try:
                self._connector = aiohttp.UnixConnector(DOCKER_SOCKET, limit=None)
            except (aiohttp.ClientError, FileNotFoundError) as e:
                raise RuntimeError(f"Can't connect to Docker daemon: {e}") from e
        return self._connector

    async def _get_session(self):
        """获取 aiohttp 会话"""
        if self._session is None or self._session.closed:
            connector = await self._get_connector()
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def close(self):
        """关闭连接"""
        if self._session and not self._session.closed:
            await self._session.close()
        if self._connector and not self._connector.closed:
            await self._connector.close()

    async def _check_connection(self):
        """检查 Docker 连接并检测 API 版本"""
        if not self._connected:
            try:
                # 获取 Docker 版本信息
                docker_info = await self._request("GET", "version", check_connection=False)
                self._connected = True

                # 解析 API 版本
                api_version = parse_version(docker_info['ApiVersion'])
                docker_version = docker_info["Version"]

                logger.info(f"Connected to Docker {docker_version}, API {api_version}")

                # 检查最小版本要求
                if api_version < parse_version(DOCKER_MINIMUM_API_VERSION):
                    raise RuntimeError(
                        f"Docker version is {docker_version}. "
                        f"GNS3 requires a minimum API version of {DOCKER_MINIMUM_API_VERSION}"
                    )

                # 如果支持，使用首选 API 版本
                preferred_api_version = parse_version(DOCKER_PREFERRED_API_VERSION)
                if api_version >= preferred_api_version:
                    self._api_version = DOCKER_PREFERRED_API_VERSION
                    logger.info(f"Using Docker API version {self._api_version}")
                else:
                    # 使用 Docker daemon 支持的最小 API 版本
                    self._api_version = docker_info['MinAPIVersion']
                    logger.info(f"Using Docker API version {self._api_version} (daemon preferred)")

            except (aiohttp.ClientError, FileNotFoundError) as e:
                self._connected = False
                raise RuntimeError(f"Can't connect to Docker daemon: {e}") from e
            except KeyError as e:
                raise RuntimeError(f"Unexpected Docker API response: missing {e}") from e

    async def _request(self, method: str, endpoint: str, **kwargs):
        """
        发送请求到 Docker API

        Args:
            method: HTTP 方法
            endpoint: API 端点（不包含版本前缀）
            **kwargs: 传递给 aiohttp.request 的其他参数

        Returns:
            响应 JSON 数据
        """
        # 首次请求时检查连接和版本
        check_connection = kwargs.pop('check_connection', True)
        if check_connection and not self._connected:
            await self._check_connection()

        session = await self._get_session()
        url = f"http://docker/{self._api_version}/{endpoint}"

        try:
            async with session.request(method, url, **kwargs) as response:
                if response.status >= 300:
                    error_text = await response.text()
                    raise RuntimeError(f"Docker API error {response.status}: {error_text}")
                if response.status == 204:  # No Content
                    return None
                return await response.json()
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Docker connection error: {e}") from e

    async def create_network(self, name: str, driver: str = "bridge", subnet: str = None):
        """创建 Docker 网络"""
        data = {
            "Name": name,
            "Driver": driver
        }
        if subnet:
            data["IPAM"] = {
                "Config": [{"Subnet": subnet}]
            }
        await self._request("POST", "networks/create", json=data)

    async def get_network(self, name: str):
        """获取网络信息"""
        try:
            return await self._request("GET", f"networks/{name}")
        except RuntimeError as e:
            if "404" in str(e):
                return None
            raise

    async def create_container(self, name: str, image: str, **kwargs):
        """创建容器"""
        data = {
            "Image": image,
            "name": name,
            "HostConfig": {},
            "NetworkingConfig": {}
        }

        # 处理网络配置
        if "network" in kwargs:
            network_name = kwargs.pop("network")
            data["NetworkingConfig"]["EndpointsConfig"] = {
                network_name: {}
            }

        # 处理环境变量
        if "environment" in kwargs:
            data["Env"] = [f"{k}={v}" for k, v in kwargs.pop("environment").items()]

        # 处理资源限制
        if "host_config" in kwargs:
            data["HostConfig"].update(kwargs.pop("host_config"))
        else:
            # 兼容旧的参数格式
            host_config = {}
            if "mem_limit" in kwargs:
                host_config["Memory"] = kwargs.pop("mem_limit")
            if "cpu_quota" in kwargs:
                host_config["NanoCpus"] = kwargs.pop("cpu_quota")
            if "pids_limit" in kwargs:
                host_config["PidsLimit"] = kwargs.pop("pids_limit")
            if "restart_policy" in kwargs:
                host_config["RestartPolicy"] = kwargs.pop("restart_policy")
            data["HostConfig"].update(host_config)

        # 处理健康检查
        if "health_config" in kwargs:
            data["HealthCheck"] = kwargs.pop("health_config")

        # 创建容器
        result = await self._request("POST", "containers/create", params={"name": name}, json=data)
        return result["Id"]

    async def start_container(self, container_id: str):
        """启动容器"""
        await self._request("POST", f"containers/{container_id}/start")

    async def get_container(self, name: str):
        """获取容器信息"""
        try:
            return await self._request("GET", f"containers/{name}/json")
        except RuntimeError as e:
            if "404" in str(e):
                return None
            raise

    async def stop_container(self, container_id: str, timeout: int = 10):
        """停止容器"""
        await self._request("POST", f"containers/{container_id}/stop", params={"t": timeout})

    async def remove_container(self, container_id: str, force: bool = False):
        """删除容器"""
        params = {"force": "true"} if force else {}
        await self._request("DELETE", f"containers/{container_id}", params=params)

    async def exec_create(self, container_id: str, cmd: list, detach: bool = False):
        """创建 exec 实例"""
        data = {
            "AttachStdin": False,
            "AttachStdout": True,
            "AttachStderr": True,
            "Cmd": cmd,
            "Detatch": detach,
            "Tty": False
        }
        result = await self._request("POST", f"containers/{container_id}/exec", json=data)
        return result["Id"]

    async def exec_start(self, exec_id: str, detach: bool = False):
        """启动 exec 实例"""
        data = {"Detach": detach}
        await self._request("POST", f"exec/{exec_id}/start", json=data)


class WebWiresharkManager:
    def __init__(self):
        self.docker = DockerHTTPClient()
        self.network_name = "gns3-wireshark"

    async def close(self):
        """关闭 Docker 连接"""
        await self.docker.close()

    @staticmethod
    def _parse_memory(memory_str: str) -> int:
        """解析内存字符串为字节数

        Args:
            memory_str: 内存字符串，如 "2g", "512m", "1024k"

        Returns:
            内存字节数
        """
        memory_str = memory_str.lower().strip()
        if not memory_str:
            return 0

        # 提取数字和单位
        match = re.match(r'(\d+(?:\.\d+)?)\s*([kmg]b?)?', memory_str)
        if not match:
            raise ValueError(f"Invalid memory format: {memory_str}")

        value = float(match.group(1))
        unit = match.group(2) or 'b'

        # 转换为字节
        multipliers = {
            'b': 1,
            'k': 1024,
            'm': 1024 * 1024,
            'g': 1024 * 1024 * 1024
        }

        unit = unit[0]  # 取第一个字符（处理 'kb', 'mb' 等）
        return int(value * multipliers.get(unit, 1))

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

    async def ensure_network(self):
        """确保 Docker 网络存在"""
        network = await self.docker.get_network(self.network_name)
        if network:
            logger.info(f"Network {self.network_name} already exists")
        else:
            logger.info(f"Creating network {self.network_name}")
            await self.docker.create_network(
                self.network_name,
                driver="bridge",
                subnet="172.28.0.0/16"
            )

    async def get_or_create_container(
        self,
        project_id: str,
        image: str = "gns3/web-wireshark:latest",
        memory: str = "2g",
        memory_swap: str = None,
        cpus: float = 1.0,
        pids_limit: int = 1000
    ) -> str:
        """获取或创建项目的 Web Wireshark 容器

        Args:
            project_id: 项目 ID
            image: Docker 镜像名称
            memory: 内存限制 (默认: 2g)
            memory_swap: 内存交换限制 (默认: 与memory相同)
            cpus: CPU核心数 (默认: 1.0)
            pids_limit: 进程数限制 (默认: 1000)

        Returns:
            容器 ID
        """
        container_name = f"gns3-wireshark-{project_id}"

        container = await self.docker.get_container(container_name)
        if container:
            if container["State"]["Running"]:
                logger.info(f"Container {container_name} already running")
                return container["Id"]
            logger.info(f"Starting existing container {container_name}")
            await self.docker.start_container(container["Id"])
            return container["Id"]

        # 创建新容器
        logger.info(f"Creating new container {container_name} with image {image}")
        logger.info(f"Resources: memory={memory}, cpus={cpus}, pids_limit={pids_limit}")

        # 计算CPU quota (1个CPU = 1000000微秒)
        cpu_quota = int(cpus * 100000)

        # 配置主机配置
        host_config = {
            "Memory": self._parse_memory(memory),
            "MemorySwap": self._parse_memory(memory_swap) if memory_swap else 0,
            "NanoCpus": cpu_quota,
            "PidsLimit": pids_limit,
            "RestartPolicy": {"Name": "unless-stopped"},
            "LogConfig": {
                "Type": "json-file",
                "Config": {
                    "max-size": "10m",
                    "max-file": "3"
                }
            }
        }

        # 健康检查配置
        health_config = {
            "Test": {
                "CMD": ["xpra", "list"],
                "Interval": 30000000000,  # 30秒（纳秒）
                "Timeout": 10000000000,   # 10秒
                "Retries": 3
            }
        }

        container_id = await self.docker.create_container(
            name=container_name,
            image=image,
            network=self.network_name,
            host_config=host_config,
            health_config=health_config,
            environment={
                "XDG_RUNTIME_DIR": "/run/user/1000",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8"
            }
        )

        # 启动容器
        await self.docker.start_container(container_id)
        return container_id

    async def start_wireshark_session(
        self,
        project_id: str,
        link_id: str,
        jwt_token: str,
        capture_stream_url: Optional[str] = None,
        image: str = "gns3/web-wireshark:latest",
        memory: str = "2g",
        memory_swap: Optional[str] = None,
        cpus: float = 1.0,
        pids_limit: int = 1000
    ) -> dict:
        """启动 Web Wireshark 会话

        Args:
            project_id: 项目 ID
            link_id: 链路 ID
            jwt_token: JWT 认证令牌
            capture_stream_url: 抓包流 URL（可选，如果未提供则自动检测）
            image: Docker 镜像名称
            memory: 内存限制 (默认: 2g)
            memory_swap: 内存交换限制 (默认: 与memory相同)
            cpus: CPU核心数 (默认: 1.0)
            pids_limit: 进程数限制 (默认: 1000)
        """
        logger.info(f"Starting Web Wireshark session for link {link_id}")

        # 如果未提供 capture_stream_url，自动构造
        if not capture_stream_url:
            gns3_url = self.detect_gns3_url()
            capture_stream_url = (
                f"{gns3_url}/v3/projects/{project_id}/links/"
                f"{link_id}/capture/stream"
            )
            logger.info(f"Auto-detected capture stream URL: {capture_stream_url}")

        container_id = await self.get_or_create_container(
            project_id,
            image,
            memory,
            memory_swap,
            cpus,
            pids_limit
        )
        container_name = f"gns3-wireshark-{project_id}"

        # 分配 display 和端口
        # 使用 link_id 的 hash 来分配固定的 display 和端口
        link_hash = abs(hash(link_id)) % 100
        display = 100 + link_hash
        port = 12300 + link_hash

        # 启动 xpra 会话
        session_name = f"link-{link_id}"
        logger.info(f"Starting xpra session {session_name} on display :{display}")

        xpra_cmd = [
            "xpra", "start", f":{display}",
            "--xvfb=Xvfb -screen 0 1920x1080x24 +extension RANDR",
            "--html=on",
            f"--bind-tcp=0.0.0.0:{port}",
            f"--session-name={session_name}",
            "--daemon=yes",
            "--dbus-launch=no",
            "--resize-display=yes"
        ]

        exec_id = await self.docker.exec_create(container_id, xpra_cmd, detach=True)
        await self.docker.exec_start(exec_id, detach=True)

        # 等待 xpra 初始化
        await asyncio.sleep(2)

        # 启动 Wireshark 并连接抓包流
        wireshark_cmd = [
            "bash", "-c",
            f"curl -N -H 'Authorization: Bearer {jwt_token}' "
            f"'{capture_stream_url}' | "
            f"wireshark -i - -k -display :{display}"
        ]

        logger.info(f"Starting Wireshark with capture stream: {capture_stream_url}")

        exec_id = await self.docker.exec_create(container_id, wireshark_cmd, detach=True)
        await self.docker.exec_start(exec_id, detach=True)

        # 获取容器 IP
        container = await self.docker.get_container(container_name)
        networks = container["NetworkSettings"]["Networks"]
        container_ip = networks.get(self.network_name, {}).get("IPAddress", "")

        if not container_ip:
            logger.error(f"Container {container_name} has no IP in network {self.network_name}")
            raise RuntimeError("Container has no IP address")

        result = {
            "link_id": link_id,
            "display": display,
            "port": port,
            "url": f"http://{container_ip}:{port}",
            "container_name": container_name,
            "container_id": container_id,
            "session_name": session_name,
            "capture_stream_url": capture_stream_url
        }

        logger.info(f"Web Wireshark session started successfully: {result['url']}")
        return result

    async def stop_wireshark_session(self, project_id: str, link_id: str):
        """停止单个 Web Wireshark 会话"""
        logger.info(f"Stopping Web Wireshark session for link {link_id}")
        try:
            container_name = f"gns3-wireshark-{project_id}"
            container = await self.docker.get_container(container_name)

            if not container:
                logger.warning(f"Container {container_name} not found")
                return

            # 获取 display 编号
            link_hash = abs(hash(link_id)) % 100
            display = 100 + link_hash

            # 停止 xpra 会话
            logger.info(f"Stopping xpra session :{display}")
            xpra_cmd = ["xpra", "stop", f":{display}"]
            exec_id = await self.docker.exec_create(container["Id"], xpra_cmd, detach=True)
            await self.docker.exec_start(exec_id, detach=True)

            logger.info("Web Wireshark session stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping session: {e}")

    async def stop_all_sessions(self, project_id: str):
        """停止项目的所有 Web Wireshark 会话"""
        logger.info(f"Stopping all Web Wireshark sessions for project {project_id}")
        try:
            container_name = f"gns3-wireshark-{project_id}"
            container = await self.docker.get_container(container_name)

            if not container:
                logger.warning(f"Container {container_name} not found")
                return

            # 停止所有 xpra 会话（display 100-199）
            for display in range(100, 200):
                try:
                    xpra_cmd = ["xpra", "stop", f":{display}"]
                    exec_id = await self.docker.exec_create(container["Id"], xpra_cmd, detach=True)
                    await self.docker.exec_start(exec_id, detach=True)
                    logger.info(f"Stopped xpra session :{display}")
                except Exception:
                    # 忽略不存在的会话
                    pass

            logger.info(f"All Web Wireshark sessions stopped for project {project_id}")

        except Exception as e:
            logger.error(f"Error stopping all sessions: {e}")

    async def stop_container(self, project_id: str):
        """停止 Web Wireshark 容器"""
        logger.info(f"Stopping Web Wireshark container for project {project_id}")
        try:
            container_name = f"gns3-wireshark-{project_id}"
            container = await self.docker.get_container(container_name)

            if not container:
                logger.warning(f"Container {container_name} not found")
                return

            if container["State"]["Running"]:
                await self.docker.stop_container(container["Id"], timeout=10)
                logger.info(f"Container {container_name} stopped successfully")
            else:
                logger.info(f"Container {container_name} already stopped")

        except Exception as e:
            logger.error(f"Error stopping container: {e}")

    async def delete_container(self, project_id: str):
        """删除 Web Wireshark 容器"""
        logger.info(f"Deleting Web Wireshark container for project {project_id}")
        try:
            container_name = f"gns3-wireshark-{project_id}"
            container = await self.docker.get_container(container_name)

            if not container:
                logger.warning(f"Container {container_name} not found")
                return

            # 先停止容器
            if container["State"]["Running"]:
                await self.docker.stop_container(container["Id"], timeout=5)

            # 删除容器
            await self.docker.remove_container(container["Id"])
            logger.info(f"Container {container_name} deleted successfully")

        except Exception as e:
            logger.error(f"Error deleting container: {e}")


async def main_async():
    parser = argparse.ArgumentParser(description="Web Wireshark 管理脚本")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="启用详细日志输出（主要用于调试）")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # start 命令
    start_parser = subparsers.add_parser("start", help="启动 Web Wireshark 会话")
    start_parser.add_argument("--project-id", required=True, help="项目 ID")
    start_parser.add_argument("--link-id", required=True, help="链路 ID")
    start_parser.add_argument("--jwt-token", required=True, help="JWT 认证令牌")
    start_parser.add_argument("--capture-url", help="抓包流 URL（可选，未提供则自动检测）")
    start_parser.add_argument("--image", default="gns3/web-wireshark:latest",
                            help="Docker 镜像名称（默认: gns3/web-wireshark:latest）")
    start_parser.add_argument("--memory", default="2g",
                            help="内存限制（默认: 2g）")
    start_parser.add_argument("--memory-swap", default=None,
                            help="内存交换限制（默认: 与memory相同）")
    start_parser.add_argument("--cpus", type=float, default=1.0,
                            help="CPU核心数（默认: 1.0）")
    start_parser.add_argument("--pids-limit", type=int, default=1000,
                            help="进程数限制（默认: 1000）")

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

    # 配置日志（仅在独立运行时通过 --verbose 参数控制）
    if args.verbose:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    if not args.command:
        parser.print_help()
        sys.exit(1)

    manager = WebWiresharkManager()

    try:
        if args.command == "start":
            await manager.ensure_network()
            result = await manager.start_wireshark_session(
                args.project_id,
                args.link_id,
                args.jwt_token,
                getattr(args, 'capture_url', None),  # 可选参数
                getattr(args, 'image', "gns3/web-wireshark:latest"),
                getattr(args, 'memory', "2g"),
                getattr(args, 'memory_swap', None),
                getattr(args, 'cpus', 1.0),
                getattr(args, 'pids_limit', 1000)
            )
            print(json.dumps(result))

        elif args.command == "stop":
            await manager.stop_wireshark_session(args.project_id, args.link_id)

        elif args.command == "stop-sessions":
            await manager.stop_all_sessions(args.project_id)

        elif args.command == "stop-container":
            await manager.stop_container(args.project_id)

        elif args.command == "delete-container":
            await manager.delete_container(args.project_id)

    except Exception as e:
        logger.error(f"Error: {e}")
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
    finally:
        await manager.close()


def main():
    """同步入口函数"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
