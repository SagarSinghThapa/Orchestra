import os
from locust import HttpUser, task, between


class OrchestraLoadUser(HttpUser):
    wait_time = between(0.05, 0.2)

    def on_start(self):
        """Authenticates on user spawn using seeded deterministic credentials."""
        self.rate_limit_mode = os.environ.get("ORCHESTRA_LOAD_TEST_RATE_LIMIT", "0") == "1"
        self.auth_headers = {"X-Orchestra-Request": "true"}

        # Login to obtain authentication session cookies
        with self.client.post(
            "/auth/login",
            json={"email": "admin@orchestra.io", "password": "TestPassword123!"},
            headers={"Content-Type": "application/json", "X-Orchestra-Request": "true"},
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                if token:
                    self.auth_headers["Authorization"] = f"Bearer {token}"
                resp.success()
            elif self.rate_limit_mode and resp.status_code == 429:
                resp.success()
            else:
                resp.failure(f"Unexpected login status {resp.status_code}")

    def _check_response(self, resp, success_statuses=(200,)):
        if resp.status_code in success_statuses:
            resp.success()
        elif self.rate_limit_mode and resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
            if retry_after:
                resp.success()
            else:
                resp.failure("429 response missing Retry-After header")
        elif self.rate_limit_mode and resp.status_code == 401 and "Authorization" not in self.auth_headers:
            resp.success()
        else:
            resp.failure(f"Unexpected status code {resp.status_code}")

    @task(4)
    def check_health(self):
        with self.client.get("/health", catch_response=True) as resp:
            self._check_response(resp, (200,))

    @task(3)
    def get_projects(self):
        with self.client.get("/projects", headers=self.auth_headers, catch_response=True) as resp:
            self._check_response(resp, (200, 201))

    @task(2)
    def get_current_user(self):
        with self.client.get("/auth/me", headers=self.auth_headers, catch_response=True) as resp:
            self._check_response(resp, (200,))

    @task(1)
    def get_eval_benchmarks(self):
        with self.client.get("/evaluations/benchmarks", headers=self.auth_headers, catch_response=True) as resp:
            self._check_response(resp, (200,))
