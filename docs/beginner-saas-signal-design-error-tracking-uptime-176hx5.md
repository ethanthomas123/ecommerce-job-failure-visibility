# Beginner SaaS Signal Design: Error Tracking, Uptime Monitoring, and Cron Heartbeats

A monitor can observe only evidence that crosses its boundary. **Short answer: use error tracking to explain failed executions, uptime monitoring to test external reachability, cron heartbeats to detect missing completion, and healthchecks to report a narrowly defined readiness condition.** A beginner SaaS often needs more than one because a green endpoint cannot prove that yesterday's scheduled export finished.

The useful question is not, "Which monitoring tool wins?" Ask what event must exist when the system is correct, who can observe it, and how late it may be before a human needs to act. That turns four overlapping labels into four clean contracts.

## How should a beginner SaaS combine error tracking, uptime monitoring, cron heartbeats, and healthchecks?

Start with the failure that produces no event. A scheduler can be paused. A deployment can omit a job registration. A worker can lose its trigger before application code begins. In each case, exception capture has nothing to report because there was no executing exception to capture. This is the defining silent-failure problem: absence must be compared with an expectation.

Now draw the system in words. An external probe crosses the public network and requests a service endpoint. Request-handling code emits errors when an execution fails. A readiness endpoint evaluates the conditions promised by its contract. Off to the side, a scheduler starts a named job; the job performs its durable side effect; only then does it emit completion evidence. Four observers. Four vantage points.

The distinctions are compact:

| Signal | Question it answers | Strong evidence | Important blind spot |
|---|---|---|---|
| Error tracking | Did executing code report a failure? | An exception, rejection, or explicitly captured error with context | Work that never started may emit nothing |
| Uptime monitoring | Can an outside observer reach the service and get the expected response? | A probe result from outside the application boundary | A responsive web endpoint says little about an unrelated batch job |
| Cron heartbeat | Did expected work reach a named milestone before its deadline? | A start, progress, or completion event compared with a schedule | It doesn't measure request-path quality between job runs |
| Healthcheck | Is this process ready or alive under a declared contract? | The exact process and dependency conditions the endpoint evaluates | Anything omitted from that contract remains invisible |

Keep those contracts separate even when one platform stores all four signals. Error tracking is event-led. Uptime monitoring is probe-led. A heartbeat is expectation-led. A healthcheck is contract-led. Combining their dashboards may be convenient; combining their meanings is where alerts become confusing.

## Replace “quiet means healthy” with a completion contract

The before model is tempting: the scheduler logs `job started`, no exception appears, and the team treats the run as successful. Quiet looks green. It isn't proof.

The after model names the expected outcome. For a nightly account export, that might be: one run for the business date, a file committed to durable storage, and a completion event received by 07:00 in the service's chosen time zone. The heartbeat deadline follows the business promise, while error events explain failures encountered on the path. An external uptime probe continues to answer a different question about the user-facing service.

Put the completion event after the durable side effect. This placement matters more than the transport. If the worker signals completion at startup and then fails during the write, the heartbeat stays green while the business result is absent. If it signals inside `finally`, it proves only that control left the block. Neither matches the word "completed."

There is one more edge: retries. The worker can commit its result and lose the network before the completion signal is acknowledged. A retry may then repeat the write. Use a stable run identity and make the business operation idempotent; send the same identity with the eventual completion evidence. Exactly-once delivery is not something a heartbeat creates. The design should tolerate repeated attempts.

Deadlines deserve the same care. A job scheduled every hour doesn't automatically need an alert at minute 61. Runtime variation, delayed scheduler dispatch, deployments, and the actual consumer deadline all affect the grace window. There is no universal five-minute answer. I'm not sure a static threshold is even appropriate for input-sized batch work until runtime distributions are available; instrument duration first, then choose a window the team can defend.

This is the crisp change:

- Before: no error arrived, so success is assumed.
- After: required completion evidence did not arrive by its deadline, so the run is late.

Small wording change. Huge operational difference.

