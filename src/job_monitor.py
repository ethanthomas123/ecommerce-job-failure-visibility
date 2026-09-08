from dataclasses import dataclass
import traceback
from typing import Callable

from .infrai_client import InfraiClient


@dataclass
class OrderRequest:
    order_id: str
    customer_email: str


@dataclass
class OrderState:
    order_id: str
    status: str = "checkout_pending"


class JobMonitor:
    def __init__(self, client: InfraiClient, capture: Callable[..., dict] | None = None):
        self.client = client
        self._capture = capture or client.capture

    def process(self, order: OrderRequest, fail_step: str | None = None) -> OrderState:
        state = OrderState(order.order_id)
        for step, next_status in (("checkout", "fulfillment_pending"), ("fulfillment", "receipt_pending"), ("receipt", "customer_notified"), ("customer_update", "customer_notified")):
            try:
                if fail_step == step:
                    raise RuntimeError(f"{step} job rejected the order")
                state.status = next_status
            except Exception as exc:
                state.status = "attention_required"
                self._capture(
                    event_id=f"order-{order.order_id}-{step}",
                    title=f"{step} job failed",
                    message=str(exc),
                    exception=traceback.format_exc(),
                    context={"order_id": order.order_id, "step": step, "customer_email": order.customer_email, "event_id": f"order-{order.order_id}-{step}"},
                )
                break
        return state
