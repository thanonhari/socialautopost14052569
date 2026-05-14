# Contributing

## Branching

- Do not commit directly to `main`.
- Create a feature branch: `feat/<topic>` or `fix/<topic>`.

## Pull Requests

Each PR should include:

1. What changed
2. Why it changed
3. How it was tested
4. Any migration/config steps

## Local Checks

Run before opening a PR:

```powershell
python -m py_compile app.py examples\webhook_receiver_example.py
```

## Commit Style

Use concise, imperative commit messages, for example:

- `Add replay cache for webhook receiver`
- `Add retry queue state transitions for autopost`

## Security Rules

- Never commit secrets or runtime artifacts from `storage/`.
- Keep `.gitignore` updated for local-only files.
