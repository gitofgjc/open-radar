import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ingest_github import build_payload, compute_delta_windows, compute_deltas, growth_rates, merge_history, normalise_repo, observed_history_days, GitHubClient, run  # noqa: E402


def iso(days_ago=0, hour=0):
    return (datetime.now(timezone.utc).replace(hour=hour, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


class IngestTests(unittest.TestCase):
    def test_deltas_require_real_observations_and_skip_intervals_without_interpolation(self):
        history = [
            {"date": iso(10), "stars": 100},
            {"date": iso(3), "stars": 130},
            {"date": iso(0), "stars": 140},
        ]
        deltas = compute_deltas(history, now=datetime.now(timezone.utc))
        # A 10-day snapshot is too far from the 7-day target; no interpolation.
        assert deltas["7d"] is None
        # 30d has no sufficiently old observation and must stay unknown.
        assert deltas["30d"] is None
        assert deltas["1d"] is None

    def test_deltas_reject_star_resets_and_negative_values(self):
        history = [{"date": iso(2), "stars": 500}, {"date": iso(0), "stars": 120}]
        deltas = compute_deltas(history, now=datetime.now(timezone.utc))
        assert deltas["1d"] is None
        assert deltas["7d"] is None

    def test_merge_history_deduplicates_same_day_and_keeps_last_known_good(self):
        prior = [{"date": "2026-01-01T08:00:00Z", "stars": 10}]
        merged = merge_history(prior, {"date": "2026-01-01T12:00:00Z", "stars": 12})
        assert len(merged) == 1
        assert merged[0]["stars"] == 12

    def test_curated_aliases_match_current_github_repository_names(self):
        fixtures = [
            ("react/react", "构建用户界面的 JavaScript 库。", "开发工具"),
            ("ggml-org/llama.cpp", "在多种硬件上高效运行大语言模型的 C/C++ 实现。", "AI 与智能体"),
            ("Comfy-Org/ComfyUI", "基于节点工作流的生成式图像界面。", "设计与创作"),
        ]
        with tempfile.TemporaryDirectory() as folder:
            for repo_id, summary, category in fixtures:
                repo = normalise_repo({
                    "full_name": repo_id, "name": repo_id.split("/", 1)[1],
                    "owner": {"login": repo_id.split("/", 1)[0]}, "description": "live description",
                    "stargazers_count": 100, "language": "Python", "topics": [],
                }, Path(folder), datetime(2026, 11, 7, tzinfo=timezone.utc))
                assert repo["summary"] == summary
                assert repo["category"] == category
                assert repo["featured"] is True

    def test_category_keywords_do_not_match_inside_unrelated_words(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = normalise_repo({
                "full_name": "example/chair", "name": "chair", "owner": {"login": "example"},
                "description": "A lightweight chair companion app for office desks.",
                "topics": [], "stargazers_count": 10,
            }, Path(folder), datetime(2026, 11, 7, tzinfo=timezone.utc))
        assert repo["category"] == "效率工具"

    def test_topics_and_description_assign_non_default_categories(self):
        fixtures = [
            ({"full_name": "example/books", "description": "A free programming course and study guide.", "topics": ["education", "books", "curriculum"]}, "学习资源"),
            ({"full_name": "example/vault", "description": "Private encrypted network utility.", "topics": ["security", "privacy", "encryption"]}, "安全与隐私"),
            ({"full_name": "example/server", "description": "Self-hosted home server dashboard.", "topics": ["self-hosted", "homelab"]}, "自托管"),
            ({"full_name": "example/model", "description": "Run large language models locally.", "topics": ["llm", "inference"]}, "AI 与智能体"),
            ({"full_name": "example/metrics", "description": "Metrics and monitoring dashboard.", "topics": ["observability", "metrics"]}, "数据与分析"),
            ({"full_name": "example/audit", "description": "A security audit skill for repositories.", "topics": []}, "安全与隐私"),
            ({"full_name": "example/tutorials", "description": "Recreate technologies from scratch.", "topics": ["tutorial-code", "tutorial-exercises"]}, "学习资源"),
        ]
        with tempfile.TemporaryDirectory() as folder:
            for raw, category in fixtures:
                raw = {**raw, "name": raw["full_name"].split("/", 1)[1], "owner": {"login": "example"}, "stargazers_count": 100}
                repo = normalise_repo(raw, Path(folder), datetime(2026, 11, 7, tzinfo=timezone.utc))
                assert repo["category"] == category, (raw["full_name"], repo["category"])

    def test_unknown_repository_copy_uses_observable_description_and_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = normalise_repo({
                "full_name": "example/useful-tool", "name": "useful-tool",
                "owner": {"login": "example"}, "description": "A compact tool for parsing release notes.",
                "stargazers_count": 1234, "forks_count": 20, "open_issues_count": 3,
                "language": "Python", "topics": ["release", "automation"],
                "pushed_at": "2026-11-06T03:04:05Z", "license": {"spdx_id": "MIT"},
            }, Path(folder), datetime(2026, 11, 7, 5, tzinfo=timezone.utc))
        assert "A compact tool for parsing release notes." in repo["summary"]
        assert "当前观测 Stars：1,234" in repo["reasons"]
        assert any("最近推送" in reason and "2026-11-06" in reason for reason in repo["reasons"])
        assert all("进入当前候选观察范围" not in reason for reason in repo["reasons"])

    def test_curated_reasons_are_explicitly_editorial(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = normalise_repo({
                "full_name": "astral-sh/uv", "name": "uv", "stargazers_count": 100,
                "language": "Rust", "topics": ["python", "packaging"],
                "pushed_at": "2026-11-06T00:00:00Z", "license": {"spdx_id": "MIT"},
            }, Path(folder), datetime(2026, 11, 7, tzinfo=timezone.utc))
        assert any(reason.startswith("编辑选取：") for reason in repo["reasons"])
        assert any(reason.startswith("当前观测 Stars：") for reason in repo["reasons"])

    def test_payload_exposes_consistent_status_copy(self):
        payload = build_payload([], fetch_error="offline")
        assert payload["meta"]["status"] == "sample"
        assert payload["meta"]["statusLabel"] == "暂无真实数据"
        assert "尚未成功获取" in payload["meta"]["statusMessage"]
        previous = {"meta": {"lastSuccessAt": "2026-11-06T00:00:00Z"}, "repositories": [{"id": "octo/demo", "history": []}], "rankings": {}}
        stale = build_payload([], previous=previous, fetch_error="rate limited", now=datetime(2026, 11, 7, tzinfo=timezone.utc))
        assert stale["meta"]["status"] == "stale"
        assert stale["meta"]["statusLabel"] == "使用旧快照"

    def test_build_payload_marks_stale_fallback_and_preserves_previous_data(self):
        previous = {
            "meta": {"schemaVersion": 1, "status": "live", "lastSuccessAt": "2026-01-01T00:00:00Z"},
            "repositories": [{"id": "octo/demo", "fullName": "octo/demo", "stars": 9, "history": []}],
            "rankings": {"stars": ["octo/demo"]},
        }
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "projects.json"
            out.write_text(json.dumps(previous), encoding="utf-8")
            payload = build_payload([], previous=previous, now=datetime(2026, 1, 2, tzinfo=timezone.utc), fetch_error="rate limited")
        assert payload["meta"]["status"] == "stale"
        assert payload["meta"]["lastSuccessAt"] == "2026-01-01T00:00:00Z"
        assert payload["repositories"][0]["stars"] == 9
        assert "rate limited" in payload["meta"]["warnings"][0]

    def test_valid_windows_use_actual_timestamps_and_relative_fraction(self):
        now = datetime(2026, 11, 7, 5, tzinfo=timezone.utc)
        history = [
            {"date": "2026-10-08T08:00:00Z", "stars": 100},
            {"date": "2026-10-31T04:00:00Z", "stars": 150},
            {"date": "2026-11-06T06:00:00Z", "stars": 180},
            {"date": "2026-11-07T05:00:00Z", "stars": 200},
        ]
        deltas = compute_deltas(history, now=now)
        assert deltas == {"1d": 20, "7d": 50, "30d": 100}
        assert growth_rates(history, deltas, now=now)["1d"] == 0.1111
        windows = compute_delta_windows(history, now=now)
        assert windows["1d"]["from"] == "2026-11-06T06:00:00Z"
        assert windows["1d"]["to"] == "2026-11-07T05:00:00Z"
        assert observed_history_days([{"history": history}]) == 29

    def test_normalise_repo_persists_observation_and_delta_windows(self):
        with tempfile.TemporaryDirectory() as folder:
            now = datetime(2026, 11, 7, 5, tzinfo=timezone.utc)
            repo = normalise_repo({
                "full_name": "octo/demo", "name": "demo", "owner": {"login": "octo"},
                "stargazers_count": 10, "forks_count": 2, "open_issues_count": 1,
            }, Path(folder), now)
            assert repo["history"] == [{"date": "2026-11-07T05:00:00Z", "stars": 10}]
            assert set(repo["deltaWindows"]) == {"1d", "7d", "30d"}
            assert all(value is None for value in repo["deltaWindows"].values())
            assert (Path(folder) / "octo__demo.json").exists()

    def test_run_whole_fetch_failure_is_stale_and_does_not_claim_success(self):
        import ingest_github
        from unittest.mock import patch
        previous = {
            "meta": {"lastSuccessAt": "2026-11-06T00:00:00Z"},
            "repositories": [{"id": "octo/demo", "stars": 9, "history": []}],
            "rankings": {"stars": ["octo/demo"]},
        }
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "public").mkdir()
            (root / "public/projects.json").write_text(json.dumps(previous), encoding="utf-8")
            with patch.object(ingest_github, "candidate_repositories", return_value=([], ["network unavailable"])):
                result = run(root / "public", root / "history")
            written = json.loads((root / "public/projects.json").read_text())
        assert result["meta"]["status"] == "stale"
        assert written["meta"]["lastSuccessAt"] == previous["meta"]["lastSuccessAt"]
        assert written["repositories"] == previous["repositories"]

    def test_client_cap_prevents_retry_requests_exceeding_budget(self):
        import ingest_github
        from unittest.mock import patch
        from urllib.error import URLError
        client = GitHubClient(max_requests=1)
        with patch.object(ingest_github, "urlopen", side_effect=URLError("temporary outage")) as opened, patch.object(ingest_github.time, "sleep"):
            with self.assertRaises(RuntimeError):
                client.request("/repos/octo/demo")
        assert opened.call_count == 1

    def test_cold_start_is_labeled_without_invented_sample_stars(self):
        payload = build_payload([], fetch_error="offline")
        assert payload["meta"]["status"] == "sample"
        assert payload["meta"]["historyDays"] == 0
        assert payload["repositories"] == []
        assert payload["meta"]["lastSuccessAt"] is None


if __name__ == "__main__":
    unittest.main()
