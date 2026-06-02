SHELL := /usr/bin/env bash
PYTHON ?= python3
LOG ?= logs/latest.log
DASHBOARD ?= output/dashboard.html
SUMMARY_JSON ?= output/summary.json
REPORT_MD ?= output/report.md
HISTORY_JSONL ?= output/history.jsonl
HISTORY_MD ?= output/history.md
HISTORY_HTML ?= output/history.html

.PHONY: all check test dashboard summary report history timeline open open-history clean

all: test check dashboard summary report history timeline

check:
	bash security_check.sh

test:
	PYTHONPATH=. $(PYTHON) -m unittest discover -s tests -v

dashboard:
	$(PYTHON) tools/render_dashboard.py --input $(LOG) --output $(DASHBOARD)

summary:
	$(PYTHON) tools/render_dashboard.py --input $(LOG) --json-output $(SUMMARY_JSON) --no-html

report:
	$(PYTHON) tools/render_dashboard.py --input $(LOG) --markdown-output $(REPORT_MD) --no-html

history:
	$(PYTHON) tools/render_dashboard.py --input $(LOG) --append-history $(HISTORY_JSONL) --no-html

timeline:
	$(PYTHON) tools/render_history.py --input $(HISTORY_JSONL) --markdown-output $(HISTORY_MD) --html-output $(HISTORY_HTML)

open: dashboard
	explorer.exe "$$(wslpath -w $(DASHBOARD))"

open-history: timeline
	explorer.exe "$$(wslpath -w $(HISTORY_HTML))"

clean:
	rm -rf output/*.html output/*.json output/*.md __pycache__ tools/__pycache__ tests/__pycache__
