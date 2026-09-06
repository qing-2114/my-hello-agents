"""workspace_tools 的离线单元测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import workspace_tools


VALID_HTML = """<!doctype html><link rel="stylesheet" href="styles.css">
<main><p id="price"></p><p id="status"></p><time id="updated-at"></time></main>
<script src="app.js"></script>"""
VALID_JS = """async function update(){try{await fetch('https://example.test/bitcoin?usd')}catch(error){console.error(error)}}
update(); setInterval(update, 30000);"""


class WorkspaceToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app_dir = Path(self.temp_dir.name) / "generated_app"
        self.patch = patch.object(workspace_tools, "APP_DIR", self.app_dir)
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()
        self.temp_dir.cleanup()

    def test_rejects_path_traversal(self) -> None:
        result = workspace_tools.write_project_file("../outside.js", "bad")
        self.assertTrue(result.startswith("ERROR:"))

    def test_valid_project_passes_static_acceptance(self) -> None:
        workspace_tools.write_project_file("index.html", VALID_HTML)
        workspace_tools.write_project_file("styles.css", "body { color: #fff; }")
        workspace_tools.write_project_file("app.js", VALID_JS)
        report = workspace_tools.validate_web_app(check_live_price=False)
        self.assertTrue(report.startswith("PASS"), report)

    def test_accepts_last_updated_as_timestamp_id(self) -> None:
        workspace_tools.write_project_file(
            "index.html", VALID_HTML.replace("updated-at", "last-updated")
        )
        workspace_tools.write_project_file("styles.css", "body { color: #fff; }")
        workspace_tools.write_project_file("app.js", VALID_JS)
        report = workspace_tools.validate_web_app(check_live_price=False)
        self.assertTrue(report.startswith("PASS"), report)

    def test_missing_files_fail_acceptance(self) -> None:
        workspace_tools.write_project_file("index.html", VALID_HTML)
        report = workspace_tools.validate_web_app(check_live_price=False)
        self.assertTrue(report.startswith("FAIL"), report)

    def test_rejects_duplicate_currency_symbol_rendering(self) -> None:
        workspace_tools.write_project_file("index.html", VALID_HTML)
        workspace_tools.write_project_file(
            "styles.css", '.price::before { content: "$"; }'
        )
        workspace_tools.write_project_file(
            "app.js",
            VALID_JS
            + '\nnew Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });',
        )
        report = workspace_tools.validate_web_app(check_live_price=False)
        self.assertTrue(report.startswith("FAIL"), report)
        self.assertIn("双 $ 符号", report)


if __name__ == "__main__":
    unittest.main()
