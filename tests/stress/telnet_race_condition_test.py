#!/usr/bin/env python3
"""
Telnet Server Race Condition Stress Test

This script reproduces the OSError: [Errno 107] bug by rapidly
connecting and disconnecting clients to trigger the race condition
during broadcast operations.

Usage:
    python telnet_race_condition_test.py --host 127.0.0.1 --port 2000 --connections 10
"""

import asyncio
import argparse
import logging
import time
from typing import List, Optional
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)


class TelnetClient:
    """A simple telnet client for stress testing."""

    def __init__(self, client_id: int, host: str, port: int):
        self.client_id = client_id
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False

    async def connect(self) -> bool:
        """Establish telnet connection."""
        try:
            log.debug(f"Client {self.client_id}: Connecting to {self.host}:{self.port}...")
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=5.0
            )
            self.connected = True
            log.debug(f"Client {self.client_id}: Connected successfully")
            return True
        except Exception as e:
            log.warning(f"Client {self.client_id}: Connection failed: {e}")
            return False

    async def send_command(self, command: str) -> bool:
        """Send a command to the telnet server."""
        if not self.writer or not self.connected:
            return False

        try:
            self.writer.write(command.encode() + b'\r\n')
            await asyncio.wait_for(self.writer.drain(), timeout=2.0)
            log.debug(f"Client {self.client_id}: Sent command: {command.strip()}")
            return True
        except Exception as e:
            log.warning(f"Client {self.client_id}: Send failed: {e}")
            return False

    async def receive_response(self, timeout: float = 1.0) -> Optional[str]:
        """Receive response from server (optional)."""
        if not self.reader or not self.connected:
            return None

        try:
            data = await asyncio.wait_for(self.reader.read(1024), timeout=timeout)
            if data:
                response = data.decode('utf-8', errors='ignore')
                log.debug(f"Client {self.client_id}: Received: {response[:50]}...")
                return response
        except asyncio.TimeoutError:
            log.debug(f"Client {self.client_id}: No response (timeout)")
        except Exception as e:
            log.debug(f"Client {self.client_id}: Receive error: {e}")
        return None

    async def disconnect(self, immediate: bool = False):
        """
        Disconnect from telnet server.

        Args:
            immediate: If True, close immediately without graceful shutdown.
                       This simulates abrupt disconnection (TCP FIN/RST).
        """
        if not self.writer:
            return

        try:
            if immediate:
                # Abrupt close - doesn't wait for flush
                self.writer.close()
                # Don't wait for close to complete
                log.debug(f"Client {self.client_id}: Abruptly disconnected")
            else:
                # Graceful close
                self.writer.close()
                await asyncio.wait_for(self.writer.wait_closed(), timeout=1.0)
                log.debug(f"Client {self.client_id}: Gracefully disconnected")
        except Exception as e:
            log.debug(f"Client {self.client_id}: Disconnect error: {e}")
        finally:
            self.connected = False
            self.writer = None
            self.reader = None


