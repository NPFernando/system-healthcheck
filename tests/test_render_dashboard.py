import json
import tempfile
import unittest
from pathlib import Path

from tools.render_dashboard import (
    append_history,
    parse_log,
    render_html,
    render_json,
    render_jsonl_record,
    render_markdown,
    status_class,
)


class RenderDashboardTests(unittest.TestCase):
    def test_parse_log_extracts_sections_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "latest.log"
            log.write_text(
                "==== Host ====\n"
                "[OK] WSL detected\n"
                "==== Summary ====\n"
                "warnings=0\n"
                "failures=0\n"
                "status=OK\n"
            )

            parsed = parse_log(log)

        self.assertEqual(parsed.status, "OK")
        self.assertEqual(parsed.warnings, 0)
        self.assertEqual(parsed.failures, 0)
        self.assertEqual(parsed.ok_count, 1)
        self.assertEqual([section.name for section in parsed.sections], ["Host", "Summary"])

    def test_status_class_maps_expected_values(self) -> None:
        self.assertEqual(status_class("OK"), "ok")
        self.assertEqual(status_class("WARN"), "warn")
        self.assertEqual(status_class("FAIL"), "fail")
        self.assertEqual(status_class(None), "unknown")

    def test_render_html_escapes_log_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "latest.log"
            log.write_text(
                "==== Network ====\n"
                "[WARN] suspicious <script>alert(1)</script>\n"
                "==== Summary ====\n"
                "warnings=1\n"
                "failures=0\n"
                "status=WARN\n"
            )

            rendered = render_html(parse_log(log))

        self.assertIn("WSL Security Healthcheck", rendered)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", rendered)
        self.assertNotIn("<script>alert(1)</script>", rendered)
        self.assertIn("Status", rendered)
        self.assertIn("WARN", rendered)
    def test_render_json_outputs_machine_readable_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "latest.log"
            log.write_text(
                "==== Host ====\n"
                "[OK] WSL detected\n"
                "==== Summary ====\n"
                "warnings=0\n"
                "failures=0\n"
                "status=OK\n"
            )

            payload = json.loads(render_json(parse_log(log)))

        self.assertEqual(payload["status"], "OK")
        self.assertEqual(payload["warnings"], 0)
        self.assertEqual(payload["failures"], 0)
        self.assertEqual(payload["ok_count"], 1)
        self.assertEqual(payload["sections"], ["Host", "Summary"])
        self.assertIn("generated_at", payload)
    def test_render_markdown_outputs_pasteable_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "latest.log"
            log.write_text(
                "==== Host ====\n"
                "[OK] WSL detected\n"
                "==== Summary ====\n"
                "warnings=0\n"
                "failures=0\n"
                "status=OK\n"
            )

            rendered = render_markdown(parse_log(log))

        self.assertIn("# WSL Security Healthcheck Report", rendered)
        self.assertIn("- Status: `OK`", rendered)
        self.assertIn("- Host", rendered)
        self.assertIn("```text", rendered)
        self.assertIn("==== Host ====", rendered)
    def test_history_appends_jsonl_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "latest.log"
            history = root / "output" / "history.jsonl"
            log.write_text(
                "==== Host ====\n"
                "[OK] WSL detected\n"
                "==== Summary ====\n"
                "warnings=0\n"
                "failures=0\n"
                "status=OK\n"
            )
            parsed = parse_log(log)

            append_history(parsed, history)
            append_history(parsed, history)

            records = [json.loads(line) for line in history.read_text().splitlines()]

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["status"], "OK")
        self.assertEqual(records[1]["warnings"], 0)
        self.assertTrue(render_jsonl_record(parsed).endswith("\n"))


if __name__ == "__main__":
    unittest.main()
