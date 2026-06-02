#!/usr/bin/env python3
"""Render timeline artifacts from system-healthcheck JSONL history.

No third-party dependencies. Consumes compact records produced by
render_dashboard.py --append-history.
"""

from __future__ import annotations

import argparse
import html
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class HistoryRecord:
    generated_at: str
    status: str
    warnings: int | None
    failures: int | None
    ok_count: int | None
    warn_count: int | None
    fail_count: int | None
    source: str | None


def load_history(path: Path) -> list[HistoryRecord]:
    records: list[HistoryRecord] = []
    if not path.exists():
        return records

    for line_number, line in enumerate(path.read_text(errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
        records.append(
            HistoryRecord(
                generated_at=str(payload.get("generated_at") or "UNKNOWN"),
                status=str(payload.get("status") or "UNKNOWN"),
                warnings=payload.get("warnings"),
                failures=payload.get("failures"),
                ok_count=payload.get("ok_count"),
                warn_count=payload.get("warn_count"),
                fail_count=payload.get("fail_count"),
                source=payload.get("source"),
            )
        )
    return records


def summarize(records: Iterable[HistoryRecord]) -> dict[str, object]:
    items = list(records)
    status_counts: dict[str, int] = {}
    for record in items:
        status_counts[record.status] = status_counts.get(record.status, 0) + 1
    latest = items[-1] if items else None
    return {
        "total_records": len(items),
        "status_counts": status_counts,
        "latest_status": latest.status if latest else None,
        "latest_generated_at": latest.generated_at if latest else None,
        "latest_warnings": latest.warnings if latest else None,
        "latest_failures": latest.failures if latest else None,
    }


def status_class(status: str) -> str:
    normalized = status.upper()
    if normalized == "OK":
        return "ok"
    if normalized == "WARN":
        return "warn"
    if normalized == "FAIL":
        return "fail"
    return "unknown"


def render_markdown(records: list[HistoryRecord], source: Path) -> str:
    summary = summarize(records)
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    lines = [
        "# WSL Security Healthcheck History",
        "",
        f"Generated at: `{generated_at}`",
        f"Source history: `{source}`",
        "",
        "## Summary",
        "",
        f"- Total records: `{summary['total_records']}`",
        f"- Latest status: `{summary['latest_status'] or 'UNKNOWN'}`",
        f"- Latest generated at: `{summary['latest_generated_at'] or 'UNKNOWN'}`",
        f"- Latest warnings: `{summary['latest_warnings'] if summary['latest_warnings'] is not None else '?'}`",
        f"- Latest failures: `{summary['latest_failures'] if summary['latest_failures'] is not None else '?'}`",
        f"- Status counts: `{summary['status_counts']}`",
        "",
        "## Timeline",
        "",
        "| # | Generated at | Status | Warnings | Failures | OK checks | Source |",
        "|---:|---|---|---:|---:|---:|---|",
    ]
    for index, record in enumerate(records, start=1):
        lines.append(
            "| {index} | `{generated_at}` | `{status}` | {warnings} | {failures} | {ok_count} | `{source}` |".format(
                index=index,
                generated_at=record.generated_at,
                status=record.status,
                warnings=record.warnings if record.warnings is not None else "?",
                failures=record.failures if record.failures is not None else "?",
                ok_count=record.ok_count if record.ok_count is not None else "?",
                source=record.source or "",
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_html(records: list[HistoryRecord], source: Path) -> str:
    summary = summarize(records)
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    rows = []
    for index, record in enumerate(records, start=1):
        css = status_class(record.status)
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td><code>{html.escape(record.generated_at)}</code></td>"
            f"<td><span class='pill {css}'>{html.escape(record.status)}</span></td>"
            f"<td>{html.escape(str(record.warnings if record.warnings is not None else '?'))}</td>"
            f"<td>{html.escape(str(record.failures if record.failures is not None else '?'))}</td>"
            f"<td>{html.escape(str(record.ok_count if record.ok_count is not None else '?'))}</td>"
            f"<td><code>{html.escape(record.source or '')}</code></td>"
            "</tr>"
        )
    rows_html = "\n".join(rows) or "<tr><td colspan='7'>No history records found.</td></tr>"
    status_counts = html.escape(json.dumps(summary["status_counts"], sort_keys=True))
    latest_status = str(summary["latest_status"] or "UNKNOWN")
    latest_css = status_class(latest_status)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WSL Security Healthcheck History</title>
  <style>
    :root {{ color-scheme: dark; --bg:#0b1020; --panel:#121a2f; --text:#e8eefc; --muted:#a8b3cf; --border:#263654; --ok:#2dd4bf; --warn:#fbbf24; --fail:#fb7185; --unknown:#94a3b8; }}
    body {{ margin:0; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 32px 20px 56px; }}
    h1 {{ margin: 0 0 8px; font-size: clamp(2rem, 4vw, 3.2rem); letter-spacing: -0.04em; }}
    .muted {{ color: var(--muted); }}
    .cards {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(170px,1fr)); gap:14px; margin:24px 0; }}
    .card {{ border:1px solid var(--border); border-radius:18px; background:var(--panel); padding:16px; }}
    .label {{ display:block; color:var(--muted); text-transform:uppercase; font-size:.78rem; letter-spacing:.08em; }}
    .value {{ display:block; margin-top:8px; font-size:1.5rem; font-weight:800; }}
    table {{ width:100%; border-collapse: collapse; border:1px solid var(--border); background:var(--panel); border-radius:14px; overflow:hidden; }}
    th, td {{ border-bottom:1px solid var(--border); padding:10px 12px; text-align:left; vertical-align:top; }}
    th {{ color:var(--muted); font-size:.8rem; text-transform:uppercase; letter-spacing:.06em; }}
    code {{ color:#bfdbfe; }}
    .pill {{ display:inline-block; padding:3px 9px; border-radius:999px; font-weight:800; }}
    .pill.ok {{ background:rgba(45,212,191,.15); color:var(--ok); }}
    .pill.warn {{ background:rgba(251,191,36,.15); color:var(--warn); }}
    .pill.fail {{ background:rgba(251,113,133,.15); color:var(--fail); }}
    .pill.unknown {{ background:rgba(148,163,184,.15); color:var(--unknown); }}
  </style>
</head>
<body>
  <main>
    <h1>WSL Security Healthcheck History</h1>
    <div class="muted">Generated at {html.escape(generated_at)} from <code>{html.escape(str(source))}</code></div>
    <section class="cards">
      <div class="card"><span class="label">Total records</span><span class="value">{summary['total_records']}</span></div>
      <div class="card"><span class="label">Latest status</span><span class="value"><span class="pill {latest_css}">{html.escape(latest_status)}</span></span></div>
      <div class="card"><span class="label">Latest warnings</span><span class="value">{html.escape(str(summary['latest_warnings'] if summary['latest_warnings'] is not None else '?'))}</span></div>
      <div class="card"><span class="label">Latest failures</span><span class="value">{html.escape(str(summary['latest_failures'] if summary['latest_failures'] is not None else '?'))}</span></div>
      <div class="card"><span class="label">Status counts</span><span class="value"><code>{status_counts}</code></span></div>
    </section>
    <table>
      <thead><tr><th>#</th><th>Generated at</th><th>Status</th><th>Warnings</th><th>Failures</th><th>OK checks</th><th>Source</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </main>
</body>
</html>
"""


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render healthcheck history timeline")
    parser.add_argument("--input", type=Path, default=Path("output/history.jsonl"), help="Input history JSONL")
    parser.add_argument("--markdown-output", type=Path, default=Path("output/history.md"), help="Output Markdown path")
    parser.add_argument("--html-output", type=Path, default=Path("output/history.html"), help="Output HTML path")
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output")
    parser.add_argument("--no-html", action="store_true", help="Skip HTML output")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    records = load_history(args.input)
    if not args.no_markdown:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(records, args.input))
        print(f"wrote {args.markdown_output}")
    if not args.no_html:
        args.html_output.parent.mkdir(parents=True, exist_ok=True)
        args.html_output.write_text(render_html(records, args.input))
        print(f"wrote {args.html_output}")
    summary = summarize(records)
    print(
        "records={total_records} latest_status={latest_status} latest_warnings={latest_warnings} latest_failures={latest_failures}".format(
            **summary
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
