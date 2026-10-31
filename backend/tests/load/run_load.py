import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def is_server_reachable(host: str) -> bool:
    try:
        with urllib.request.urlopen(f"{host}/health", timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def run():
    parser = argparse.ArgumentParser(description="Orchestra Bounded Local Load Testing Harness")
    parser.add_argument("--users", type=int, default=20, help="Simulated concurrent users (max 50)")
    parser.add_argument("--spawn-rate", type=int, default=5, help="Spawn rate users/sec (max 10)")
    parser.add_argument("--duration", type=str, default="30s", help="Load test duration e.g. 30s (max 60s)")
    parser.add_argument("--host", type=str, default="http://127.0.0.1:8001", help="Target API host")
    parser.add_argument("--rate-limit", action="store_true", help="Enable rate limiting validation scenario")
    args = parser.parse_args()

    # Enforce strict workstation safety caps
    users = min(args.users, 50)
    spawn_rate = min(args.spawn_rate, 10)
    host = args.host

    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    results_dir = repo_root / "test-results" / "load"
    results_dir.mkdir(parents=True, exist_ok=True)

    csv_prefix = (results_dir / "locust_stats").as_posix()
    html_report = (results_dir / "report.html").as_posix()

    print("=" * 70)
    print(" LOCAL BENCHMARK (NON-PRODUCTION) — BOUNDED LOAD HARNESS ")
    print("=" * 70)
    print(f"Target:      {host}")
    print(f"Concurrency: {users} users @ {spawn_rate} users/sec")
    print(f"Duration:    {args.duration}")
    print(f"Artifacts:   {results_dir.as_posix()}")
    print("-" * 70)

    # 1. Bootstrap test database
    bootstrap_script = repo_root / "tests" / "e2e" / "fixtures" / "bootstrap_test_db.py"
    if bootstrap_script.exists():
        print("[Setup] Seeding deterministic test database personas...")
        subprocess.run([sys.executable, str(bootstrap_script)], check=True, cwd=str(repo_root))

    # 2. Check or spin up server if not running
    server_process = None
    if not is_server_reachable(host):
        print(f"[Setup] Starting local backend uvicorn server on {host}...")
        env = os.environ.copy()
        env["ENVIRONMENT"] = "test"
        env["DATABASE_URL"] = f"sqlite:///{(repo_root / 'test-results' / 'orchestra_e2e.db').as_posix()}"
        env["JWT_SECRET"] = "test-jwt-secret-key-minimum-32-chars-long"
        env["LLM_PROVIDER"] = "test"
        env["EMBEDDING_PROVIDER"] = "test"
        env["RATE_LIMIT_ENABLED"] = "true" if args.rate_limit else "false"

        port = 8001
        try:
            port = int(host.split(":")[-1].replace("/", ""))
        except Exception:
            pass

        server_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=str(repo_root / "backend"),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        for _ in range(30):
            if is_server_reachable(host):
                print("[Setup] Backend server is ready.")
                break
            time.sleep(0.5)
        else:
            if server_process:
                server_process.kill()
            raise RuntimeError(f"Backend server failed to start on {host}")

    try:
        # 3. Execute locust
        locust_file = Path(__file__).resolve().parent / "locustfile.py"
        locust_env = os.environ.copy()
        if args.rate_limit:
            locust_env["ORCHESTRA_LOAD_TEST_RATE_LIMIT"] = "1"

        cmd = [
            sys.executable,
            "-m",
            "locust",
            "-f",
            str(locust_file),
            "--headless",
            "-u",
            str(users),
            "-r",
            str(spawn_rate),
            "--run-time",
            args.duration,
            "--host",
            host,
            "--csv",
            csv_prefix,
            "--html",
            html_report,
        ]

        print(f"[Execution] Running Locust load test: {' '.join(cmd)}")
        result = subprocess.run(cmd, env=locust_env, cwd=str(repo_root))

        # 4. Generate JSON summary report
        summary_path = results_dir / "load_summary.json"
        summary_data = {
            "title": "LOCAL BENCHMARK (NON-PRODUCTION)",
            "target": host,
            "concurrency_users": users,
            "spawn_rate": spawn_rate,
            "duration": args.duration,
            "exit_code": result.returncode,
            "report_html": html_report,
            "status": "PASS" if result.returncode == 0 else "FAIL",
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2)

        print("-" * 70)
        print(f"[Results] Load summary written to: {summary_path.as_posix()}")
        print(f"[Results] HTML report written to: {html_report}")
        print("=" * 70)

        if result.returncode != 0:
            sys.exit(result.returncode)

    finally:
        if server_process:
            print("[Teardown] Stopping spawned uvicorn server...")
            server_process.kill()


if __name__ == "__main__":
    run()
