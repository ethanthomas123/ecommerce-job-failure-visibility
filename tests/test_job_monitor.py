from src.job_monitor import JobMonitor, OrderRequest


def test_receipt_failure_needs_attention_and_is_captured():
    captured = []
    monitor = JobMonitor(client=None, capture=lambda **payload: captured.append(payload))

    state = monitor.process(OrderRequest("ord-7", "buyer@example.com"), fail_step="receipt")

    assert state.status == "attention_required"
    assert captured[0]["context"]["event_id"] == "order-ord-7-receipt"
    assert captured[0]["context"]["step"] == "receipt"
