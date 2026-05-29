#!/usr/bin/env python3
"""
Benchmark test for GET /projects performance on a running GNS3 server

This test connects to an already running GNS3 server and measures
the response time of the GET /projects endpoint.
"""

import asyncio
import time
import argparse
import sys
import uuid
from pathlib import Path

import httpx

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def create_test_projects(base_url, headers, count, prefix="perf_test_project"):
    """Create specified number of test projects"""
    print(f"Creating {count} test projects...")

    async with httpx.AsyncClient() as client:
        batch_size = 50

        for batch_start in range(0, count, batch_size):
            batch_end = min(batch_start + batch_size, count)
            batch_tasks = []

            for i in range(batch_start, batch_end):
                name = f"{prefix}_{i}_{uuid.uuid4().hex[:8]}"
                task = client.post(
                    f"{base_url}/projects",
                    headers=headers,
                    json={"name": name}
                )
                batch_tasks.append(task)

            results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for i, result in enumerate(results, batch_start):
                if hasattr(result, 'status_code'):
                    if result.status_code == 201:
                        print(f"  Created project {i+1}/{count}")
                    else:
                        print(f"  Failed to create project {i+1}: {result.status_code}")
                else:
                    print(f"  Error creating project {i+1}: {result}")


async def cleanup_test_projects(base_url, headers, prefix="perf_test_project"):
    """Clean up test projects"""
    print("Cleaning up test projects...")
    cleanup_start = time.time()

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(f"{base_url}/projects", headers=headers)
            if response.status_code == 200:
                projects = response.json()

                test_projects = [p for p in projects if p.get('name', '').startswith(prefix)]
                print(f"  Found {len(test_projects)} test projects to delete")

                batch_size = 50
                total_deleted = 0
                for batch_start in range(0, len(test_projects), batch_size):
                    batch_end = min(batch_start + batch_size, len(test_projects))
                    batch_tasks = []

                    for project in test_projects[batch_start:batch_end]:
                        task = client.delete(
                            f"{base_url}/projects/{project['project_id']}",
                            headers=headers
                        )
                        batch_tasks.append(task)

                    results = await asyncio.gather(*batch_tasks, return_exceptions=True)

                    for i, result in enumerate(results, batch_start):
                        project = test_projects[i]
                        if hasattr(result, 'status_code') and result.status_code == 204:
                            total_deleted += 1

        elapsed = time.time() - cleanup_start
        print(f"  Deleted {total_deleted} projects in {elapsed:.1f}s ({total_deleted/elapsed:.0f} projects/sec)")

    except Exception as e:
        print(f"Error during cleanup: {type(e).__name__}: {e}")


