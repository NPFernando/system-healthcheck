import tempfile
import unittest
from pathlib import Path

from tools.render_history import load_history, render_html, render_markdown, summarize


class RenderHistoryTests(unittest.TestCase):
    def test_load_history_reads_jsonl_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "history.jsonl"
            history.write_text(
                '{"generated_at":"2026-01-01T00:00:00+00:00","status":"OK","warnings":0,"failures":0,"ok_count":10,"warn_count":0,"fail_count":0,"source":"a.log"}\n'
                '{"generated_at":"2026-01-01T01:00:00+00:00","status":"WARN","warnings":1,"failures":0,"ok_count":9,"warn_count":1,"fail_count":0,"source":"b.log"}\n'
            )

            records = load_history(history)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].status, "OK")
        self.assertEqual(records[1].warnings, 1)

    def test_summarize_counts_status_and_latest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "history.jsonl"
            history.write_text(
                '{"generated_at":"t1","status":"OK","warnings":0,"failures":0}\n'
                '{"generated_at":"t2","status":"FAIL","warnings":0,"failures":1}\n'
            )
            summary = summarize(load_history(history))

        self.assertEqual(summary["total_records"], 2)
        self.assertEqual(summary["status_counts"], {"OK": 1, "FAIL": 1})
        self.assertEqual(summary["latest_status"], "FAIL")
        self.assertEqual(summary["latest_failures"], 1)

    def test_render_markdown_outputs_timeline_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "history.jsonl"
            history.write_text('{"generated_at":"t1","status":"OK","warnings":0,"failures":0,"ok_count":10,"source":"a.log"}\n')
            rendered = render_markdown(load_history(history), history)

        self.assertIn("# WSL Security Healthcheck History", rendered)
        self.assertIn("| # | Generated at | Status | Warnings | Failures | OK checks | Source |", rendered)
        self.assertIn("`OK`", rendered)

    def test_render_html_escapes_source_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "history.jsonl"
            history.write_text(
                '{"generated_at":"t1","status":"OK","warnings":0,"failures":0,"ok_count":10,"source":"<script>alert(1)</script>"}\n'
            )
            rendered = render_html(load_history(history), history)

        self.assertIn("WSL Security Healthcheck History", rendered)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", rendered)
        self.assertNotIn("<script>alert(1)</script>", rendered)


if __name__ == "__main__":
    unittest.main()
