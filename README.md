# QQQ Regime Signal Bot

See `docs/SPEC.md` for the initial strategy. This README covers deployment.

## Layout

- `main.py` — daily signal computation; pushes Pushover notification on regime flip; writes `last_state.json`.
- `dashboard.py` — ad-hoc sanity check; prints live raw signal + last committed state. No notifications.
- `last_state.json` — committed state (created on first run; do not edit by hand).
- `.github/workflows/cron.yml` — daily Mon-Fri schedule at 21:30 UTC plus manual dispatch.
- `requirements.txt` — Python deps.

## Repo secrets

Set in GitHub → Settings → Secrets and variables → Actions:

- `FRED_API_KEY`
- `PUSHOVER_USER_KEY`
- `PUSHOVER_API_TOKEN`

## Local sanity check

```sh
python -m venv .venv && .venv/bin/pip install -r requirements.txt
echo "FRED_API_KEY=..." >> .env
echo "PUSHOVER_USER_KEY=..." >> .env
echo "PUSHOVER_API_TOKEN=..." >> .env
set -a; source .env; set +a; .venv/bin/python dashboard.py
```

## Schedule

Cron is `30 21 * * 1-5` (UTC). That's 4:30pm EST in winter, 5:30pm EDT in summer — always after the 4:00pm ET equity close. Trading-day holidays are handled at runtime: if `yfinance` returns a close date already in `last_state.json`, the script no-ops without touching the buffer.

## Hysteresis

Asymmetric:

- raw_signal goes risk-off → deployed flips immediately.
- raw_signal goes risk-on → deployed flips only after 3 consecutive trading days of risk-on raw_signal.

The rolling buffer of the last 3 raw_signal values lives in `last_state.json` under `buffer`.

## Manual trigger

Actions → cron → Run workflow.