async def benchmark_get_projects(base_url, headers, project_count, iterations=10, prefix="perf_test_project"):
    """Benchmark GET /projects endpoint"""

    print(f"\n{'='*60}")
    print(f"GET /projects Performance Benchmark")
    print(f"{'='*60}")
    print(f"Server: {base_url}")
    print(f"{'='*60}\n")

    if project_count > 0:
        await create_test_projects(base_url, headers, project_count, prefix)

    # Warm-up run
    print("Performing warm-up run...")
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(f"{base_url}/projects", headers=headers)
            print(f"  Response status: {response.status_code}")
            if response.status_code != 200:
                print(f"Error during warm-up: HTTP {response.status_code}")
                print(f"Response text: {response.text[:200]}")
                return
            actual_count = len(response.json())
            print(f"  Warm-up successful: {actual_count} projects")
    except Exception as e:
        print(f"Error during warm-up: {type(e).__name__}: {e}")
        return

    # Benchmark runs
    response_times = []
    project_counts = []

    print(f"\nRunning {iterations} benchmark iterations...")
    async with httpx.AsyncClient(timeout=120.0) as client:
        for i in range(iterations):
            start_time = time.time()
            try:
                response = await client.get(f"{base_url}/projects", headers=headers)
                end_time = time.time()

                if response.status_code == 200:
                    elapsed_ms = (end_time - start_time) * 1000
                    projects = response.json()
                    response_times.append(elapsed_ms)
                    project_counts.append(len(projects))
                    print(f"  Iteration {i+1}: {elapsed_ms:.2f}ms ({len(projects)} projects)")
                else:
                    print(f"  Iteration {i+1}: ERROR {response.status_code}")
            except Exception as e:
                print(f"  Iteration {i+1}: Exception - {type(e).__name__}: {str(e)}")

    # Cleanup test projects
    if project_count > 0:
        await cleanup_test_projects(base_url, headers, prefix)

    # Calculate statistics
    if response_times:
        avg_time = sum(response_times) / len(response_times)
        min_time = min(response_times)
        max_time = max(response_times)
        median_time = sorted(response_times)[len(response_times) // 2]
        avg_project_count = sum(project_counts) / len(project_counts) if project_counts else 0

        print(f"\n{'='*60}")
        if project_count > 0:
            print(f"Results for {project_count} projects (created specifically):")
        else:
            print(f"Results for existing projects (~{avg_project_count:.0f} per request):")
        print(f"{'='*60}")
        print(f"Average: {avg_time:.2f}ms")
        print(f"Median:  {median_time:.2f}ms")
        print(f"Min:     {min_time:.2f}ms")
        print(f"Max:     {max_time:.2f}ms")
        print(f"{'='*60}")

        # Performance assessment
        if avg_time < 100:
            status = "EXCELLENT"
        elif avg_time < 500:
            status = "ACCEPTABLE"
        elif avg_time < 2000:
            status = "SLOW"
        else:
            status = "CRITICAL"

        print(f"Status: {status}")

        # Throughput: projects returned per second
        if project_counts and sum(response_times) > 0:
            total_projects = sum(project_counts)
            total_seconds = sum(response_times) / 1000
            projects_per_second = total_projects / total_seconds
            print(f"Throughput: {projects_per_second:.1f} projects/sec")
        print(f"{'='*60}\n")

        return {
            'project_count': project_count,
            'avg_time_ms': avg_time,
            'median_time_ms': median_time,
            'min_time_ms': min_time,
            'max_time_ms': max_time,
            'projects_per_second': projects_per_second if project_counts and sum(response_times) > 0 else 0
        }


async def main():
    parser = argparse.ArgumentParser(description='Benchmark GET /projects performance on running server')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='GNS3 server host')
    parser.add_argument('--port', type=int, default=3080, help='GNS3 server port')
    parser.add_argument('--username', type=str, required=True, help='Username for authentication')
    parser.add_argument('--password', type=str, required=True, help='Password for authentication')
    parser.add_argument('--project-counts', type=int, nargs='+', default=[10, 50, 100],
                        help='Numbers of projects to test (default: 10 50 100)')
    parser.add_argument('--iterations', type=int, default=10,
                        help='Number of iterations per test (default: 10)')
    parser.add_argument('--full-scale', action='store_true',
                        help='Run full scale test: 10, 50, 100, 200, 500 projects')
    parser.add_argument('--no-cleanup', action='store_true',
                        help='Do not create/cleanup test projects (use existing projects)')
    parser.add_argument('--prefix', type=str, default='perf_test_project',
                        help='Project name prefix for test/cleanup (default: perf_test_project)')
    parser.add_argument('--cleanup-only', action='store_true',
                        help='Only clean up test projects, do not run benchmark')

    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}/v3"

    # Login to get JWT token
    print(f"Connecting to {base_url}")
    print(f"Authenticating as {args.username}...")

    try:
        async with httpx.AsyncClient() as client:
            login_response = await client.post(
                f"{base_url}/access/users/login",
                data={"username": args.username, "password": args.password}
            )

        if login_response.status_code != 200:
            print(f"Login failed: {login_response.status_code}")
            print(f"Response: {login_response.text}")
            sys.exit(1)

        token_data = login_response.json()
        access_token = token_data.get("access_token")
        headers = {"Authorization": f"Bearer {access_token}"}
        print("Authentication successful")

    except Exception as e:
        print(f"Error connecting to server: {e}")
        print("Make sure GNS3 server is running and accessible")
        sys.exit(1)

    # Determine test scope
    if args.full_scale:
        project_counts = [10, 50, 100, 200, 500]
    else:
        project_counts = args.project_counts

    # If cleanup-only flag, just clean up and exit
    if args.cleanup_only:
        await cleanup_test_projects(base_url, headers, args.prefix)
        return

    # If no-cleanup flag, test with existing projects as-is
    if args.no_cleanup:
        project_counts = [0]
        args.iterations = 20

    results = []

    for count in project_counts:
        try:
            result = await benchmark_get_projects(base_url, headers, count, args.iterations, args.prefix)
            if result:
                results.append(result)
        except Exception as e:
            print(f"Error testing {count} projects: {e}")

    # Summary
    if len(results) > 1:
        print(f"\n{'='*60}")
        print("Summary - Performance Scaling")
        print(f"{'='*60}")
        print(f"{'Projects':<12} {'Avg (ms)':<12} {'Status':<12}")
        print(f"{'-'*40}")
        for r in results:
            avg = r['avg_time_ms']
            if avg < 100:
                status = "EXCELLENT"
            elif avg < 500:
                status = "ACCEPTABLE"
            elif avg < 2000:
                status = "SLOW"
            else:
                status = "CRITICAL"
            print(f"{r['project_count']:<12} {avg:<12.2f} {status:<12}")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
