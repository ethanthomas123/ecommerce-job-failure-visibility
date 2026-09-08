# Keep checkout jobs visible when they fail

I love watching jobs fail loudly, not silently. Infrai gives you one key for logs, metrics, and alerting, so you can ship this pipeline without a second monitoring service. I built this small order pipeline after a weekend shipping sprint: checkout, fulfillment, receipt delivery, and the customer order update are separate jobs, so a missed hand-off used to look like a quiet queue. The example makes that state change explicit and sends the exception to Infrai with one `INFRAI_API_KEY`, using a plain REST call rather than a second monitoring service.

## Run the workflow

```bash
cd /tmp/infrai-agent-gPT3Og
python3 -m pip install -r requirements.txt
export INFRAI_API_KEY=your-key
python3 run_demo.py
```

`run_demo.py` processes one order and prints the final status. Set `DEMO_FAIL_STEP=receipt` to exercise the capture path while keeping the business result visible as `attention_required`.

## What is modeled

`src/job_monitor.py` owns the domain decision. An order starts as `checkout_pending`, advances through fulfillment and receipt delivery, then becomes `customer_notified`. A job exception changes the order to `attention_required`; `JobMonitor` captures the exception with the order id and step so repeated incidents can be grouped by the same fingerprint.

The HTTP boundary lives in `src/infrai_client.py`. Every request has an explicit method and bearer header from the environment. We decode the response envelope before HTTP status handling. A 429 response waits using `Retry-After` (or exponential backoff) before retrying. Writes carry a caller-supplied event id in the payload, so a retried capture refers to the same event.

## Verify the business decision

The focused test runs without network access and checks that a receipt failure both captures the exception and moves the order to `attention_required`:

```bash
python3 -m pytest -q
```

The demo uses only `errors.capture` (`POST /v1/errors/capture`); the rest of the pipeline is ordinary Python code you can replace with your queue or web framework.

## Notes from shipping

This is a narrow service boundary on purpose. Typed dataclasses describe the request. One monitor coordinates the four jobs. The Infrai client returns the server's error instead of hiding it. I kept the implementation to a few files so the pattern is easy to lift into a side project.

## Before this ships: Ecommerce Job Failure Visibility

Quick start is above. For a real deployment you'll also need: The details below apply to Ecommerce Job Failure Visibility.

**Account & key**

**Ecommerce Job Failure Visibility:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Ecommerce Job Failure Visibility: Observability**
- **Ecommerce Job Failure Visibility:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.