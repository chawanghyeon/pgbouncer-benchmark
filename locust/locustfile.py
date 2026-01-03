from locust import HttpUser, task, between

class BenchmarkUser(HttpUser):
    # No wait time between tasks to max out the target system
    # If we want a more realistic user behavior, we'd add wait_time = between(1, 5)
    # But for a backend benchmark, we usually want to saturate the server.
    wait_time = between(0, 0)

    @task
    def db_test(self):
        with self.client.get("/benchmark/db-test", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