async def rapid_fire_client(
    client_id: int,
    host: str,
    port: int,
    iterations: int,
    min_delay: float = 0.001,
    max_delay: float = 0.01,
    receive_before_disconnect: bool = False,
    immediate_disconnect: bool = True,
    device_type: str = "iou-l3"
):
    """
    A client that rapidly connects, sends commands, and disconnects.

    This is designed to trigger the race condition by disconnecting
    quickly while the server might be broadcasting data.

    Args:
        client_id: Unique identifier for this client
        host: Telnet server host
        port: Telnet server port
        iterations: Number of connect/disconnect cycles
        min_delay: Minimum delay before disconnect (seconds)
        max_delay: Maximum delay before disconnect (seconds)
        receive_before_disconnect: Whether to wait for response before disconnect
        immediate_disconnect: Use abrupt close instead of graceful close
        device_type: Type of device (iou-l3, vpcs, etc.)
    """
    success_count = 0
    fail_count = 0

    # Cisco IOS commands for IOU-L3 that trigger broadcast output
    ios_commands = [
        "show ip interface brief",
        "show ip route",
        "show running-config",
        "show version",
        "show protocols",
        "debug ip ospf events",
        "undebug ip ospf events",
        "clear ip ospf process",
    ]

    # Commands that generate significant output
    broadcast_trigger_commands = [
        "show running-config",
        "show ip ospf neighbor",
        "show ip ospf database",
        "show ip protocols",
        "show ip route",
        "write memory",  # This generates "Building configuration..." output
    ]

    for i in range(iterations):
        client = TelnetClient(client_id, host, port)

        # Connect
        if not await client.connect():
            fail_count += 1
            await asyncio.sleep(0.1)
            continue

        # Wait a bit for the telnet session to stabilize
        await asyncio.sleep(0.05)

        # Send commands based on device type
        if device_type == "iou-l3":
            # Use IOS commands that trigger broadcasts
            cmd_index = i % len(broadcast_trigger_commands)
            cmd = broadcast_trigger_commands[cmd_index]

            # Send the command
            await client.send_command(cmd)

            # Small delay to let server start broadcasting
            await asyncio.sleep(0.01)

            # Send another command quickly to increase broadcast chance
            await client.send_command("show ip ospf")

            # Very short delay to increase race condition likelihood
            delay = min_delay + (max_delay - min_delay) * (i % 10) / 10.0
            await asyncio.sleep(delay)

        else:
            # Generic test commands for other devices
            test_commands = ["?", "version", "list"]
            for cmd in test_commands:
                await client.send_command(cmd)

                if receive_before_disconnect:
                    await client.receive_response(timeout=0.1)

                delay = min_delay + (max_delay - min_delay) * (i % 10) / 10.0
                await asyncio.sleep(delay)

        # Disconnect - this is where the race condition triggers
        await client.disconnect(immediate=immediate_disconnect)

        success_count += 1

        # Small delay between iterations
        await asyncio.sleep(0.05)

    log.info(f"Client {client_id}: Completed {success_count}/{iterations} cycles ({fail_count} failures)")
    return success_count, fail_count


async def long_lived_client(
    client_id: int,
    host: str,
    port: str,
    duration: float,
    send_interval: float = 1.0
):
    """
    A long-lived client that stays connected and periodically sends commands.

    This simulates a web console user and should NOT experience issues
    when other clients disconnect rapidly.

    Args:
        client_id: Unique identifier
        host: Telnet server host
        port: Telnet server port
        duration: How long to stay connected (seconds)
        send_interval: Interval between commands (seconds)
    """
    client = TelnetClient(client_id, host, port)

    if not await client.connect():
        log.error(f"Long-lived client {client_id}: Failed to connect")
        return

    log.info(f"Long-lived client {client_id}: Connected for {duration}s")

    start_time = time.time()
    commands_sent = 0

    while time.time() - start_time < duration:
        await asyncio.sleep(send_interval)

        # Send periodic commands to keep connection active
        test_commands = ["?", "help", "status"]
        cmd = test_commands[commands_sent % len(test_commands)]

        if await client.send_command(cmd):
            commands_sent += 1
            await client.receive_response(timeout=0.5)

    await client.disconnect(immediate=False)
    log.info(f"Long-lived client {client_id}: Sent {commands_sent} commands over {duration}s")


