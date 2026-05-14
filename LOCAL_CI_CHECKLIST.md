# Local CI Checklist

Use this checklist while GitHub Actions is unavailable.

## Purpose

Run the minimum checks locally before commit, push, or PR.

## 1) Update branch

```powershell
git checkout main
git pull
git checkout -b feat/<topic>
```

If already on a feature branch:

```powershell
git checkout <your-branch>
git pull --rebase origin main
```

## 2) Python compile check

```powershell
python -m py_compile app.py examples\webhook_receiver_example.py
```

Pass condition:

- no output
- exit code `0`

## 3) Git diff sanity check

```powershell
git status
git diff --stat
```

Pass condition:

- only intended files changed
- no runtime artifacts or secrets included

## 4) Secret leakage check

```powershell
rg -n "TOKEN=|SECRET=|AIza|ghp_|github_pat_|-----BEGIN" .
```

Pass condition:

- no real secret values are present in tracked files

## 5) Runtime artifact check

```powershell
git status --short
```

Pass condition:

- no `storage/` artifacts staged
- no `.env` files staged
- no token cache files staged

## 6) Manual app smoke check

Start app:

```powershell
python app.py
```

Open:

- `http://127.0.0.1:8765`

Smoke check:

- jobs list loads
- existing job details open
- autopost panel renders
- no immediate browser error for the current page

## 7) If touching autopost logic

Verify against:

- [RUNTIME_VERIFICATION_PLAN.md](/D:/Projects/socialautopost/RUNTIME_VERIFICATION_PLAN.md:1)

Minimum autopost checks:

- start dry-run
- pause/resume
- retry failed
- audit file written

## 8) Commit gate

Only commit when all checks above pass.

Suggested flow:

```powershell
git add .
git commit -m "..."
git push -u origin <branch>
```

## Temporary Team Rule

Until GitHub Actions is restored:

1. Do not merge PRs without paste/screenshot evidence of local compile check.
2. Do not merge autopost changes without referencing the runtime verification items executed.
3. Do not rely on repo green status as proof of validation.
