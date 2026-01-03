import subprocess
import time
import os
import pandas as pd


# Configuration
FRAMEWORKS = ["fastapi", "flask", "django"]
POOL_MODES = ["direct", "pooled"]
USER_COUNTS = [1000]  # Concurrency levels
SPAWN_RATE = 50  # Users per second
RUN_TIME = "60s"  # Test duration per scenario, e.g., "1m" or "60s"
RESULTS_DIR = "results"


def run_command(command, cwd=None):
    """Runs a shell command and raises error if it fails."""
    print(f"Executing: {command}")
    subprocess.check_call(command, shell=True, cwd=cwd)


def cleanup():
    """Stops and removes all containers."""
    print("Cleaning up containers...")
    subprocess.run("docker-compose down -v", shell=True, check=False)


def wait_for_service(service_name, port, timeout=60):
    """
    Rudimentary wait for service.
    In a real scenario, we might retry curling the health check endpoint.
    For now, we just sleep a bit or use `docker-compose exec` to check.
    """
    print(f"Waiting for {service_name} to stabilize...")
    time.sleep(30)  # Increased wait for DB init


def ensure_db_ready():
    """Ensure Postgres is running and Seeded."""
    print("Starting Postgres...")
    run_command("docker-compose up -d postgres")
    wait_for_service("postgres", 5432)

    # Check if we need to seed
    # We can check by querying the users count
    try:
        check_cmd = "docker-compose exec -T postgres psql -U postgres -d benchmark_db -c 'SELECT count(*) FROM users'"
        output = subprocess.check_output(check_cmd, shell=True).decode()
        if "0" in output.splitlines()[2].strip():  # Rudimentary parsing
            raise Exception("Empty Table")
        print("Data exists, skipping seed.")
    except Exception:
        print("Seeding database...")
        # Run seed.py locally using venv python
        # Ensure postgres port 5432 is accessible (it is mapped in docker-compose)
        run_command("./venv/bin/python database/seed.py")


def run_scenario(framework, pool_mode, users):
    """Runs a single benchmark scenario."""
    filename = f"{framework}_{pool_mode}_{users}u"
    result_file = os.path.join(RESULTS_DIR, f"{filename}_stats.csv")

    if os.path.exists(result_file):
        print(f"Skipping {filename}: Results already exist.")
        return

    print(f"--- Running Scenario: {framework} | {pool_mode} | {users} Users ---")

    service_name = f"{framework}-app"

    try:
        # 1. Start Infrastructure
        # Always restart database/pgbouncer to ensure clean state?
        # Or keep DB running? Keeping DB running is faster, but might carry over caching effects.
        # For this benchmark, let's keep DB running but restart pgbouncer if needed.
        # Actually, restart app to clear app-level pools.

        # Cleanup override if it exists from a previous crash
        if os.path.exists("docker-compose.override.yml"):
            os.remove("docker-compose.override.yml")

        # Clean start for App
        run_command(f"docker-compose stop {service_name}")
        run_command(f"docker-compose rm -f {service_name}")

        # Strategy: generate `docker-compose.override.yml` for the current run.
        with open("docker-compose.override.yml", "w") as f:
            val = "1" if pool_mode == "pooled" else "0"
            f.write(f"""
version: '3.8'
services:
  {service_name}:
    environment:
      USE_CONNECTION_POOLING: '{val}'
""")

        if pool_mode == "pooled":
            run_command("docker-compose up -d pgbouncer", cwd=None)

        run_command(f"docker-compose up -d {service_name}")
        wait_for_service(
            service_name,
            8000
            if framework == "fastapi"
            else (8001 if framework == "django" else 8002),
        )

        # 2. Run Locust
        # Host is localhost:port mapped
        port = (
            8000 if framework == "fastapi" else 8001 if framework == "django" else 8002
        )
        host_url = f"http://localhost:{port}"

        cmd = [
            "./venv/bin/locust",
            "-f",
            "locust/locustfile.py",
            "--headless",
            "-u",
            str(users),
            "-r",
            str(SPAWN_RATE),
            "--run-time",
            RUN_TIME,
            "--host",
            host_url,
            "--csv",
            f"{RESULTS_DIR}/{filename}",
            "--only-summary",  # Less log spam
        ]

        print(f"Starting Locust: {' '.join(cmd)}")
        subprocess.check_call(cmd)

    except Exception as e:
        print(f"FAILED Scenario {filename}: {e}")
    finally:
        # Cleanup override
        if os.path.exists("docker-compose.override.yml"):
            os.remove("docker-compose.override.yml")


def generate_summary():
    """Reads all CSV results and creates a summary report."""
    print("Generating Summary Report...")
    summary_data = []

    # Iterate over files in RESULTS_DIR
    for filename in os.listdir(RESULTS_DIR):
        if filename.endswith("_stats.csv"):
            # Filename format: {framework}_{pool_mode}_{users}u_stats.csv
            # We strip _stats.csv
            base_name = filename.replace("_stats.csv", "")
            parts = base_name.split("_")
            if len(parts) != 3:
                continue

            framework = parts[0]
            pool_mode = parts[1]
            users = parts[2].replace("u", "")

            # Read CSV
            try:
                df = pd.read_csv(os.path.join(RESULTS_DIR, filename))
                # Get Aggregated stats (usually last row or specific row 'Aggregated')
                # Locust stats csv has 'Name' column. We want 'Aggregated'.
                agg = df[df["Name"] == "Aggregated"].iloc[0]

                summary_data.append(
                    {
                        "Framework": framework,
                        "Pool Mode": pool_mode,
                        "Users": int(users),
                        "RPS": agg["Requests/s"],
                        "P95 Latency (ms)": agg["95%"],
                        "P99 Latency (ms)": agg["99%"],
                        "Failures/s": agg["Failures/s"],
                    }
                )
            except Exception as e:
                print(f"Failed to process {filename}: {e}")

    if summary_data:
        summary_df = pd.DataFrame(summary_data)
        summary_df = summary_df.sort_values(by=["Framework", "Pool Mode", "Users"])

        # Save to CSV
        summary_df.to_csv("summary_report.csv", index=False)

        # Save to Markdown
        with open("README.md", "a") as f:
            f.write("\n## Benchmark Results\n")
            f.write(summary_df.to_markdown(index=False))

        print("Summary Report Saved to summary_report.csv and appended to README.md")


def main():
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)

    cleanup()

    try:
        ensure_db_ready()

        for framework in FRAMEWORKS:
            for pool_mode in POOL_MODES:
                for users in USER_COUNTS:
                    run_scenario(framework, pool_mode, users)
                    # Cool down
                    time.sleep(5)

        generate_summary()

    except KeyboardInterrupt:
        print("Interrupted by user.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cleanup()
        print("Benchmark completed.")


if __name__ == "__main__":
    main()
