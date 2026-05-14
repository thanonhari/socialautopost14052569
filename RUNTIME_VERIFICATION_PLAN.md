# Runtime Verification Plan

This file defines the minimum runtime checks before treating the current autopost prototype as staging-ready.

## Scope

Verify:

- operator controls (`Start`, `Pause`, `Resume`, `Retry failed`)
- audit artifacts
- webhook replay protection
- YouTube Shorts native adapter token path

## Preconditions

1. Start the app:

```powershell
python app.py
```

2. Prepare a job with:

- completed export package
- at least one highlight clip

3. Set an operator value in the UI toolbar.
4. For live-mode tests, set:

```powershell
$env:SOCIALAUTOPOST_APPROVAL_PHRASE="APPROVED"
$env:SOCIALAUTOPOST_LIVE_MAX_DELIVERIES="3"
```

## Test 1: Dry-Run Autopost

Expected result:

- autopost starts successfully
- `autopost.report.json` is created
- `autopost.queue.json` is created
- `autopost.audit.jsonl` contains `autopost_started` and delivery events

## Test 1B: Live Guardrails

Steps:

1. Switch mode to `Live`.
2. Leave approval text blank or incorrect.
3. Confirm start is rejected.
4. Enter the correct approval phrase.
5. Select enough platforms/clips to exceed `SOCIALAUTOPOST_LIVE_MAX_DELIVERIES`.

Expected result:

- incorrect approval phrase blocks live start
- excessive live delivery count blocks live start

## Test 2: Pause / Resume

Steps:

1. Start autopost on a job with multiple delivery targets.
2. Click `Pause`.
3. Confirm `autopost.control.json` changes to `paused`.
4. Confirm audit log records `operator_pause` and `autopost_paused`.
5. Click `Resume`.
6. Confirm control returns to `active`.
7. Confirm audit log records `operator_resume` and `autopost_resumed`.

Expected result:

- no new deliveries are sent while paused
- queue processing continues after resume

## Test 3: Retry Failed

Steps:

1. Trigger at least one failed or blocked delivery.
2. Click `Retry failed`.
3. Confirm retry thread starts.
4. Confirm audit log records `operator_retry`, `delivery_retry_queued`, and `delivery_retry_finished`.

Expected result:

- only failed/blocked items are retried
- successful items are not re-sent

## Test 4: Webhook Replay Protection

Steps:

1. Run `examples/webhook_receiver_example.py`
2. Send a signed request once
3. Send the same request again with the same `X-Idempotency-Key`

Expected result:

- first request returns success
- second request returns `409` with `replay detected`

## Test 5: Operator Attribution

Expected result:

- `X-Operator` value appears in audit events
- start/pause/resume/retry events all record the same operator value

## Test 6: Shorts Native Token Refresh Path

Preconditions:

- set `SOCIALAUTOPOST_SHORTS_ADAPTER=native`
- provide refresh token, client id, and client secret

Expected result:

- token is refreshed when expired
- `storage/oauth/shorts.token.json` is created/updated
- upload session starts without manual token replacement

## Exit Criteria

The prototype passes runtime verification when:

1. No control action throws an unhandled error
2. Audit artifacts are written consistently
3. Replay protection blocks duplicate requests
4. Retry flow only retries failed/blocked deliveries
5. Native Shorts path can refresh token and reach upload session init
