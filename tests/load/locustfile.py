"""Locust load test for GoldDesk.

اجرا:
    locust -f tests/load/locustfile.py --host http://localhost:8000
"""

from locust import HttpUser, between, task


class GoldDeskUser(HttpUser):
    """کاربر معمولی GoldDesk — polling 30s، snapshot 5min."""

    wait_time = between(5, 15)

    @task(10)
    def get_snapshot(self):
        """بیشترین ترافیک — polling هر ۳۰ ثانیه."""
        self.client.get("/api/gold/snapshot", name="snapshot")

    @task(5)
    def get_score(self):
        self.client.get("/api/gold/score", name="score")

    @task(3)
    def get_hot(self):
        """polling سریع — هر ۱۰ ثانیه."""
        self.client.get("/api/gold/hot", name="hot")

    @task(2)
    def get_coins(self):
        self.client.get("/api/gold/coins", name="coins")

    @task(1)
    def get_funds(self):
        self.client.get("/api/gold/funds", name="funds")

    @task(1)
    def get_health(self):
        self.client.get("/api/gold/health", name="health")

    @task(1)
    def get_signals(self):
        self.client.get("/api/gold/signals/recent?limit=5", name="signals")

    @task(1)
    def dca_calc(self):
        self.client.post(
            "/api/gold/dca/plan",
            json={
                "total_capital_irt": 100_000_000,
                "risk_profile": "balanced",
                "current_score": 65,
            },
            name="dca_plan",
        )

    @task(1)
    def portfolio(self):
        self.client.get("/api/gold/portfolio", name="portfolio")

    @task(1)
    def chat(self):
        self.client.post(
            "/api/gold/chat",
            json={"message": "حباب سکه چقدره؟"},
            name="chat",
        )

    @task(1)
    def metrics(self):
        self.client.get("/api/gold/metrics", name="metrics")
