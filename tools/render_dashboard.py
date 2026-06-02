#!/usr/bin/env python3
"""Render a standalone HTML dashboard from a security_check.sh log.

No third-party dependencies. Does not read secrets; it only consumes the already-redacted
healthcheck log output.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

SECTION_RE = re.compile(r"^==== (?P<name>.+?) ====$")
SUMMARY_RE = re.compile(r"^(warnings|failures|status)=(.*)$")
STATUS_LINE_RE = re.compile(r"^\[(OK|WARN|FAIL)\] (.*)$")


@dataclass(frozen=True)
class Section:
    name: str
    lines: list[str]


@dataclass(frozen=True)
class ParsedLog:
    source: Path
    sections: list[Section]
    warnings: int | None
    failures: int | None
    status: str | None
    ok_count: int
    warn_count: int
    fail_count: int


def parse_log(path: Path) -> ParsedLog:
    current_name = "Preamble"
    current_lines: list[str] = []
    sections: list[Section] = []
    warnings: int | None = None
    failures: int | None = None
    status: str | None = None
    ok_count = warn_count = fail_count = 0

    for raw_line in path.read_text(errors="replace").splitlines():
        line = raw_line.rstrip("\n")
        section_match = SECTION_RE.match(line)
        if section_match:
            if current_lines or current_name != "Preamble":
                sections.append(Section(current_name, current_lines))
            current_name = section_match.group("name")
            current_lines = []
            continue

        status_match = STATUS_LINE_RE.match(line)
        if status_match:
            level = status_match.group(1)
            if level == "OK":
                ok_count += 1
            elif level == "WARN":
                warn_count += 1
            elif level == "FAIL":
                fail_count += 1

        summary_match = SUMMARY_RE.match(line)
        if summary_match:
            key, value = summary_match.groups()
            if key == "warnings":
                warnings = int(value)
            elif key == "failures":
                failures = int(value)
            elif key == "status":
                status = value.strip()

        current_lines.append(line)

    if current_lines or current_name != "Preamble":
        sections.append(Section(current_name, current_lines))

    return ParsedLog(
        source=path,
        sections=sections,
        warnings=warnings,
        failures=failures,
        status=status,
        ok_count=ok_count,
        warn_count=warn_count,
        fail_count=fail_count,
    )


def status_class(status: str | None) -> str:
    normalized = (status or "UNKNOWN").upper()
    if normalized == "OK":
        return "ok"
    if normalized == "WARN":
        return "warn"
    if normalized == "FAIL":
        return "fail"
    return "unknown"


def render_badge(label: str, value: object, css_class: str) -> str:
    return (
        f'<div class="badge {css_class}">'
        f'<span class="badge-label">{html.escape(label)}</span>'
        f'<span class="badge-value">{html.escape(str(value))}</span>'
        "</div>"
    )


def render_sections(sections: Iterable[Section]) -> str:
    rendered: list[str] = []
    for section in sections:
        body = html.escape("\n".join(section.lines))
        rendered.append(
            "<details open>"
            f"<summary>{html.escape(section.name)}</summary>"
            f"<pre>{body}</pre>"
            "</details>"
        )
    return "\n".join(rendered)


def summary_dict(parsed: ParsedLog) -> dict[str, object]:
    """Return a compact machine-readable summary for cron/tools."""
    return {
        "source": str(parsed.source),
        "status": parsed.status,
        "warnings": parsed.warnings,
        "failures": parsed.failures,
        "ok_count": parsed.ok_count,
        "warn_count": parsed.warn_count,
        "fail_count": parsed.fail_count,
        "sections": [section.name for section in parsed.sections],
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }


def render_json(parsed: ParsedLog) -> str:
    return json.dumps(summary_dict(parsed), indent=2, sort_keys=True) + "\n"


def render_jsonl_record(parsed: ParsedLog) -> str:
    return json.dumps(summary_dict(parsed), sort_keys=True) + "\n"


def append_history(parsed: ParsedLog, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(render_jsonl_record(parsed))


def render_markdown(parsed: ParsedLog) -> str:
    """Render a compact Markdown report suitable for notes or chat."""
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    status = parsed.status or "UNKNOWN"
    lines = [
        "# WSL Security Healthcheck Report",
        "",
        f"Generated at: `{generated_at}`",
        f"Source log: `{parsed.source}`",
        "",
        "## Summary",
        "",
        f"- Status: `{status}`",
        f"- Warnings: `{parsed.warnings if parsed.warnings is not None else '?'}`",
        f"- Failures: `{parsed.failures if parsed.failures is not None else '?'}`",
        f"- OK checks: `{parsed.ok_count}`",
        f"- WARN lines: `{parsed.warn_count}`",
        f"- FAIL lines: `{parsed.fail_count}`",
        "",
        "## Sections",
        "",
    ]
    for section in parsed.sections:
        lines.append(f"- {section.name}")

    lines.extend(["", "## Full redacted log", "", "```text"])
    for section in parsed.sections:
        lines.append(f"==== {section.name} ====")
        lines.extend(section.lines)
    lines.extend(["```", ""])
    return "\n".join(lines)


def render_html(parsed: ParsedLog) -> str:
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    status = parsed.status or "UNKNOWN"
    css = status_class(status)
    title = f"WSL Security Healthcheck - {status}"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b1020;
      --panel: #121a2f;
      --panel-2: #17223d;
      --text: #e8eefc;
      --muted: #a8b3cf;
      --ok: #2dd4bf;
      --warn: #fbbf24;
      --fail: #fb7185;
      --unknown: #94a3b8;
      --border: #263654;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: radial-gradient(circle at top left, #172554 0, var(--bg) 42rem);
      color: var(--text);
    }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 32px 20px 56px; }}
    header {{ margin-bottom: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: clamp(2rem, 4vw, 3.4rem); letter-spacing: -0.04em; }}
    .subtitle {{ color: var(--muted); line-height: 1.6; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin: 24px 0; }}
    .badge {{ border: 1px solid var(--border); border-radius: 18px; background: linear-gradient(180deg, var(--panel), var(--panel-2)); padding: 16px; }}
    .badge-label {{ display: block; color: var(--muted); font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.08em; }}
    .badge-value {{ display: block; margin-top: 8px; font-size: 1.7rem; font-weight: 800; }}
    .badge.ok .badge-value {{ color: var(--ok); }}
    .badge.warn .badge-value {{ color: var(--warn); }}
    .badge.fail .badge-value {{ color: var(--fail); }}
    .badge.unknown .badge-value {{ color: var(--unknown); }}
    details {{ border: 1px solid var(--border); border-radius: 16px; background: rgba(18, 26, 47, 0.88); margin: 12px 0; overflow: hidden; }}
    summary {{ cursor: pointer; padding: 14px 16px; font-weight: 750; background: rgba(255,255,255,0.03); }}
    pre {{ margin: 0; padding: 16px; overflow-x: auto; white-space: pre-wrap; word-break: break-word; color: #d7e1f8; line-height: 1.45; }}
    .footer {{ margin-top: 24px; color: var(--muted); font-size: 0.9rem; }}
    code {{ color: #bfdbfe; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>WSL Security Healthcheck</h1>
      <div class="subtitle">
        Generated from <code>{html.escape(str(parsed.source))}</code><br>
        Generated at {html.escape(generated_at)}
      </div>
    </header>

    <section class="grid" aria-label="Summary">
      {render_badge("Status", status, css)}
      {render_badge("Warnings", parsed.warnings if parsed.warnings is not None else "?", "warn" if parsed.warnings else "ok")}
      {render_badge("Failures", parsed.failures if parsed.failures is not None else "?", "fail" if parsed.failures else "ok")}
      {render_badge("OK checks", parsed.ok_count, "ok")}
      {render_badge("WARN lines", parsed.warn_count, "warn" if parsed.warn_count else "ok")}
      {render_badge("FAIL lines", parsed.fail_count, "fail" if parsed.fail_count else "ok")}
    </section>

    <section>
      {render_sections(parsed.sections)}
    </section>

    <div class="footer">
      This dashboard is static HTML generated locally. It intentionally consumes only the redacted healthcheck log.
    </div>
  </main>
</body>
</html>
"""


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render security healthcheck HTML dashboard")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("logs/latest.log"),
        help="Path to security_check.sh log (default: logs/latest.log)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/dashboard.html"),
        help="Output HTML path (default: output/dashboard.html)",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional output path for compact JSON summary",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        help="Optional output path for Markdown report",
    )
    parser.add_argument(
        "--append-history",
        type=Path,
        help="Optional JSONL path to append this run's compact summary",
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Skip HTML output; useful with --json-output, --markdown-output, or --append-history",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    if not args.input.exists():
        raise SystemExit(f"input log not found: {args.input}")
    if args.no_html and not (args.json_output or args.markdown_output or args.append_history):
        raise SystemExit("--no-html requires --json-output, --markdown-output, or --append-history")

    parsed = parse_log(args.input)

    if not args.no_html:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_html(parsed))
        print(f"wrote {args.output}")

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(render_json(parsed))
        print(f"wrote {args.json_output}")

    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(parsed))
        print(f"wrote {args.markdown_output}")

    if args.append_history:
        append_history(parsed, args.append_history)
        print(f"appended {args.append_history}")

    print(f"status={parsed.status} warnings={parsed.warnings} failures={parsed.failures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
