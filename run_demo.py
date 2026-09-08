import os

from src.infrai_client import InfraiClient
from src.job_monitor import JobMonitor, OrderRequest


def main() -> None:
    order = OrderRequest(order_id="demo-1001", customer_email="buyer@example.com")
    monitor = JobMonitor(InfraiClient())
    state = monitor.process(order, fail_step=os.getenv("DEMO_FAIL_STEP"))
    print(f"order {state.order_id}: {state.status}")


if __name__ == "__main__":
    main()

