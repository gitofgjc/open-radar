import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


class WorkflowContractTests(unittest.TestCase):
    def read(self, name):
        path = WORKFLOWS / name
        self.assertTrue(path.exists(), f"missing workflow: {path}")
        return path.read_text(encoding="utf-8")

    def test_refresh_workflow_is_manual_and_daily_at_0017_utc(self):
        text = self.read("update-and-deploy.yml")
        self.assertRegex(text, r"(?m)^\s*workflow_dispatch:\s*$")
        self.assertRegex(text, r"(?m)^\s*-\s*cron:\s*['\"]17 0 \* \* \*['\"]\s*$")
        self.assertIn("python scripts/ingest_github.py --output public/data", text)
        self.assertIn("contents: write", text)
        self.assertIn("[skip ci]", text)
        self.assertIn("GITHUB_TOKEN", text)
        self.assertNotRegex(text, r"(?i)(echo|printf).*\$\{?\{?\s*secrets\.")

    def test_refresh_workflow_has_pinned_actions_and_stale_safe_commit(self):
        text = self.read("update-and-deploy.yml")
        actions = re.findall(r"uses:\s*([^\s#]+)", text)
        self.assertGreaterEqual(len(actions), 1)
        for action in actions:
            self.assertRegex(action, r"@[0-9a-f]{40}$", f"action is not pinned: {action}")
        self.assertIn("continue-on-error: true", text)
        self.assertIn("git diff --quiet", text)
        self.assertIn("public/data", text)

    def test_pages_workflow_publishes_public_with_oidc_least_privilege(self):
        text = self.read("pages.yml")
        self.assertRegex(text, r"(?m)^\s*workflow_dispatch:\s*$")
        self.assertIn("pages: write", text)
        self.assertIn("id-token: write", text)
        self.assertIn("actions/upload-pages-artifact", text)
        self.assertIn("actions/deploy-pages", text)
        self.assertIn("path: public", text)
        self.assertIn("workflow_run:", text)
        self.assertIn("Refresh GitHub radar data", text)
        self.assertIn("ref: ${{ github.event_name == 'workflow_run' && github.event.workflow_run.head_branch || github.ref_name }}", text)
        self.assertNotIn("contents: write", text)
        actions = re.findall(r"uses:\s*([^\s#]+)", text)
        for action in actions:
            self.assertRegex(action, r"@[0-9a-f]{40}$", f"action is not pinned: {action}")

    def test_docs_cover_local_preview_stale_data_and_first_deploy_boundary(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        combined = f"{readme}\n{contributing}"
        for phrase in (
            "python3 -m http.server --directory public 4173",
            "每天北京时间 08:17",
            "last-known-good",
            "workflow_dispatch",
            "GitHub Pages",
            "不需要把密码",
            "GITHUB_TOKEN",
            "Secrets",
        ):
            self.assertIn(phrase, combined)


if __name__ == "__main__":
    unittest.main()
