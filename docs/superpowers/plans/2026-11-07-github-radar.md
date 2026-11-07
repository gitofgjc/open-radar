# GitHub Radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a polished static GitHub project radar with daily snapshots, explainable rankings, searchable exploration, local personal lists, and GitHub Pages automation.

**Architecture:** A Python ingest script calls GitHub REST API and writes versioned JSON under `public/data/`. A dependency-light static frontend reads that JSON and keeps personal state in localStorage. GitHub Actions runs ingest and deploys the static `public/` directory to Pages.

**Tech Stack:** HTML, CSS, vanilla JavaScript, Python 3 standard library, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-07-github-radar-design.md`

## Global Constraints

- Never expose GitHub credentials in frontend assets or logs.
- Do not claim growth values without real historical snapshots.
- Always show data source and last successful fetch time.
- Preserve last-known-good data when a fetch fails.
- Keep personal list data local to the browser in the MVP.

### Task 1: Data contracts and ingest pipeline

**Files:**
- Create: `scripts/ingest_github.py`
- Create: `scripts/sample_data.py`
- Create: `tests/test_ingest.py`
- Create: `public/data/projects.json`
- Create: `public/data/meta.json`

**Interfaces:**
- `scripts/ingest_github.py::calculate_deltas(snapshots) -> dict`
- `scripts/ingest_github.py::build_rankings(repositories, snapshots) -> dict`
- `scripts/ingest_github.py::write_payload(output_dir, payload) -> None`

- [ ] Write tests for delta windows, cold-start behavior, stale fallback, and explainable recommendation reasons.
- [ ] Run `python -m unittest tests/test_ingest.py` and verify the new tests fail before implementation.
- [ ] Implement deterministic ranking and JSON serialization using only the standard library.
- [ ] Add a sample-data generator so the UI is useful before the first API run.
- [ ] Run the test suite and validate the sample payload against the frontend contract.
- [ ] Commit as `feat: add github snapshot data pipeline`.

### Task 2: Static radar frontend

**Files:**
- Create: `public/index.html`
- Create: `public/styles.css`
- Create: `public/app.js`
- Create: `tests/test_frontend_contract.py`

**Interfaces:**
- `window.RadarApp` exposes `loadData()`, `renderRoute()`, and `getPersonalState()` for browser smoke tests.
- `projects.json` fields: `repositories`, `rankings`, `snapshots`, `meta`.

- [ ] Write a contract test that checks required navigation labels and data hooks exist.
- [ ] Run the test and verify it fails before frontend implementation.
- [ ] Implement the responsive shell, Today dashboard, Explore filters, detail drawer/page, My List, and Data status view.
- [ ] Add localStorage persistence for saves, tags, status, notes, and import/export.
- [ ] Add accessible keyboard navigation, empty states, stale-state banners, and escaped external text.
- [ ] Run static contract tests and browser smoke checks.
- [ ] Commit as `feat: build github radar frontend`.

### Task 3: CI, Pages deployment, and documentation

**Files:**
- Create: `.github/workflows/update-and-deploy.yml`
- Create: `.github/workflows/pages.yml`
- Create: `README.md`
- Create: `CONTRIBUTING.md`

**Interfaces:**
- Scheduled workflow invokes `python scripts/ingest_github.py --output public/data`.
- Pages workflow publishes `public/` as the artifact.

- [ ] Add a workflow_dispatch path and a daily UTC 00:17 schedule.
- [ ] Configure least-privilege Pages permissions and avoid logging secrets.
- [ ] Add stale fallback behavior and `[skip ci]` snapshot commits.
- [ ] Document local preview, data caveats, required repository settings, and first deployment steps.
- [ ] Validate YAML syntax and run the complete test suite.
- [ ] Commit as `ci: add daily refresh and pages deployment`.

### Task 4: Product verification and release readiness

**Files:**
- Modify: `public/styles.css`
- Modify: `public/app.js`
- Create: `tests/test_release_readiness.py`

- [ ] Add tests for missing-data and stale-data rendering contracts.
- [ ] Run all automated checks.
- [ ] Preview the site in a browser at desktop and mobile widths.
- [ ] Check links, filters, local persistence, and detail navigation.
- [ ] Make final visual and accessibility fixes.
- [ ] Commit as `test: verify release readiness`.
