import argparse
import csv
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


def parse_duration_seconds(duration_str: str) -> int:
    s = duration_str.strip().lower()
    if s.endswith("s"):
        return int(s[:-1])
    elif s.endswith("m"):
        return int(s[:-1]) * 60
    elif s.endswith("h"):
        return int(s[:-1]) * 3600
    else:
        return int(s)


def validate_load_parameters(users: int, spawn_rate: int, duration_str: str) -> int:
    """Strictly validates load parameters against workstation safety caps.

    Does NOT silently clamp values. Rejects unsafe parameters with ValueError.
    """
    if users < 1 or users > 50:
        raise ValueError(f"Invalid --users {users}: must be between 1 and 50.")
    if spawn_rate < 1 or spawn_rate > 10:
        raise ValueError(f"Invalid --spawn-rate {spawn_rate}: must be between 1 and 10.")
    try:
        dur_sec = parse_duration_seconds(duration_str)
    except Exception as exc:
        raise ValueError(f"Invalid --duration format '{duration_str}': {exc}") from exc

    if dur_sec < 1 or dur_sec > 60:
        raise ValueError(f"Invalid --duration {duration_str}: duration must be between 1s and 60s.")
    return dur_sec


def run():
    parser = argparse.ArgumentParser(description="Orchestra Bounded Local Load Testing Harness")
    parser.add_argument("--users", type=int, default=20, help="Simulated concurrent users (max 50)")
    parser.add_argument("--spawn-rate", type=int, default=5, help="Spawn rate users/sec (max 10)")
    parser.add_argument("--duration", type=str, default="30s", help="Load test duration e.g. 30s (max 60s)")
    parser.add_argument("--host", type=str, default="http://127.0.0.1:8001", help="Target API host")
    parser.add_argument("--rate-limit", action="store_true", help="Enable rate limiting validation scenario (Scenario B)")
    args = parser.parse_args()

    # Enforce strict validation: reject out-of-bound parameters explicitly
    try:
        validate_load_parameters(args.users, args.spawn_rate, args.duration)
    except ValueError as err:
        print(f"[Validation Error] {err}", file=sys.stderr)
        sys.exit(2)

    users = args.users
    spawn_rate = args.spawn_rate
    host = args.host

    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    results_dir = repo_root / "test-results" / "load"
    results_dir.mkdir(parents=True, exist_ok=True)

    if args.rate_limit:
        csv_prefix = (results_dir / "locust_saturation_stats").as_posix()
        html_report = (results_dir / "saturation_report.html").as_posix()
        summary_path = results_dir / "saturation_summary.json"
        scenario_title = "LOCAL BENCHMARK (NON-PRODUCTION) — SCENARIO B (RATE LIMIT SATURATION)"
    else:
        csv_prefix = (results_dir / "locust_stats").as_posix()
        html_report = (results_dir / "report.html").as_posix()
        summary_path = results_dir / "load_summary.json"
        scenario_title = "LOCAL BENCHMARK (NON-PRODUCTION) — SCENARIO A (THROUGHPUT BASELINE)"

    print("=" * 70)
    print(f" {scenario_title} ")
    print("=" * 70)
    print(f"Target:      {host}")
    print(f"Concurrency: {users} users @ {spawn_rate} users/sec")
    print(f"Duration:    {args.duration}")
    print(f"Artifacts:   {results_dir.as_posix()}")
    print("-" * 70)

    # 1. Bootstrap test database
    bootstrap_candidates = [
        repo_root / "frontend" / "tests" / "e2e" / "fixtures" / "bootstrap_test_db.py",
        repo_root / "tests" / "e2e" / "fixtures" / "bootstrap_test_db.py",
    ]
    bootstrap_script = next((p for p in bootstrap_candidates if p.exists()), None)
    if bootstrap_script:
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
        if args.rate_limit:
            env["RATE_LIMIT_BACKEND"] = "memory"
            env["RATE_LIMIT_AUTH_LIMIT"] = "100"
            env["RATE_LIMIT_READ_LIMIT"] = "20"
            env["RATE_LIMIT_READ_WINDOW_SECONDS"] = "60"
        else:
            env["RATE_LIMIT_AUTH_LIMIT"] = "100"
            env["RATE_LIMIT_READ_LIMIT"] = "500"

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
        summary_data = {
            "title": scenario_title,
            "scenario": "B - Rate Limit Saturation" if args.rate_limit else "A - Throughput Baseline",
            "target": host,
            "concurrency_users": users,
            "spawn_rate": spawn_rate,
            "duration": args.duration,
            "exit_code": result.returncode,
            "report_html": html_report,
            "rate_limit_enabled": args.rate_limit,
            "status": "PASS" if result.returncode == 0 else "FAIL",
        }

        # If stats CSV exists, parse metrics
        stats_csv_path = Path(f"{csv_prefix}_stats.csv")
        if stats_csv_path.exists():
            try:
                with open(stats_csv_path, mode="r", encoding="utf-8") as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        if row.get("Name") == "Aggregated":
                            summary_data["total_requests"] = int(row.get("Request Count", 0))
                            summary_data["failure_count"] = int(row.get("Failure Count", 0))
                            summary_data["requests_per_s"] = float(row.get("Requests/s", 0.0))
                            summary_data["p50_ms"] = float(row.get("50%", 0.0))
                            summary_data["p90_ms"] = float(row.get("90%", 0.0))
                            summary_data["p95_ms"] = float(row.get("95%", 0.0))
                            summary_data["max_ms"] = float(row.get("Max Response Time", 0.0))
            except Exception as ex:
                summary_data["stats_parse_error"] = str(ex)

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
