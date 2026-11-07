# Open Radar / 开源雷达

Open Radar 是一个面向个人长期使用的 GitHub 开源项目发现页：**今日**给出短摘要，**探索**用于检索和筛选，**排行**展示 Stars 与真实快照增长，**我的清单**保存在浏览器本地，**数据方法**解释来源和统计口径。

## 本地预览

项目是无构建步骤的静态站点。启动本地服务器后访问 <http://localhost:4173>：

```bash
python3 -m http.server --directory public 4173
```

不要直接双击 `public/index.html`：浏览器的 `file://` 安全策略会阻止相对 JSON 加载。首次加载成功后，页面的阅读和已加载数据仍可在离线状态下使用；收藏、标签、状态和备注保存在当前浏览器的 localStorage 中，支持导出/导入迁移。

## 数据与更新

GitHub REST API 在构建时生成 `public/data/projects.json`。自动任务每天北京时间 08:17 起运行（对应 UTC 00:17，GitHub 可能延迟），也可以在 Actions 中使用 `workflow_dispatch` 手动运行。增长值只在存在真实历史快照时显示；冷启动或窗口不足时会显示“趋势积累中”。

抓取失败时，脚本保留最后一次成功数据并把状态标为 `stale`，页面会显示警告和最后成功时间。页面不会把 token 暴露给浏览器；Actions 使用 GitHub 自动提供的 `GITHUB_TOKEN`，只在工作流环境中读取。

## 发布到 GitHub Pages

1. 在自己的 GitHub 账号下创建仓库，并把代码推送到 `main`（仓库可以公开，便于免费使用 Pages）。首次推送需要你对仓库有 push 权限；不需要把 GitHub 密码或 token 发给开发者。
2. 在仓库 **Settings → Pages** 将 Source 设为 **GitHub Actions**。
3. `pages.yml` 会在 `public/` 变化时发布站点。刷新任务提交的新数据会自动触发发布；也可以手动运行部署任务。
4. 发布完成后，GitHub Actions 的部署任务会显示最终 URL，通常是 `https://<账号>.github.io/<仓库>/`。

如果仓库必须保持私有，请先确认你的 GitHub 账户计划支持私有仓库 Pages。需要更高 API 配额时，可自行创建只读 public-data fine-grained token 并存为仓库 Secret；普通每日刷新不需要额外 PAT。

## 质量检查

```bash
python3 -m unittest discover -s tests -v
```

工作流使用固定版本的 Actions，Pages 部署只授予 `contents: read`、`pages: write` 和 `id-token: write`；数据刷新任务才需要 `contents: write`，用于提交每日快照。
