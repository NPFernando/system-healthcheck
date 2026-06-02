# System Healthcheck Index

Artifacts for the local WSL/Hermes security healthcheck project.

## Primary commands

```bash
# Run full healthcheck
bash /home/npfernando/code/personal/system-healthcheck/security_check.sh

# Generate HTML dashboard
cd /home/npfernando/code/personal/system-healthcheck
make dashboard

# Generate JSON summary
cd /home/npfernando/code/personal/system-healthcheck
make summary

# Generate Markdown report
cd /home/npfernando/code/personal/system-healthcheck
make report

# Append history record
cd /home/npfernando/code/personal/system-healthcheck
make history

# Render history timeline
cd /home/npfernando/code/personal/system-healthcheck
make timeline

# Run all validation/report generation
cd /home/npfernando/code/personal/system-healthcheck
make all

# Run tests
cd /home/npfernando/code/personal/system-healthcheck
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

## Key files

- `security_check.sh` - dependency-light WSL/Hermes security/readiness checker
- `tools/render_dashboard.py` - static HTML dashboard renderer
- `tests/test_render_dashboard.py` - stdlib unit tests for renderer parsing and escaping
- `logs/latest.log` - latest healthcheck output
- `output/dashboard.html` - generated dashboard
- `output/summary.json` - generated machine-readable summary
- `output/report.md` - generated pasteable Markdown report
- `output/history.jsonl` - append-only compact status history
- `output/history.md` - generated Markdown history timeline
- `output/history.html` - generated HTML history timeline
- `Makefile` - convenience targets for checks, tests, dashboard, summary, report, history, timeline, and cleanup
- `/home/npfernando/.hermes/scripts/security_healthcheck_watchdog.sh` - Hermes cron wrapper that refreshes logs, dashboard, summary, report, and history timelines

## Current expected status

- Healthcheck: OK
- Hermes smoke: HERMES_OK
- SearXNG: localhost-only and container-hardened
- Caddy: localhost-only
- SSH: localhost-only
- Apt updates: 0 pending
