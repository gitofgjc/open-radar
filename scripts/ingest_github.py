#!/usr/bin/env python3
"""Build the Open Radar GitHub data snapshot.

The command is intentionally dependency-free so it can run in GitHub Actions and
on a laptop. It uses only GitHub's REST API and stores one append-only history
file per repository under data/history.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

UTC = timezone.utc
API_ROOT = "https://api.github.com"
SCHEMA_VERSION = 1
DEFAULT_MAX_REQUESTS = 56

# The curation layer is deliberately separate from GitHub's mutable metadata.
# It gives the Chinese UI a stable, human-readable reason for inclusion.
CURATED: Dict[str, Dict[str, Any]] = {
    "microsoft/vscode": {"summary": "跨平台代码编辑器，扩展生态成熟，适合日常开发。", "category": "开发工具", "reasons": ["社区规模大且持续维护", "扩展生态覆盖主流语言"]},
    "neovim/neovim": {"summary": "面向开发者的现代化 Vim，适合键盘驱动和高度定制。", "category": "开发工具", "reasons": ["活跃的核心开发社区", "配置和插件生态丰富"]},
    "git/git": {"summary": "分布式版本控制系统 Git 的官方源码。", "category": "开发工具", "reasons": ["基础设施级项目", "文档与发布流程稳定"]},
    "astral-sh/uv": {"summary": "用 Rust 编写的快速 Python 包与项目管理器。", "category": "开发工具", "reasons": ["近期迭代活跃", "显著改善 Python 环境管理体验"]},
    "astral-sh/ruff": {"summary": "速度很快的 Python linter 和 formatter。", "category": "开发工具", "reasons": ["工具链整合度高", "适合纳入持续集成"]},
    "junegunn/fzf": {"summary": "终端通用模糊查找器，适合快速定位文件和命令。", "category": "效率工具", "reasons": ["命令行工作流复用性高", "依赖少且跨平台"]},
    "sharkdp/bat": {"summary": "带语法高亮和 Git 集成的 cat 替代品。", "category": "效率工具", "reasons": ["上手成本低", "终端阅读体验直接改善"]},
    "BurntSushi/ripgrep": {"summary": "高性能递归文本搜索工具，适合大型代码库。", "category": "开发工具", "reasons": ["性能和可靠性经过广泛验证", "常用于自动化脚本"]},
    "tldr-pages/tldr": {"summary": "面向常见命令的简明社区手册。", "category": "学习资源", "reasons": ["适合快速查命令", "社区维护的实用文档"]},
    "ohmyzsh/ohmyzsh": {"summary": "可扩展的 Zsh 配置框架，提供主题和插件。", "category": "效率工具", "reasons": ["生态成熟", "适合新机器快速配置"]},
    "docker/compose": {"summary": "用声明式文件编排多容器开发环境。", "category": "开发工具", "reasons": ["本地开发常用", "文档和兼容性较好"]},
    "kubernetes/kubernetes": {"summary": "容器编排平台 Kubernetes 的主仓库。", "category": "开发工具", "reasons": ["云原生基础设施核心项目", "社区与供应商支持广泛"]},
    "helm/helm": {"summary": "Kubernetes 的应用包管理器，提供可复用的 Chart。", "category": "开发工具", "reasons": ["部署流程标准化", "适合团队共享配置"]},
    "prometheus/prometheus": {"summary": "开源监控与时序数据库，使用 PromQL 查询指标。", "category": "数据与分析", "reasons": ["可观测性基础组件", "生态和集成丰富"]},
    "grafana/grafana": {"summary": "可组合的指标、日志和链路可视化平台。", "category": "数据与分析", "reasons": ["仪表盘和数据源覆盖广", "适合建立团队观测面板"]},
    "usememos/memos": {"summary": "轻量、可自托管的知识和碎片记录工具。", "category": "自托管", "reasons": ["适合个人知识库", "部署简单且更新活跃"]},
    "immich-app/immich": {"summary": "注重隐私的自托管照片和视频管理平台。", "category": "自托管", "reasons": ["本地数据控制力强", "近期功能迭代快"]},
    "paperless-ngx/paperless-ngx": {"summary": "将纸质文件扫描件整理为可搜索的文档库。", "category": "自托管", "reasons": ["OCR 和自动归档实用", "适合家庭或小团队部署"]},
    "gethomepage/homepage": {"summary": "可自托管的现代化服务导航首页。", "category": "自托管", "reasons": ["配置集中管理常用服务", "界面简洁且集成多"]},
    "home-assistant/core": {"summary": "以隐私为先的家庭自动化平台。", "category": "自托管", "reasons": ["设备集成数量大", "本地自动化能力强"]},
    "syncthing/syncthing": {"summary": "点对点持续同步文件，不依赖中心服务器。", "category": "安全与隐私", "reasons": ["数据传输自主可控", "跨平台同步成熟"]},
    "tailscale/tailscale": {"summary": "基于 WireGuard 的组网工具，简化安全远程访问。", "category": "安全与隐私", "reasons": ["组网体验友好", "适合连接个人设备和服务"]},
    "OpenVPN/openvpn3": {"summary": "OpenVPN 3 客户端核心库和工具。", "category": "安全与隐私", "reasons": ["成熟的加密网络方案", "适合需要可审计客户端的场景"]},
    "moby/moby": {"summary": "Docker 容器引擎的开源项目。", "category": "开发工具", "reasons": ["容器生态底层组件", "发布和社区信号稳定"]},
    "pocketbase/pocketbase": {"summary": "单文件后端，内置数据库、认证和文件存储。", "category": "开发工具", "reasons": ["适合快速构建小型应用", "部署和试错成本低"]},
    "supabase/supabase": {"summary": "基于 Postgres 的开源后端平台。", "category": "数据与分析", "reasons": ["数据库能力完整", "适合原型和生产应用"]},
    "appwrite/appwrite": {"summary": "面向开发者的自托管后端服务平台。", "category": "开发工具", "reasons": ["认证与存储等基础能力齐全", "适合希望保留部署控制权的团队"]},
    "directus/directus": {"summary": "将 SQL 数据库连接为 API 和管理界面。", "category": "数据与分析", "reasons": ["低代码数据管理灵活", "适合已有数据库项目"]},
    "langchain-ai/langchain": {"summary": "构建大语言模型应用的开发框架。", "category": "AI 与智能体", "reasons": ["集成模型和工具的案例多", "适合快速验证智能体流程"]},
    "microsoft/autogen": {"summary": "用于多智能体协作和对话式应用的框架。", "category": "AI 与智能体", "reasons": ["关注智能体编排模式", "有较多实验性实践参考"]},
    "open-webui/open-webui": {"summary": "可自托管的模型对话 Web 界面，支持多种后端。", "category": "AI 与智能体", "reasons": ["本地模型体验完整", "适合个人和团队试用"]},
    "ollama/ollama": {"summary": "在本地运行和管理大语言模型的工具。", "category": "AI 与智能体", "reasons": ["本地推理上手快", "模型管理命令简单"]},
    "comfyanonymous/ComfyUI": {"summary": "基于节点工作流的生成式图像界面。", "category": "设计与创作", "reasons": ["工作流可视化且可复用", "扩展模型和节点众多"]},
    "AUTOMATIC1111/stable-diffusion-webui": {"summary": "Stable Diffusion 的社区 Web 界面和扩展平台。", "category": "设计与创作", "reasons": ["图像生成生态成熟", "适合探索模型和插件"]},
    "openai/whisper": {"summary": "通用语音识别模型，支持多语言转写。", "category": "AI 与智能体", "reasons": ["语音转写质量和适用面广", "研究与应用资料丰富"]},
    "ggerganov/llama.cpp": {"summary": "在多种硬件上高效运行大语言模型的 C/C++ 实现。", "category": "AI 与智能体", "reasons": ["本地推理基础设施重要", "硬件适配和量化工具丰富"]},
    "pytorch/pytorch": {"summary": "面向研究和生产的开源机器学习框架。", "category": "AI 与智能体", "reasons": ["生态和教程体系完整", "持续吸收前沿研究"]},
    "huggingface/transformers": {"summary": "预训练模型和推理训练工具的主流库。", "category": "AI 与智能体", "reasons": ["模型覆盖范围广", "社区共享资源丰富"]},
    "numpy/numpy": {"summary": "Python 科学计算的数组和数值运算基础库。", "category": "数据与分析", "reasons": ["科学 Python 生态底座", "API 稳定且资料丰富"]},
    "pandas-dev/pandas": {"summary": "用于表格数据处理和分析的 Python 库。", "category": "数据与分析", "reasons": ["数据清洗场景覆盖广", "与主流分析工具链兼容"]},
    "jupyter/notebook": {"summary": "交互式计算笔记本，适合探索、教学和报告。", "category": "数据与分析", "reasons": ["探索式工作流成熟", "扩展和分享方式多"]},
    "streamlit/streamlit": {"summary": "用 Python 快速搭建数据应用和模型演示。", "category": "数据与分析", "reasons": ["原型开发速度快", "适合分享交互式结果"]},
    "vitejs/vite": {"summary": "现代前端开发服务器和构建工具。", "category": "开发工具", "reasons": ["开发反馈速度快", "前端生态采用广泛"]},
    "facebook/react": {"summary": "构建用户界面的 JavaScript 库。", "category": "开发工具", "reasons": ["组件生态成熟", "社区资源和招聘需求广泛"]},
    "vuejs/core": {"summary": "渐进式 JavaScript 用户界面框架。", "category": "开发工具", "reasons": ["学习曲线平滑", "中文社区和文档资源丰富"]},
    "sveltejs/svelte": {"summary": "将组件编译为高效 JavaScript 的前端框架。", "category": "开发工具", "reasons": ["运行时开销低", "组件语法简洁"]},
    "denoland/deno": {"summary": "内置 TypeScript、权限和工具链的 JavaScript 运行时。", "category": "开发工具", "reasons": ["开箱即用的开发体验", "持续探索 Web 标准"]},
    "oven-sh/bun": {"summary": "面向 JavaScript 和 TypeScript 的快速运行时与工具链。", "category": "开发工具", "reasons": ["启动和安装速度快", "整合常用开发工具"]},
    "vercel/next.js": {"summary": "用于生产级 React 应用的全栈框架。", "category": "开发工具", "reasons": ["渲染和部署能力完整", "生产案例与文档丰富"]},
    "playwright-community/playwright": {"summary": "跨浏览器端到端测试与自动化框架。", "category": "开发工具", "reasons": ["覆盖现代浏览器", "适合稳定回归测试"]},
    "pytest-dev/pytest": {"summary": "Python 测试框架，强调可读性和插件扩展。", "category": "开发工具", "reasons": ["测试表达清晰", "插件生态成熟"]},
    "eslint/eslint": {"summary": "可配置的 JavaScript 和 TypeScript 静态检查器。", "category": "开发工具", "reasons": ["前端质量门槛常用", "规则和插件丰富"]},
    "prettier/prettier": {"summary": "统一代码格式的多语言 formatter。", "category": "开发工具", "reasons": ["减少团队格式争议", "编辑器和 CI 集成方便"]},
    "logseq/logseq": {"summary": "本地优先的双向链接知识管理工具。", "category": "效率工具", "reasons": ["数据保存在本地", "适合结构化思考和日记"]},
    "obsidianmd/obsidian-releases": {"summary": "Obsidian 的公开发布和版本信息仓库。", "category": "效率工具", "reasons": ["知识管理工具生态活跃", "插件社区丰富"]},
    "calcom/cal.com": {"summary": "可自托管的日程预约和会议排程工具。", "category": "自托管", "reasons": ["适合团队预约流程", "开放集成和部署控制"]},
}

CATEGORIES = ("AI 与智能体", "开发工具", "自托管", "数据与分析", "设计与创作", "学习资源", "安全与隐私", "效率工具")


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _normalise_history(history: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_day: Dict[str, Dict[str, Any]] = {}
    for item in history or []:
        when = parse_time(item.get("date"))
        stars = item.get("stars")
        if not when or not isinstance(stars, int) or stars < 0:
            continue
        key = when.date().isoformat()
        by_day[key] = {"date": iso(when), "stars": stars}
    return sorted(by_day.values(), key=lambda x: x["date"])


def merge_history(prior: Iterable[Dict[str, Any]], observation: Dict[str, Any], max_days: int = 400) -> List[Dict[str, Any]]:
    """Merge a real observation, replacing a same-day observation and pruning old rows."""
    merged = _normalise_history(list(prior or []) + [observation])
    cutoff = parse_time(observation.get("date"))
    if cutoff:
        merged = [row for row in merged if (cutoff - parse_time(row["date"])).days <= max_days]
    return merged


def _baseline_for_window(history: List[Dict[str, Any]], now: datetime, days: int) -> Optional[Dict[str, Any]]:
    """Find a real snapshot near the requested window target.

    A much older row is deliberately rejected: presenting a 10-day interval as
    a 7-day change would fabricate precision. Tolerances account for scheduled
    jobs that run a little early or late (18h, 36h and 72h respectively).
    """
    latest = max(history, key=lambda row: row["date"]) if history else None
    if not latest:
        return None
    latest_when = parse_time(latest.get("date")) or now
    target = latest_when - timedelta(days=days)
    tolerance = {1: timedelta(hours=18), 7: timedelta(hours=36), 30: timedelta(hours=72)}[days]
    eligible: List[Tuple[float, Dict[str, Any]]] = []
    for row in history:
        when = parse_time(row.get("date"))
        if not when or row is latest:
            continue
        distance = abs((when - target).total_seconds())
        if distance <= tolerance.total_seconds():
            eligible.append((distance, row))
    return min(eligible, key=lambda pair: pair[0])[1] if eligible else None


def _window_baselines(history: Iterable[Dict[str, Any]], now: Optional[datetime] = None) -> Tuple[Optional[Dict[str, Any]], Dict[str, Optional[Dict[str, Any]]]]:
    rows = _normalise_history(history)
    latest = max(rows, key=lambda row: row["date"]) if rows else None
    reference = parse_time(latest.get("date")) if latest else (now or utc_now()).astimezone(UTC)
    return latest, {label: _baseline_for_window(rows, reference, days) for label, days in (("1d", 1), ("7d", 7), ("30d", 30))}


def compute_delta_windows(history: Iterable[Dict[str, Any]], now: Optional[datetime] = None) -> Dict[str, Optional[Dict[str, Any]]]:
    latest, baselines = _window_baselines(history, now=now)
    if not latest:
        return {label: None for label in ("1d", "7d", "30d")}
    return {
        label: ({"from": baseline["date"], "to": latest["date"], "days": days} if baseline else None)
        for (label, days), baseline in ((("1d", 1), baselines["1d"]), (("7d", 7), baselines["7d"]), (("30d", 30), baselines["30d"]))
    }


def compute_deltas(history: Iterable[Dict[str, Any]], now: Optional[datetime] = None) -> Dict[str, Optional[int]]:
    """Compute changes only when a real snapshot is near each target window."""
    latest, baselines = _window_baselines(history, now=now)
    if not latest:
        return {"1d": None, "7d": None, "30d": None}
    result: Dict[str, Optional[int]] = {}
    for label in ("1d", "7d", "30d"):
        baseline = baselines[label]
        if not baseline:
            result[label] = None
            continue
        delta = latest["stars"] - baseline["stars"]
        result[label] = delta if delta >= 0 else None
    return result

def growth_rates(history: Iterable[Dict[str, Any]], deltas: Dict[str, Optional[int]], now: Optional[datetime] = None) -> Dict[str, Optional[float]]:
    rows = _normalise_history(history)
    _latest, baselines = _window_baselines(rows, now=now)
    result: Dict[str, Optional[float]] = {}
    for label in ("1d", "7d", "30d"):
        baseline = baselines[label]
        delta = deltas.get(label)
        if not baseline or delta is None or baseline["stars"] <= 0:
            result[label] = None
        else:
            result[label] = round(delta / baseline["stars"], 4)
    return result


def _safe_category(value: Any) -> str:
    return value if value in CATEGORIES else "效率工具"


def _curated(repo_id: str) -> Dict[str, Any]:
    item = CURATED.get(repo_id, {})
    return {
        "summary": item.get("summary") or "社区持续维护的开源项目，适合进一步阅读其文档和变更记录。",
        "category": _safe_category(item.get("category")),
        "reasons": list(item.get("reasons") or ["进入当前候选观察范围", "可从仓库文档和近期活动进一步评估"]),
    }


def _history_path(history_root: Path, repo_id: str) -> Path:
    safe = repo_id.replace("/", "__").replace("\\", "__")
    return history_root / f"{safe}.json"


def load_history(history_root: Path, repo_id: str) -> List[Dict[str, Any]]:
    path = _history_path(history_root, repo_id)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return _normalise_history(raw if isinstance(raw, list) else raw.get("history", []))
    except (OSError, ValueError, TypeError):
        return []


def save_history(history_root: Path, repo_id: str, history: List[Dict[str, Any]]) -> None:
    history_root.mkdir(parents=True, exist_ok=True)
    path = _history_path(history_root, repo_id)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class GitHubClient:
    def __init__(self, token: Optional[str] = None, max_requests: int = DEFAULT_MAX_REQUESTS, timeout: float = 15.0):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.max_requests = max_requests
        self.requests = 0
        self.timeout = timeout
        self.remaining: Optional[int] = None

    def request(self, path: str, params: Optional[Dict[str, str]] = None) -> Any:
        if self.requests >= self.max_requests:
            raise RuntimeError(f"request safety cap reached ({self.max_requests})")
        query = ("?" + urlencode(params)) if params else ""
        req = Request(API_ROOT + path + query, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "open-radar-ingest/1.0",
            **({"Authorization": f"Bearer {self.token}"} if self.token else {}),
        })
        last_error: Optional[Exception] = None
        for attempt in range(3):
            if self.requests >= self.max_requests:
                raise RuntimeError(f"request safety cap reached ({self.max_requests})")
            self.requests += 1
            try:
                with urlopen(req, timeout=self.timeout) as response:
                    self.remaining = _int_header(response.headers.get("X-RateLimit-Remaining"))
                    if self.remaining is not None and self.remaining <= 1:
                        # The response is still valid; avoid another call.
                        self.max_requests = min(self.max_requests, self.requests)
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                self.remaining = _int_header(exc.headers.get("X-RateLimit-Remaining")) if exc.headers else None
                last_error = exc
                if exc.code == 403 and self.remaining is not None and self.remaining <= 0:
                    raise RuntimeError("GitHub API rate limit exhausted") from exc
                if exc.code not in (429, 500, 502, 503, 504):
                    raise
                retry_after = _int_header(exc.headers.get("Retry-After")) if exc.headers else None
                time.sleep(min(retry_after or (2 ** attempt), 8))
            except (URLError, TimeoutError, OSError, ValueError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"GitHub request failed: {last_error}") from last_error


def _int_header(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def normalise_repo(raw: Dict[str, Any], history_root: Path, now: datetime) -> Dict[str, Any]:
    repo_id = raw.get("full_name") or raw.get("name")
    if not repo_id or "/" not in repo_id:
        raise ValueError("GitHub response has no full_name")
    curated = _curated(repo_id)
    observation = {"date": iso(now), "stars": int(raw.get("stargazers_count") or 0)}
    history = merge_history(load_history(history_root, repo_id), observation)
    save_history(history_root, repo_id, history)
    deltas = compute_deltas(history, now=now)
    delta_windows = compute_delta_windows(history, now=now)
    return {
        "id": repo_id,
        "fullName": repo_id,
        "name": raw.get("name") or repo_id.rsplit("/", 1)[-1],
        "owner": (raw.get("owner") or {}).get("login") or repo_id.split("/", 1)[0],
        "url": raw.get("html_url") or f"https://github.com/{repo_id}",
        "homepage": raw.get("homepage") or None,
        "description": raw.get("description") or "",
        "summary": curated["summary"],
        "category": curated["category"],
        "topics": list(raw.get("topics") or []),
        "language": raw.get("language") or None,
        "license": ((raw.get("license") or {}).get("spdx_id") or None),
        "stars": observation["stars"],
        "forks": int(raw.get("forks_count") or 0),
        "openIssues": int(raw.get("open_issues_count") or 0),
        "createdAt": raw.get("created_at"),
        "pushedAt": raw.get("pushed_at"),
        "fetchedAt": iso(now),
        "archived": bool(raw.get("archived", False)),
        "featured": repo_id in CURATED,
        "reasons": curated["reasons"],
        "deltas": deltas,
        "growthRates": growth_rates(history, deltas, now=now),
        "deltaWindows": delta_windows,
        "history": history,
    }


def _sort_ids(repositories: Sequence[Dict[str, Any]], field: str, reverse: bool = True) -> List[str]:
    available = [r for r in repositories if r.get(field) is not None]
    return [r["id"] for r in sorted(available, key=lambda r: r.get(field, 0), reverse=reverse)]


def _newcomers(repositories: Sequence[Dict[str, Any]], now: datetime) -> List[str]:
    cutoff = now - timedelta(days=90)
    rows = [r for r in repositories if (when := parse_time(r.get("createdAt"))) and when >= cutoff]
    return [r["id"] for r in sorted(rows, key=lambda r: parse_time(r.get("createdAt")) or cutoff, reverse=True)]


def observed_history_days(repositories: Sequence[Dict[str, Any]]) -> int:
    """Return the largest span covered by actual snapshots in this payload."""
    spans: List[int] = []
    for repo in repositories:
        rows = _normalise_history(repo.get("history") or [])
        if len(rows) >= 2:
            first = parse_time(rows[0].get("date"))
            last = parse_time(rows[-1].get("date"))
            if first and last:
                spans.append(max(0, (last - first).days))
    return max(spans, default=0)


def _base_meta(now: datetime, status: str, count: int, last_success: Optional[str], warnings: List[str], history_days: int = 0) -> Dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": iso(now),
        "lastSuccessAt": last_success,
        "status": status,
        "source": "GitHub REST API",
        "coverage": "结合 GitHub stars 排名、近期创建且受关注的仓库与人工精选候选；榜单反映本次抓取范围。",
        "repositoryCount": count,
        "historyDays": max(0, int(history_days)),
        "nextUpdate": "每天北京时间 08:17 起（可能延迟）",
        "warnings": warnings,
    }


def build_payload(repositories: Sequence[Dict[str, Any]], previous: Optional[Dict[str, Any]] = None, now: Optional[datetime] = None, fetch_error: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
    """Build a schema-valid payload, preserving the previous snapshot on failure."""
    current_time = (now or utc_now()).astimezone(UTC)
    previous = previous or {}
    if not repositories:
        prior_meta = previous.get("meta") or {}
        warnings = list(prior_meta.get("warnings") or [])
        if fetch_error:
            warnings.insert(0, f"本次抓取失败，已保留上次成功数据：{fetch_error}")
        if previous.get("repositories"):
            meta = _base_meta(current_time, "stale", len(previous.get("repositories", [])), prior_meta.get("lastSuccessAt"), warnings, observed_history_days(previous.get("repositories", [])))
            # Keep the old generatedAt as a useful audit trail only through
            # lastSuccessAt; generatedAt identifies this stale attempt.
            return {"meta": meta, "repositories": previous.get("repositories", []), "rankings": previous.get("rankings", {})}
        warning = fetch_error or "尚未获得 GitHub API 数据"
        return {
            "meta": _base_meta(current_time, "sample", 0, None, [f"样例/空数据：{warning}"], 0),
            "repositories": [],
            "rankings": {"stars": [], "growth1d": [], "growth7d": [], "growth30d": [], "featured": [], "newcomers": []},
        }
    warnings: List[str] = []
    if fetch_error:
        warnings.append(fetch_error)
    effective_status = status or ("partial" if fetch_error else "live")
    last_success = iso(current_time) if effective_status in ("live", "partial") else (previous.get("meta") or {}).get("lastSuccessAt")
    repos = list(repositories)
    rankings = {
        "stars": _sort_ids(repos, "stars"),
        "growth1d": [],
        "growth7d": [],
        "growth30d": [],
        "featured": [r["id"] for r in repos if r.get("featured")],
        "newcomers": _newcomers(repos, current_time),
    }
    # _sort_ids needs a scalar field; rank growth lists explicitly by nested delta.
    for label in ("growth1d", "growth7d", "growth30d"):
        window = label.replace("growth", "")
        rankings[label] = [r["id"] for r in sorted([r for r in repos if (r.get("deltas") or {}).get(window) is not None], key=lambda r: (r.get("deltas") or {}).get(window, 0), reverse=True)]
    meta = _base_meta(current_time, effective_status, len(repos), last_success, warnings, observed_history_days(repos))
    return {"meta": meta, "repositories": repos, "rankings": rankings}


def candidate_repositories(client: GitHubClient, now: datetime) -> Tuple[List[Dict[str, Any]], List[str]]:
    raw_by_id: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []
    queries = [
        {"q": "stars:>1000", "sort": "stars", "order": "desc", "per_page": "30"},
        {"q": f"created:>={iso(now - timedelta(days=180))[:10]} stars:>100", "sort": "stars", "order": "desc", "per_page": "30"},
    ]
    for params in queries:
        try:
            result = client.request("/search/repositories", params)
            for item in result.get("items", []):
                if item.get("full_name"):
                    raw_by_id[item["full_name"]] = item
        except Exception as exc:
            errors.append(str(exc))
    # Fill gaps with curated candidates. Search responses already cover many of
    # them, so this normally costs fewer than 30 additional API calls.
    for repo_id in CURATED:
        if repo_id in raw_by_id:
            continue
        try:
            raw = client.request("/repos/" + quote(repo_id, safe="/"))
            if raw.get("full_name"):
                raw_by_id[raw["full_name"]] = raw
        except Exception as exc:
            errors.append(f"{repo_id}: {exc}")
        if client.requests >= client.max_requests:
            break
    return list(raw_by_id.values()), errors


def run(output: Path, history_root: Optional[Path] = None, token: Optional[str] = None, max_requests: int = DEFAULT_MAX_REQUESTS) -> Dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    history_root = history_root or Path("data/history")
    history_root.mkdir(parents=True, exist_ok=True)
    target = output / "projects.json"
    previous: Optional[Dict[str, Any]] = None
    try:
        previous = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = None
    now = utc_now()
    client = GitHubClient(token=token, max_requests=max_requests)
    try:
        raw_repos, errors = candidate_repositories(client, now)
    except Exception as exc:
        raw_repos, errors = [], [str(exc)]
    repos: List[Dict[str, Any]] = []
    for raw in raw_repos:
        try:
            repos.append(normalise_repo(raw, history_root, now))
        except (TypeError, ValueError, OSError) as exc:
            errors.append(f"{raw.get('full_name', 'unknown')}: {exc}")
    # If only a small fraction was available, retain untouched old rows so a
    # transient API failure never erases a useful local catalogue.
    warning = "; ".join(errors[:3]) if errors else None
    # A wholly failed refresh must enter the stale path before merging any
    # fallback rows; otherwise it would incorrectly advance lastSuccessAt.
    if repos and previous and previous.get("repositories") and len(repos) < max(3, len(previous["repositories"]) // 2):
        existing = {r.get("id") for r in repos}
        repos.extend(r for r in previous["repositories"] if r.get("id") not in existing)
        warning = (warning + "; " if warning else "") + "部分候选抓取失败，合并上次成功仓库"
    payload = build_payload(repos, previous=previous, now=now, fetch_error=warning, status=("partial" if errors else "live"))
    # Atomic replacement avoids leaving a truncated file if the process stops.
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(target)
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch GitHub repositories for Open Radar")
    parser.add_argument("--output", default="public/data", help="output directory containing projects.json")
    parser.add_argument("--history", default="data/history", help="directory for per-repository history snapshots")
    parser.add_argument("--max-requests", type=int, default=DEFAULT_MAX_REQUESTS, help="hard API request cap (default: %(default)s)")
    args = parser.parse_args(argv)
    try:
        payload = run(Path(args.output), Path(args.history), max_requests=max(1, min(args.max_requests, 58)))
    except Exception as exc:
        print(f"ingest failed: {exc}", file=sys.stderr)
        return 1
    meta = payload.get("meta", {})
    print(f"status={meta.get('status')} repositories={meta.get('repositoryCount')} generatedAt={meta.get('generatedAt')}")
    for warning in meta.get("warnings", [])[:3]:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