async def run_stress_test(
    host: str,
    port: int,
    rapid_clients: int,
    long_lived_clients: int,
    iterations_per_client: int,
    test_duration: float,
    device_type: str = "iou-l3"
):
    """
    Run the stress test with multiple concurrent clients.

    This creates:
    1. Rapid-fire clients that connect/disconnect quickly (triggers bug)
    2. Long-lived clients that stay connected (should not be affected)

    Args:
        host: Telnet server host
        port: Telnet server port
        rapid_clients: Number of rapid connect/disconnect clients
        long_lived_clients: Number of long-lived clients
        iterations_per_client: Iterations per rapid client
        test_duration: Test duration in seconds
        device_type: Type of device (iou-l3, vpcs, etc.)
    """
    log.info("=" * 70)
    log.info("Telnet Server Race Condition Stress Test")
    log.info("=" * 70)
    log.info(f"Target: {host}:{port}")
    log.info(f"Device Type: {device_type}")
    log.info(f"Rapid clients: {rapid_clients} (each {iterations_per_client} iterations)")
    log.info(f"Long-lived clients: {long_lived_clients} (duration: {test_duration}s)")
    log.info(f"Expected behavior: Rapid clients disconnect, long-lived clients unaffected")
    log.info("=" * 70)

    tasks: List[asyncio.Task] = []

    # Start long-lived clients first (simulate web console users)
    for i in range(long_lived_clients):
        task = asyncio.create_task(
            long_lived_client(
                client_id=1000 + i,
                host=host,
                port=port,
                duration=test_duration,
                send_interval=2.0
            )
        )
        tasks.append(task)
        await asyncio.sleep(0.1)  # Stagger connections

    # Give long-lived clients time to establish
    await asyncio.sleep(1.0)

    # Start rapid-fire clients (simulate automated scripts)
    log.info("Starting rapid-fire clients...")
    rapid_tasks: List[asyncio.Task] = []

    for i in range(rapid_clients):
        task = asyncio.create_task(
            rapid_fire_client(
                client_id=i,
                host=host,
                port=port,
                iterations=iterations_per_client,
                min_delay=0.001,  # 1ms - very fast
                max_delay=0.01,   # 10ms - still fast
                receive_before_disconnect=False,  # Don't wait for response
                immediate_disconnect=True,  # Abrupt close
                device_type=device_type
            )
        )
        rapid_tasks.append(task)
        await asyncio.sleep(0.05)  # Slightly stagger starts

    # Wait for all rapid clients to complete
    log.info("Waiting for rapid-fire clients to complete...")
    rapid_results = await asyncio.gather(*rapid_tasks, return_exceptions=True)

    # Calculate statistics
    total_success = 0
    total_failures = 0
    for result in rapid_results:
        if isinstance(result, Exception):
            log.error(f"Rapid client failed with exception: {result}")
        elif isinstance(result, tuple):
            success, failures = result
            total_success += success
            total_failures += failures

    log.info(f"Rapid clients completed: {total_success} success, {total_failures} failures")

    # Wait for long-lived clients to finish
    log.info("Waiting for long-lived clients to complete...")
    await asyncio.gather(*tasks)

    log.info("=" * 70)
    log.info("Stress test completed!")
    log.info("=" * 70)
    log.info("Check GNS3 server logs for:")
    log.info("  - ❌ 'OSError: [Errno 107] Transport endpoint is not connected'")
    log.info("  - ✅ 'Error sending data to client None: ...' (properly handled)")
    log.info("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Stress test for telnet server race condition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic test with IOU-L3 device (default)
  python telnet_race_condition_test.py --port 2000

  # Test with IOU-L3 using OSPF/show commands (triggers broadcast)
  python telnet_race_condition_test.py --port 2000 --device-type iou-l3 --rapid-clients 20

  # Heavy load with many clients
  python telnet_race_condition_test.py --port 2000 --rapid-clients 50 --iterations 100

  # Test with VPCS device
  python telnet_race_condition_test.py --port 2000 --device-type vpcs

Device Types:
  iou-l3   - Cisco IOS L3 router (uses show/run/write commands that trigger broadcast)
  vpcs     - VPCS simulator (simple commands)
  generic  - Generic device (basic test commands)
        """
    )

    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Telnet server host (default: 127.0.0.1)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=2000,
        help='Telnet server port (default: 2000)'
    )

    parser.add_argument(
        '--rapid-clients',
        type=int,
        default=10,
        help='Number of rapid connect/disconnect clients (default: 10)'
    )

    parser.add_argument(
        '--long-lived',
        type=int,
        default=2,
        help='Number of long-lived clients (default: 2)'
    )

    parser.add_argument(
        '--iterations',
        type=int,
        default=50,
        help='Iterations per rapid client (default: 50)'
    )

    parser.add_argument(
        '--duration',
        type=float,
        default=30.0,
        help='Test duration in seconds (default: 30.0)'
    )

    parser.add_argument(
        '--device-type',
        default='iou-l3',
        choices=['iou-l3', 'vpcs', 'generic'],
        help='Device type for commands (default: iou-l3)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        asyncio.run(run_stress_test(
            host=args.host,
            port=args.port,
            rapid_clients=args.rapid_clients,
            long_lived_clients=args.long_lived,
            iterations_per_client=args.iterations,
            test_duration=args.duration,
            device_type=args.device_type
        ))
    except KeyboardInterrupt:
        log.info("Test interrupted by user")
        sys.exit(0)


if __name__ == '__main__':
    main()
