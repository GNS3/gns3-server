#!/usr/bin/env python3
"""
Web Wireshark Management Script

Manages Web Wireshark containers using Docker and xpra for web-based packet capture.
"""

import sys
import json
import argparse
import logging
import asyncio
import os
from typing import Optional

# Add parent directory to path for imports when run directly
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

try:
    from gns3server.agent.web_wireshark.manager import WebWiresharkManager
except ImportError:
    from manager import WebWiresharkManager

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


async def cmd_start(args) -> int:
    """Start Web Wireshark session.

    Args:
        args: Command line arguments

    Returns:
        Exit code (0 for success)
    """
    manager = WebWiresharkManager()
    try:
        await manager.ensure_network()

        result = await manager.start_wireshark_session(
            project_id=args.project_id,
            link_id=args.link_id,
            jwt_token=args.jwt_token,
            capture_stream_url=args.capture_url,
            image=args.image,
            memory=args.memory,
            cpus=args.cpus,
            pids_limit=args.pids_limit
        )

        print(json.dumps(result, indent=2))
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    finally:
        await manager.close()


async def cmd_stop(args) -> int:
    """Stop Web Wireshark session.

    Args:
        args: Command line arguments

    Returns:
        Exit code (0 for success)
    """
    manager = WebWiresharkManager()
    try:
        await manager.stop_wireshark_session(
            project_id=args.project_id,
            link_id=args.link_id
        )
        print(json.dumps({"status": "stopped"}))
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    finally:
        await manager.close()


async def cmd_stop_all(args) -> int:
    """Stop all Web Wireshark sessions for a project.

    Args:
        args: Command line arguments

    Returns:
        Exit code (0 for success)
    """
    manager = WebWiresharkManager()
    try:
        await manager.stop_all_sessions(project_id=args.project_id)
        print(json.dumps({"status": "all sessions stopped"}))
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    finally:
        await manager.close()


async def cmd_delete(args) -> int:
    """Delete Web Wireshark container.

    Args:
        args: Command line arguments

    Returns:
        Exit code (0 for success)
    """
    manager = WebWiresharkManager()
    try:
        await manager.delete_container(project_id=args.project_id)
        print(json.dumps({"status": "deleted"}))
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    finally:
        await manager.close()


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Web Wireshark container management"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start Web Wireshark session")
    start_parser.add_argument("--project-id", required=True, help="Project ID")
    start_parser.add_argument("--link-id", required=True, help="Link ID")
    start_parser.add_argument("--jwt-token", required=True, help="JWT token")
    start_parser.add_argument(
        "--capture-url",
        help="Capture stream URL (auto-detected if not provided)"
    )
    start_parser.add_argument(
        "--image",
        default="gns3/web-wireshark:latest",
        help="Docker image (default: gns3/web-wireshark:latest)"
    )
    start_parser.add_argument(
        "--memory",
        default="2g",
        help="Memory limit (default: 2g)"
    )
    start_parser.add_argument(
        "--cpus",
        type=float,
        default=1.0,
        help="CPU cores (default: 1.0)"
    )
    start_parser.add_argument(
        "--pids-limit",
        type=int,
        default=1000,
        help="Process limit (default: 1000)"
    )

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop Web Wireshark session")
    stop_parser.add_argument("--project-id", required=True, help="Project ID")
    stop_parser.add_argument("--link-id", required=True, help="Link ID")

    # Stop all command
    stop_all_parser = subparsers.add_parser("stop-all", help="Stop all sessions")
    stop_all_parser.add_argument("--project-id", required=True, help="Project ID")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete container")
    delete_parser.add_argument("--project-id", required=True, help="Project ID")

    return parser


async def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    setup_logging(args.verbose)

    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "stop-all": cmd_stop_all,
        "delete": cmd_delete,
    }

    return await commands[args.command](args)


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
