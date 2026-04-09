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
                subnet="172.28.0.0/16"
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


if __name__ == "__main__":
    main()
