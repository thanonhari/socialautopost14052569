# Security Policy

## Supported Versions

This repository is currently maintained on the `main` branch only.

## Reporting a Vulnerability

Please do not open public issues for sensitive vulnerabilities.

Report privately by email:

- thanonhari@gmail.com

Include:

1. Vulnerability summary
2. Reproduction steps
3. Affected files/endpoints
4. Suggested mitigation (if available)

## Secret Handling

- Never commit tokens, cookies, or credentials.
- Use environment variables or your organization secret manager.
- Rotate secrets immediately if exposure is suspected.

## Webhook Security Baseline

For live autopost webhooks:

- Verify `X-Signature` and `X-Timestamp`
- Enforce timestamp skew window
- Add replay protection (nonce/idempotency TTL store)
