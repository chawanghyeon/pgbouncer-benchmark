import subprocess
import time
import os
import threading
import json
import statistics
import pandas as pd


# Configuration
FRAMEWORKS = ["fastapi", "flask", "django"]
POOL_MODES = ["direct", "pooled"]
USER_COUNTS = [500, 1000]  # Concurrency levels
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
    """
    print(f"Waiting for {service_name} to stabilize...")
    time.sleep(30)  # Increased wait for DB init


def ensure_db_ready():
    """Ensure Postgres is running and Seeded."""
    print("Starting Postgres...")
    run_command("docker-compose up -d postgres")
    wait_for_service("postgres", 5432)

    # Check if we need to seed
    try:
        check_cmd = "docker-compose exec -T postgres psql -U postgres -d benchmark_db -c 'SELECT count(*) FROM users'"
        output = subprocess.check_output(check_cmd, shell=True).decode()
        if "0" in output.splitlines()[2].strip():
            raise Exception("Empty Table")
        print("Data exists, skipping seed.")
    except Exception:
        print("Seeding database...")
        run_command("./venv/bin/python database/seed.py")


def monitor_resources(stop_event, containers, results):
    """
    Monitors Docker container resources in a background thread.
    stores result in `results` dict.
    """
    stats_data = {c: {"cpu": [], "mem": []} for c in containers}

    while not stop_event.is_set():
        try:
            # Get stats for all running containers
            cmd = [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{.Name}},{{.CPUPerc}},{{.MemPerc}}",
            ]
            output = subprocess.check_output(cmd).decode().strip().splitlines()

            for line in output:
                try:
                    name, cpu_str, mem_str = line.split(",")
                    if name in containers:
                        # Parse CSS percentage (10.5%) -> 10.5
                        cpu_val = float(cpu_str.strip("%"))
                        mem_val = float(mem_str.strip("%"))
                        stats_data[name]["cpu"].append(cpu_val)
                        stats_data[name]["mem"].append(mem_val)
                except ValueError:
                    continue  # Skip if parsing fails

        except Exception as e:
            print(f"Monitor Warning: {e}")

        time.sleep(1)

    # Calculate averages
    for c in containers:
        cpus = stats_data[c]["cpu"]
        mems = stats_data[c]["mem"]
        if cpus:
            results[c] = {
                "avg_cpu": statistics.mean(cpus),
                "avg_mem": statistics.mean(mems),
            }
        else:
            results[c] = {"avg_cpu": 0, "avg_mem": 0}


def run_scenario(framework, pool_mode, users):
    """Runs a single benchmark scenario."""
    filename = f"{framework}_{pool_mode}_{users}u"
    result_file = os.path.join(RESULTS_DIR, f"{filename}_stats.csv")
    resource_file = os.path.join(RESULTS_DIR, f"{filename}_resources.json")

    if os.path.exists(result_file):
        print(f"Skipping {filename}: Results already exist.")
        return

    print(f"--- Running Scenario: {framework} | {pool_mode} | {users} Users ---")

    service_name = f"{framework}-app"

    try:
        # 1. Start Infrastructure
        if os.path.exists("docker-compose.override.yml"):
            os.remove("docker-compose.override.yml")

        # Clean start for App
        run_command(f"docker-compose stop {service_name}")
        run_command(f"docker-compose rm -f {service_name}")

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

        # Wait for service to be ready
        wait_for_service(
            service_name,
            8000
            if framework == "fastapi"
            else (8001 if framework == "django" else 8002),
        )

        # 2. Start Resource Monitor
        stop_event = threading.Event()
        resource_results = {}
        target_containers = ["postgres", service_name]

        monitor_thread = threading.Thread(
            target=monitor_resources,
            args=(stop_event, target_containers, resource_results),
        )
        monitor_thread.start()

        # 3. Run Locust
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
            "--only-summary",
        ]

        print(f"Starting Locust: {' '.join(cmd)}")
        subprocess.check_call(cmd)

        # 4. Stop Monitor and Save
        stop_event.set()
        monitor_thread.join()

        with open(resource_file, "w") as f:
            json.dump(resource_results, f)

    except Exception as e:
        print(f"FAILED Scenario {filename}: {e}")
        stop_event.set()  # ensure thread stops
    finally:
        if os.path.exists("docker-compose.override.yml"):
            os.remove("docker-compose.override.yml")


def generate_summary():
    """Reads all CSV results and creates a summary report."""
    print("Generating Summary Report...")
    summary_data = []

    for filename in os.listdir(RESULTS_DIR):
        if filename.endswith("_stats.csv"):
            base_name = filename.replace("_stats.csv", "")
            parts = base_name.split("_")
            if len(parts) != 3:
                continue

            framework = parts[0]
            pool_mode = parts[1]
            users = parts[2].replace("u", "")

            # Read Stats
            try:
                df = pd.read_csv(os.path.join(RESULTS_DIR, filename))
                agg = df[df["Name"] == "Aggregated"].iloc[0]

                # Read Resources
                res_path = os.path.join(RESULTS_DIR, f"{base_name}_resources.json")
                db_cpu = db_mem = app_cpu = app_mem = 0
                if os.path.exists(res_path):
                    with open(res_path, "r") as f:
                        res = json.load(f)
                        if "postgres" in res:
                            db_cpu = round(res["postgres"]["avg_cpu"], 1)
                            db_mem = round(res["postgres"]["avg_mem"], 1)

                        app_container = f"{framework}-app"
                        if app_container in res:
                            app_cpu = round(res[app_container]["avg_cpu"], 1)
                            app_mem = round(res[app_container]["avg_mem"], 1)

                summary_data.append(
                    {
                        "Framework": framework,
                        "Pool Mode": pool_mode,
                        "Users": int(users),
                        "RPS": agg["Requests/s"],
                        "P95 Latency (ms)": agg["95%"],
                        "P99 Latency (ms)": agg["99%"],
                        "Failures/s": agg["Failures/s"],
                        "DB CPU (%)": db_cpu,
                        "DB Mem (%)": db_mem,
                        "App CPU (%)": app_cpu,
                        "App Mem (%)": app_mem,
                    }
                )
            except Exception as e:
                print(f"Failed to process {filename}: {e}")

    if summary_data:
        summary_df = pd.DataFrame(summary_data)
        summary_df = summary_df.sort_values(by=["Framework", "Pool Mode", "Users"])

        # Save to CSV
        summary_df.to_csv("summary_report.csv", index=False)

        print("Summary Report Saved to summary_report.csv")


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
