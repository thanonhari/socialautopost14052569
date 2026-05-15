# YouTube Shorts Native Staging Checklist

Use this checklist when real Google OAuth credentials are available and you want to verify the native Shorts upload path in staging.

## Goal

Verify that the native Shorts adapter can:

- refresh an expired access token
- persist the refreshed token cache
- initialize the YouTube upload session
- upload a clip successfully
- record the result in autopost artifacts

## Preconditions

1. Use a Google project that is allowed to call the YouTube Data API.
2. Use an OAuth client with a refresh token that belongs to the target YouTube channel.
3. Confirm the access token has the `https://www.googleapis.com/auth/youtube.upload` scope.
4. Prepare a completed job with:
   - `exports/index.json`
   - at least one highlight clip
   - `rights_confirmed = true`
5. Keep the initial test conservative:
   - one clip
   - one platform (`shorts`)
   - `private` visibility

## Required Env Vars

Set these before starting `app.py`:

```powershell
$env:SOCIALAUTOPOST_APPROVAL_PHRASE="APPROVED"
$env:SOCIALAUTOPOST_LIVE_MAX_DELIVERIES="3"
$env:SOCIALAUTOPOST_SHORTS_ADAPTER="native"
$env:SOCIALAUTOPOST_SHORTS_TOKEN="ya29..."
$env:SOCIALAUTOPOST_SHORTS_TOKEN_EXPIRES_AT="1700000000"
$env:SOCIALAUTOPOST_SHORTS_REFRESH_TOKEN="1//..."
$env:SOCIALAUTOPOST_SHORTS_CLIENT_ID="..."
$env:SOCIALAUTOPOST_SHORTS_CLIENT_SECRET="..."
$env:SOCIALAUTOPOST_SHORTS_PRIVACY_STATUS="private"
$env:SOCIALAUTOPOST_SHORTS_CATEGORY_ID="22"
$env:SOCIALAUTOPOST_SHORTS_MADE_FOR_KIDS="false"
python app.py
```

Notes:

- To force refresh-path coverage, set `SOCIALAUTOPOST_SHORTS_TOKEN_EXPIRES_AT` to a timestamp in the past.
- Do not test first with a production-public upload.

## Test 1: Token Refresh Path

Steps:

1. Start the app with an expired `SOCIALAUTOPOST_SHORTS_TOKEN_EXPIRES_AT`.
2. Trigger live autopost for:
   - one clip
   - platform `shorts`
   - valid approval phrase
3. Wait for upload initialization.

Expected result:

- token refresh is attempted automatically
- `storage/oauth/shorts.token.json` is created or updated
- new token expiry is later than the old one
- no manual token replacement is required

## Test 2: Upload Session Init

Expected result:

- no auth error from Google
- native adapter reaches resumable upload session init
- autopost does not fall back to the generic webhook path

Check:

- `autopost.report.json`
- `autopost.audit.jsonl`
- app logs for Shorts native adapter messages

## Test 3: Successful Private Upload

Expected result:

- delivery status becomes `posted`
- `remote_id` is populated
- returned YouTube video URL or video id is captured in report artifacts
- uploaded video appears in YouTube Studio for the connected channel

## Test 4: Artifact Verification

Verify these files under the job directory:

- `autopost.report.json`
- `autopost.queue.json`
- `autopost.control.json`
- `autopost.audit.jsonl`

Expected report fields:

- `platform = "shorts"`
- `dry_run = false`
- `status = "posted"`
- `delivery_state = "posted"`
- `remote_id` present

Expected audit events:

- `autopost_started`
- `delivery_queued`
- `delivery_sending`
- `delivery_finished`
- `autopost_finished`

## Failure Cases To Exercise

Run at least one targeted failure test for each category:

1. Expired or revoked refresh token
Expected result:
   - clear auth failure
   - no false `posted` status

2. Missing client secret or client id
Expected result:
   - request is blocked or fails with actionable error

3. Wrong OAuth scope
Expected result:
   - Google API rejects upload
   - error is preserved in autopost artifacts

4. Network failure during upload
Expected result:
   - delivery status becomes `failed`
   - retry path can pick it up later

## Exit Criteria

Treat the Shorts native path as staging-verified only when all are true:

1. Expired access token refreshes successfully.
2. Token cache persists to `storage/oauth/shorts.token.json`.
3. One private Shorts upload completes successfully.
4. `autopost.report.json` records `posted` with a remote identifier.
5. Audit artifacts are complete and consistent.

## Cleanup

After testing:

1. Remove or rotate temporary staging credentials if needed.
2. Delete unwanted private test uploads from the channel.
3. Confirm no token values were written into tracked files or commits.