## A TypeScript pattern that keeps the evidence honest

The following example has no vendor SDK and no invented endpoint. Its interfaces make each boundary visible: the ledger owns idempotency, error capture owns diagnostic context, and the heartbeat sink receives completion only after the write resolves.

```ts
type JobRun = {
  jobName: string;
  runId: string;
  scheduledFor: string;
};

interface ErrorTracker {
  capture(error: unknown, run: JobRun): Promise<void>;
}

interface CompletionSink {
  complete(run: JobRun): Promise<void>;
}

interface Ledger {
  writeOnce(idempotencyKey: string, amountCents: number): Promise<void>;
}

export async function postDailyCharge(
  run: JobRun,
  accountId: string,
  amountCents: number,
  ledger: Ledger,
  errors: ErrorTracker,
  completions: CompletionSink,
): Promise<void> {
  try {
    const idempotencyKey = `${run.jobName}:${run.runId}:${accountId}`;
    await ledger.writeOnce(idempotencyKey, amountCents);
    await completions.complete(run);
  } catch (error: unknown) {
    await errors.capture(error, run);
    throw error;
  }
}
```

Don't move `completions.complete` into `finally`. The distinction is deliberate. The scheduler should retain control of retry timing, so the function rethrows after recording diagnostic evidence. The stable idempotency key lets the ledger define what a duplicate attempt means rather than asking the monitoring layer to solve data consistency.

Test the silence.

A focused suite needs at least four paths. On success, one durable write precedes one completion. When the write rejects, error capture runs, completion does not, and the rejection escapes to the scheduler. When the same run is attempted again, `writeOnce` preserves the single business effect. Finally, withhold completion in a non-production test and verify that the late-run alert reaches the intended owner. The last test checks the negative space that ordinary unit tests skip.

Healthchecks stay outside this worker. A liveness check can answer whether the process should be restarted. A readiness check can answer whether the instance should receive traffic. Those are operational decisions, so each endpoint should test only conditions relevant to that decision. Making every probe query every batch record creates coupling, load, and ambiguous incidents.

For logging pipelines, the same separation applies. An appender transports log events; it cannot manufacture an event for code that never ran. If logs feed error diagnosis, treat delivery behavior, buffering, and failure handling as part of that pipeline's contract rather than assuming a log line is a scheduled-work monitor.

## What should alerts say, and when is this model unsuitable?

An alert should name the broken promise, not the telemetry brand. "Daily export has no completion for business date 2026-08-06; due at 07:00 UTC" is actionable. "Heartbeat failed" forces the responder to rediscover the job, milestone, deadline, and customer consequence while the clock is running. Attach the run identity, last observed state, owner, and a link to internal diagnostic context. Keep customer identifiers out of high-cardinality monitor names.

Route each signal by consequence. An external availability failure may page the service owner because users cannot connect. A newly captured exception may create or group a defect for investigation. A late payroll or settlement job may page because its deadline is firm, while a delayed analytics refresh may open a lower-urgency ticket. Severity comes from impact and time sensitivity, not from which collector emitted the event.

There are real limits. Cron heartbeats are not suitable for consumers with no expected cadence; use queue age, consumer lag, or a synthetic end-to-end event when irregular arrivals make silence normal. Error tracking alone can be enough for a local operation that a person starts and immediately verifies. Uptime probes add little to a component with no externally reachable contract. Stick with a narrow readiness check when a traffic router needs a fast admission decision, and don't turn it into an audit of every downstream workflow.

More signals also create work: ownership, retention, access control, alert routing, test fixtures, and cardinality limits. Start with the user-visible promise and the scheduled outcomes that can fail silently. Add telemetry only when someone can state the decision it will drive.

The final design review can be brief. For every important operation, ask: What proves it ran? What proves it finished? What sees it from outside? What deadline matters? If two answers point to the same green light, inspect that assumption. One signal rarely proves four different things.

## Sources

- https://logback.qos.ch/manual/appenders.html
