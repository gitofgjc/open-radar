# 贡献与维护

## 开发边界

前端代码在 `public/`，数据抓取在 `scripts/`，自动化在 `.github/workflows/`。不要在前端代码或生成的 JSON 中写入 GitHub token、PAT 或其他凭据。外部文本必须在渲染前转义；排名和增长必须能从当前数据与历史快照解释。

## 本地运行

```bash
python3 -m http.server --directory public 4173
python3 -m unittest discover -s tests -v
```

## 数据刷新约定

`update-and-deploy.yml` 在 UTC 00:17（北京时间 08:17 起）和手动触发时运行 `python scripts/ingest_github.py --output public/data`。任务失败时应保留 last-known-good 数据并写入 `meta.status = "stale"` 与可读警告；禁止用估算或插值填充 Star 增长。提交每日快照时使用 `[skip ci]`，避免刷新任务循环触发自身。

## GitHub 权限与安全

首次部署只需要仓库所有者在 GitHub 完成登录，并授予目标仓库的 push 权限；不需要把密码提供给任何人。默认使用 Actions 自动注入的 `GITHUB_TOKEN`，不打印该变量，也不把它传给浏览器。若确实需要 PAT，将其保存为仓库 **Settings → Secrets and variables → Actions** 中的 Secret，选择最小的只读 public-data 权限，并轮换过期 token。

Pages 工作流只读仓库内容并使用 Pages 的 OIDC 部署权限；刷新工作流才拥有提交数据所需的 `contents: write`。不要让来自不可信 fork 的工作流获得写权限。

## 提交前检查

- 运行完整测试并确认没有 token 出现在 diff、构建产物或日志中。
- 手动检查 stale、无数据和历史不足状态仍然可读。
- 让数据来源、抓取时间和统计窗口在页面可见。
