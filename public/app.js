/* Open Radar · dependency-free browser application */
(function (root) {
  'use strict';

  const STORAGE_KEY = 'open-radar-personal-v1';
  const CATEGORIES = ['AI 与智能体', '开发工具', '自托管', '数据与分析', '设计与创作', '学习资源', '安全与隐私', '效率工具'];
  let storage = null;
  let payload = null;
  const STATUS_VALUES = ['want', 'evaluating', 'using', 'archived'];
  let currentRoute = 'explore';
  let routeDetailId = null;
  let exploreState = { query: '', category: 'all', language: 'all', license: 'all', activity: 'all', sort: 'stars', tab: 'all' };
  let rankingWindow = '1d';

  const safeStorage = () => {
    if (storage) return storage;
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        storage = window.localStorage;
        storage.getItem(STORAGE_KEY);
        return storage;
      }
    } catch (_) { /* private browsing or blocked storage */ }
    storage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
    return storage;
  };

  const clone = (value) => JSON.parse(JSON.stringify(value));
  const getPersonalState = () => {
    let parsed;
    try { parsed = JSON.parse(safeStorage().getItem(STORAGE_KEY) || 'null'); } catch (_) { parsed = null; }
    if (!parsed || typeof parsed !== 'object' || !parsed.items || typeof parsed.items !== 'object') return {};
    const items = {};
    Object.entries(parsed.items).forEach(([id, item]) => {
      if (!item || typeof item !== 'object') return;
      items[id] = {
        favorite: Boolean(item.favorite),
        status: STATUS_VALUES.includes(item.status) ? item.status : 'want',
        tags: Array.isArray(item.tags) ? item.tags.map(String).map(tag => tag.trim()).filter(Boolean).slice(0, 12) : [],
        note: String(item.note || '').slice(0, 2000)
      };
    });
    return items;
  };
  const writePersonal = (items) => safeStorage().setItem(STORAGE_KEY, JSON.stringify({ version: 1, items }));
  const configureStorage = (next) => { storage = next; };
  const resetPersonalState = () => safeStorage().removeItem(STORAGE_KEY);
  const updatePersonal = (id, changes) => {
    const items = getPersonalState();
    const previous = items[id] || { favorite: false, status: 'want', tags: [], note: '' };
    const next = { ...previous, ...changes };
    next.favorite = Boolean(next.favorite);
    next.status = STATUS_VALUES.includes(next.status) ? next.status : 'want';
    next.tags = Array.isArray(next.tags) ? next.tags.map(String).map(s => s.trim()).filter(Boolean).slice(0, 12) : [];
    next.note = String(next.note || '').slice(0, 2000);
    if (!next.favorite && next.status === 'want' && !next.tags.length && !next.note) delete items[id];
    else items[id] = next;
    writePersonal(items);
    return next;
  };
  const exportPersonalState = () => JSON.stringify({ version: 1, exportedAt: new Date().toISOString(), items: getPersonalState() }, null, 2);
  const importPersonalState = (value) => {
    const parsed = typeof value === 'string' ? JSON.parse(value) : value;
    if (!parsed || typeof parsed !== 'object' || !parsed.items || typeof parsed.items !== 'object') throw new Error('无效的清单文件');
    const items = {};
    Object.entries(parsed.items).forEach(([id, item]) => {
      if (!item || typeof item !== 'object') return;
      items[id] = { favorite: Boolean(item.favorite), status: STATUS_VALUES.includes(item.status) ? item.status : 'want', tags: Array.isArray(item.tags) ? item.tags.map(String).filter(Boolean).slice(0, 12) : [], note: String(item.note || '').slice(0, 2000) };
    });
    writePersonal(items);
    return items;
  };

  const normalizeRoute = (path) => {
    const clean = String(path || '').replace(/^#/, '').replace(/^\//, '');
    if (!clean) return 'explore';
    if (clean === 'today') return 'today';
    if (clean === 'explore') return 'explore';
    if (clean === 'rankings') return 'rankings';
    if (clean === 'list') return 'list';
    if (clean === 'data') return 'data';
    if (clean === 'detail' || clean.startsWith('project/')) return 'detail';
    return 'today';
  };
  const detailIdFromPath = (path) => {
    const clean = String(path || '').replace(/^#/, '').replace(/^\//, '');
    if (!clean.startsWith('project/')) return null;
    return decodeURIComponent(clean.slice(8));
  };

  const num = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  const formatNumber = (value) => {
    const n = num(value);
    if (n >= 1000000) return `${(n / 1000000).toFixed(n >= 10000000 ? 0 : 1)}M`;
    if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`;
    return String(Math.round(n));
  };
  const formatDateTime = (value) => {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '—';
    return date.toLocaleString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' });
  };
  const formatDate = (value) => {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '—';
    return date.toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' });
  };
  const relativeDate = (value) => {
    if (!value) return '未知时间';
    const diff = Math.max(0, Date.now() - new Date(value).getTime());
    const days = Math.floor(diff / 86400000);
    if (days === 0) return '今天更新';
    if (days === 1) return '昨天更新';
    if (days < 30) return `${days} 天前更新`;
    return formatDate(value);
  };
  const escapeHtml = (value) => String(value == null ? '' : value).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
  const normalizeRepo = (repo) => ({
    ...repo,
    id: repo.id || repo.fullName || `${repo.owner || 'unknown'}/${repo.name || 'project'}`,
    fullName: repo.fullName || repo.id || `${repo.owner || 'unknown'}/${repo.name || 'project'}`,
    owner: repo.owner || String(repo.fullName || repo.id || '').split('/')[0],
    name: repo.name || String(repo.fullName || repo.id || '').split('/').pop(),
    summary: repo.summary || repo.description || '暂无中文简介',
    description: repo.description || repo.summary || '暂无项目描述',
    category: CATEGORIES.includes(repo.category) ? repo.category : '效率工具',
    topics: Array.isArray(repo.topics) ? repo.topics : [],
    stars: num(repo.stars), forks: num(repo.forks), openIssues: num(repo.openIssues),
    growthRates: repo.growthRates || {}, deltas: repo.deltas || {}, history: Array.isArray(repo.history) ? repo.history : []
  });
  const repos = () => (payload && Array.isArray(payload.repositories) ? payload.repositories : []).map(normalizeRepo);
  const repoById = (id) => repos().find(repo => repo.id === id || repo.fullName === id);
  const categoryOf = (repo) => repo.category || '效率工具';

  const filterRepositories = (collection, options = {}) => {
    const opts = { query: '', category: 'all', language: 'all', license: 'all', activity: 'all', sort: 'stars', tab: 'all', ...options };
    const query = String(opts.query || '').trim().toLowerCase();
    let result = collection.map(normalizeRepo).filter(repo => {
      if (opts.category !== 'all' && categoryOf(repo) !== opts.category) return false;
      if (opts.language !== 'all' && (repo.language || '未标注') !== opts.language) return false;
      if (opts.license !== 'all' && (repo.license || '未标注') !== opts.license) return false;
      if (opts.activity !== 'all' && (Date.now() - new Date(repo.pushedAt || 0).getTime()) > Number(opts.activity) * 86400000) return false;
      if (opts.sort === 'growth' && growthValue(repo, '1d') == null) return false;
      if (opts.tab === 'featured' && !repo.featured) return false;
      if (opts.tab === 'new' && (Date.now() - new Date(repo.createdAt || 0).getTime()) > 1000 * 60 * 60 * 24 * 90) return false;
      if (!query) return true;
      const haystack = [repo.fullName, repo.name, repo.owner, repo.summary, repo.description, repo.category, repo.language, ...repo.topics].join(' ').toLowerCase();
      return haystack.includes(query);
    });
    const sorters = {
      stars: (a, b) => num(b.stars) - num(a.stars),
      growth: (a, b) => num(growthValue(b, '1d'), -Infinity) - num(growthValue(a, '1d'), -Infinity),
      recent: (a, b) => new Date(b.pushedAt || b.createdAt || 0) - new Date(a.pushedAt || a.createdAt || 0),
      forks: (a, b) => num(b.forks) - num(a.forks)
    };
    result.sort(sorters[opts.sort] || sorters.stars);
    return result;
  };

  const growthValue = (repo, window = '1d') => {
    const value = repo.growthRates && repo.growthRates[window];
    if (value != null && !Number.isNaN(Number(value))) return Number(value);
    const delta = repo.deltas && repo.deltas[window];
    return delta != null && !Number.isNaN(Number(delta)) ? Number(delta) : null;
  };
  const growthLabel = (repo, window = '1d') => {
    const value = repo.growthRates && repo.growthRates[window];
    if (value == null || Number.isNaN(Number(value))) return '趋势积累中';
    const percent = Number(value) * 100;
    return `${percent >= 0 ? '+' : ''}${percent.toFixed(Number.isInteger(percent) ? 0 : 1)}%`;
  };
  const statusLabel = (status) => ({ want: '想试', evaluating: '评估中', using: '使用中', archived: '归档' }[status] || '想试');
  const statusClass = (status) => ({ want: '', evaluating: 'watching', using: 'done', archived: '' }[status] || '');
  const iconStar = (filled = false) => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.8l2.47 5 5.53.8-4 3.9.94 5.5L12 16.4l-4.94 2.6.94-5.5-4-3.9 5.53-.8L12 3.8z" ${filled ? '' : 'fill="none" stroke="currentColor" stroke-width="1.5"'}/></svg>`;
  const projectHref = (id) => `#project/${encodeURIComponent(id)}`;

  const cardHtml = (repo) => {
    const personal = getPersonalState()[repo.id] || {};
    const growth = repo.growthRates && repo.growthRates['1d'];
    return `<article class="repo-card ${repo.featured ? 'featured' : ''}">
      <div class="repo-card-head"><a class="card-link" href="${projectHref(repo.id)}"><span class="repo-name">${escapeHtml(repo.fullName)}</span><span class="repo-owner">${escapeHtml(repo.owner)} · ${escapeHtml(repo.language || '未标注')}</span></a><button class="star-button ${personal.favorite ? 'is-saved' : ''}" data-action="favorite" data-id="${escapeHtml(repo.id)}" aria-label="${personal.favorite ? '取消收藏' : '收藏'} ${escapeHtml(repo.fullName)}" aria-pressed="${Boolean(personal.favorite)}">${iconStar(Boolean(personal.favorite))}</button></div>
      <a class="card-link" href="${projectHref(repo.id)}"><p class="repo-summary">${escapeHtml(repo.summary)}</p></a>
      <div class="repo-meta"><span class="pill">${escapeHtml(categoryOf(repo))}</span>${repo.featured ? '<span class="pill pill-green">编辑精选</span>' : ''}${repo.topics.slice(0, 2).map(topic => `<span class="pill">#${escapeHtml(topic)}</span>`).join('')}</div>
      <div class="repo-stats"><span>★ <b>${formatNumber(repo.stars)}</b></span><span>⑂ <b>${formatNumber(repo.forks)}</b></span><span class="growth">${growth == null ? '—' : growthLabel(repo)}</span><span class="faint" style="margin-left:auto">${relativeDate(repo.pushedAt)}</span></div>
    </article>`;
  };

  const emptyHtml = (title, description) => `<div class="empty-state"><div class="empty-icon">⌕</div><h3>${escapeHtml(title)}</h3><p>${escapeHtml(description)}</p></div>`;
  const staleBanner = () => {
    const meta = payload && payload.meta;
    if (!meta || !['stale', 'partial'].includes(meta.status)) return '';
    return `<div class="banner"><strong>${meta.status === 'stale' ? '数据处于保鲜期外' : '数据部分更新'}</strong><span>仍可浏览最近一次成功采集的项目快照${meta.lastSuccessAt ? ` · 上次成功 ${formatDate(meta.lastSuccessAt)}` : ''}。</span></div>`;
  };
  const renderToday = () => {
    const all = repos(); const featured = all.filter(repo => repo.featured); const picks = (featured.length ? featured : all).slice(0, 6);
    const meta = (payload && payload.meta) || {}; const growthCount = all.filter(repo => repo.growthRates && repo.growthRates['1d'] != null).length; const categoryCounts = CATEGORIES.map(category => all.filter(repo => categoryOf(repo) === category).length); const maxCategory = Math.max(1, ...categoryCounts);
    return `${staleBanner()}<section class="hero"><div class="hero-copy"><div class="eyebrow">${formatDate(meta.generatedAt || new Date())} · DAILY SIGNAL</div><h1>今天，<em>发现</em>值得<br>留下的项目。</h1><p>为中文开发者整理 GitHub 上正在发生的变化。先看一眼今日信号，再进入探索库，按你的问题、技术栈和阅读节奏找到下一件值得投入的事。</p></div><div class="hero-signal"><div class="signal-top"><strong>观察范围分布</strong><span>${all.length ? `${all.length} 个项目` : '等待数据'}</span></div><div class="signal-bars">${categoryCounts.map(count => `<i style="--h:${Math.max(8, Math.round((count / maxCategory) * 100))}%" title="${count} 个项目"></i>`).join('')}</div><div class="signal-foot"><span>快照 ${meta.historyDays ?? '—'} 天历史</span><b>${formatNumber(all.length)} <small class="faint">repos</small></b></div></div></section>
      <section class="kpi-grid"><div class="kpi"><span class="kpi-label">今日候选集</span><strong class="kpi-value">${formatNumber(all.length)}</strong><span class="kpi-note">来自当前观察范围</span></div><div class="kpi"><span class="kpi-label">编辑精选</span><strong class="kpi-value green">${formatNumber(featured.length)}</strong><span class="kpi-note">有明确入选理由</span></div><div class="kpi"><span class="kpi-label">已收藏项目</span><strong class="kpi-value">${formatNumber(Object.values(getPersonalState()).filter(item => item.favorite).length)}</strong><span class="kpi-note">只保存在你的浏览器</span></div><div class="kpi"><span class="kpi-label">数据状态</span><strong class="kpi-value" style="font-size:20px;margin-top:20px">${meta.status === 'live' ? 'LIVE' : (meta.status || 'SAMPLE').toUpperCase()}</strong><span class="kpi-note">${meta.lastSuccessAt ? `更新于 ${formatDate(meta.lastSuccessAt)}` : '等待首次快照'}</span></div></section>
      <section><div class="section-head"><div><div class="eyebrow">CURATED RADAR</div><h2 class="section-title" style="margin-top:11px">今天值得打开的项目</h2></div><a class="cta-link" href="#explore">进入探索库</a></div>${picks.length ? `<div class="card-grid">${picks.map(cardHtml).join('')}</div>` : emptyHtml('候选集正在准备', '数据文件尚未到达，稍后刷新或直接进入数据方法查看采集说明。')}</section>
      <section class="split-section"><div class="list-panel"><div class="section-head"><div><div class="eyebrow">WHY IT MATTERS</div><h2 style="margin-top:11px;font-size:23px">让推荐可解释</h2></div><a class="cta-link" href="#data">看方法</a></div><p class="muted" style="font-size:12px;line-height:1.8;max-width:520px">每个项目都保留来源、分类、更新时间和入选理由。趋势没有积累时，我们会明确告诉你“趋势积累中”，而不是填入一个看起来漂亮的数字。</p></div><div class="list-panel"><div class="section-head"><div><div class="eyebrow">QUICK RANK</div><h2 style="margin-top:11px;font-size:23px">星标榜单</h2></div></div><div class="mini-list">${all.slice().sort((a,b)=>b.stars-a.stars).slice(0,3).map((repo,i)=>`<a class="mini-item" href="${projectHref(repo.id)}"><span class="mini-rank">0${i+1}</span><span><span class="mini-title">${escapeHtml(repo.fullName)}</span><span class="mini-sub">${escapeHtml(categoryOf(repo))}</span></span><span class="mini-growth">★ ${formatNumber(repo.stars)}</span></a>`).join('') || '<span class="faint" style="font-size:12px">暂无排名</span>'}</div></div></section>`;
  };

  const renderExplore = () => {
    const all = repos(); const categories = [...new Set(all.map(categoryOf))].sort(); const languages = [...new Set(all.map(repo => repo.language || '未标注'))].sort(); const result = filterRepositories(all, exploreState);
    return `${staleBanner()}<section class="explore-head"><div><div class="eyebrow">THE LIBRARY</div><h1 style="margin-top:12px">探索库</h1><p>把搜索当作长期习惯。用一句问题、一个技术栈或一个主题切入，再用排序和标签缩小范围。</p></div><span class="result-count">${result.length} / ${all.length} 个项目</span></section><section class="toolbar"><input class="field" id="explore-query" aria-label="搜索项目" placeholder="搜索项目、描述、主题或语言…" value="${escapeHtml(exploreState.query)}"><select class="select" id="explore-category" aria-label="筛选分类"><option value="all">全部分类</option>${categories.map(category => `<option value="${escapeHtml(category)}" ${exploreState.category === category ? 'selected' : ''}>${escapeHtml(category)}</option>`).join('')}</select><select class="select" id="explore-language" aria-label="筛选语言"><option value="all">全部语言</option>${languages.map(language => `<option value="${escapeHtml(language)}" ${exploreState.language === language ? 'selected' : ''}>${escapeHtml(language)}</option>`).join('')}</select><select class="select" id="explore-license" aria-label="筛选许可证"><option value="all">全部许可证</option>${[...new Set(all.map(repo => repo.license || '未标注'))].sort().map(license => `<option value="${escapeHtml(license)}" ${exploreState.license === license ? 'selected' : ''}>${escapeHtml(license)}</option>`).join('')}</select><select class="select" id="explore-activity" aria-label="筛选活跃度"><option value="all">全部活跃度</option><option value="7" ${exploreState.activity === '7' ? 'selected' : ''}>近 7 天更新</option><option value="30" ${exploreState.activity === '30' ? 'selected' : ''}>近 30 天更新</option><option value="90" ${exploreState.activity === '90' ? 'selected' : ''}>近 90 天更新</option></select><select class="select" id="explore-sort" aria-label="排序方式"><option value="stars" ${exploreState.sort === 'stars' ? 'selected' : ''}>按星标最多</option><option value="growth" ${exploreState.sort === 'growth' ? 'selected' : ''}>按近期增长</option><option value="recent" ${exploreState.sort === 'recent' ? 'selected' : ''}>按最近更新</option><option value="forks" ${exploreState.sort === 'forks' ? 'selected' : ''}>按 Fork 数</option></select></section><div class="tabs" role="tablist"><button class="tab ${exploreState.tab === 'all' ? 'is-active' : ''}" data-action="tab" data-tab="all">全部项目</button><button class="tab ${exploreState.tab === 'featured' ? 'is-active' : ''}" data-action="tab" data-tab="featured">编辑精选</button><button class="tab ${exploreState.tab === 'new' ? 'is-active' : ''}" data-action="tab" data-tab="new">新近加入</button></div>${result.length ? `<div class="card-grid">${result.map(cardHtml).join('')}</div>` : emptyHtml('没有匹配的项目', '换一个关键词，或清空筛选条件。你的搜索只作用于当前快照，不会上传到任何地方。')}`;
  };

  const rankedIds = (key, fallback = []) => {
    const ids = payload && payload.rankings && Array.isArray(payload.rankings[key]) ? payload.rankings[key] : fallback;
    const map = new Map(repos().map(repo => [repo.id, repo]));
    const ordered = ids.map(id => map.get(id)).filter(Boolean);
    if (ordered.length) return ordered;
    if (key === 'growth1d' || key === 'growth7d' || key === 'growth30d') {
      const window = key.replace('growth', '');
      return repos().filter(repo => growthValue(repo, window) != null).sort((a, b) => num(growthValue(b, window), -Infinity) - num(growthValue(a, window), -Infinity));
    }
    if (key === 'newcomers') return [];
    return repos().slice().sort((a,b)=>b.stars-a.stars);
  };
  const rankPanelHtml = (title, key, scoreType) => `<section class="rank-panel"><h3>${title}</h3>${rankedIds(key).slice(0,7).map((repo,index) => `<a class="rank-item" href="${projectHref(repo.id)}"><span class="rank-number ${index === 0 ? 'top' : ''}">${String(index + 1).padStart(2, '0')}</span><span><span class="rank-name">${escapeHtml(repo.fullName)}</span><span class="rank-note">${escapeHtml(categoryOf(repo))}</span></span><span class="rank-score ${scoreType === 'growth' ? 'growth' : ''}">${scoreType === 'growth' ? `${growthLabel(repo, rankingWindow)} · Δ ${repo.deltas && repo.deltas[rankingWindow] == null ? '—' : num(repo.deltas[rankingWindow])}` : scoreType === 'featured' ? (repo.featured ? '精选' : '—') : `★ ${formatNumber(repo.stars)}`}</span></a>`).join('') || '<p class="faint" style="font-size:12px">暂无足够历史数据</p>'}</section>`;
  const renderRankings = () => `${staleBanner()}<section class="explore-head"><div><div class="eyebrow">SIGNAL BOARD</div><h1 style="margin-top:12px">排行</h1><p>从当前候选集里观察星标规模、近期变化和编辑精选。增长榜只显示真实历史数据。</p></div></section><div class="tabs" role="tablist"><button class="tab ${rankingWindow === '1d' ? 'is-active' : ''}" data-action="ranking-window" data-window="1d">近 1 天</button><button class="tab ${rankingWindow === '7d' ? 'is-active' : ''}" data-action="ranking-window" data-window="7d">近 7 天</button><button class="tab ${rankingWindow === '30d' ? 'is-active' : ''}" data-action="ranking-window" data-window="30d">近 30 天</button></div><div class="rank-grid">${rankPanelHtml('星标最多', 'stars', 'stars')}${rankPanelHtml('近期增长', `growth${rankingWindow}`, 'growth')}${rankPanelHtml('编辑精选', 'featured', 'featured')}</div><section class="detail-panel" style="margin-top:16px"><div class="section-head"><div><div class="eyebrow">COLD START</div><h2 style="margin-top:11px;font-size:22px">新近加入的热门项目</h2></div></div><div class="card-grid">${rankedIds('newcomers').slice(0,3).map(cardHtml).join('') || emptyHtml('还在积累新项目', '新近项目将在下一次数据快照中出现。')}</div></section>`;

  const renderList = () => {
    const items = getPersonalState(); const saved = repos().filter(repo => items[repo.id] && (items[repo.id].favorite || items[repo.id].status !== 'want' || items[repo.id].note || items[repo.id].tags.length));
    return `<section class="explore-head"><div><div class="eyebrow">YOUR SPACE</div><h1 style="margin-top:12px">我的清单</h1><p>收藏、稍后阅读、标签和笔记只保存在当前浏览器。导出 JSON 可以带走这份个人上下文。</p></div><div class="action-row"><button class="button" data-action="export">导出清单</button><button class="button" data-action="import">导入 JSON</button><input id="import-file" type="file" accept="application/json" hidden></div></section><div class="list-layout"><aside class="list-sidebar"><h3>按状态整理</h3><div class="list-nav"><button class="is-active" data-action="list-filter" data-filter="all">全部收藏 <span>${saved.length}</span></button><button data-action="list-filter" data-filter="want">想试 <span>${saved.filter(repo => items[repo.id].status === 'want').length}</span></button><button data-action="list-filter" data-filter="evaluating">评估中 <span>${saved.filter(repo => items[repo.id].status === 'evaluating').length}</span></button><button data-action="list-filter" data-filter="using">使用中 <span>${saved.filter(repo => items[repo.id].status === 'using').length}</span></button><button data-action="list-filter" data-filter="archived">归档 <span>${saved.filter(repo => items[repo.id].status === 'archived').length}</span></button></div></aside><section class="list-main"><div class="section-head"><h2 class="section-title" style="font-size:22px">已保存的项目</h2><span class="result-count">本地数据 · ${saved.length} 项</span></div><div id="list-results">${saved.length ? saved.map(repo => { const item = items[repo.id]; return `<article class="list-card" data-list-status="${escapeHtml(item.status)}"><div><a href="${projectHref(repo.id)}"><h3>${escapeHtml(repo.fullName)}</h3><p>${escapeHtml(item.note || repo.summary)}</p></a><div class="repo-meta" style="margin-top:10px">${item.tags.map(tag=>`<span class="tag">#${escapeHtml(tag)}</span>`).join('')}<span class="status-badge ${statusClass(item.status)}">${statusLabel(item.status)}</span></div></div><div class="list-actions"><a class="button" href="${projectHref(repo.id)}">打开</a><button class="star-button is-saved" data-action="favorite" data-id="${escapeHtml(repo.id)}" aria-label="取消收藏">${iconStar(true)}</button></div></article>`; }).join('') : emptyHtml('清单还是空的', '在探索库里点击星标，或者打开任意项目保存状态、标签和阅读笔记。')}</div></section></div>`;
  };

  const trendSvg = (repo) => {
    const history = repo.history.filter(point => point && point.stars != null).slice(-14);
    if (history.length < 2) return `<div class="empty-state" style="min-height:140px"><div class="empty-icon">∿</div><p>历史快照不足，趋势会在后续采集中出现。</p></div>`;
    const values = history.map(point => num(point.stars)); const min = Math.min(...values); const max = Math.max(...values); const range = Math.max(1, max - min); const width = 720; const height = 150; const points = values.map((value, index) => `${(index / (values.length - 1)) * width},${height - 18 - ((value - min) / range) * (height - 38)}`); const area = `0,${height} ${points.join(' ')} ${width},${height}`;
    return `<div class="trend-wrap"><svg class="trend-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(repo.fullName)} 星标趋势"><defs><linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#a7f45d" stop-opacity=".24"/><stop offset="1" stop-color="#a7f45d" stop-opacity="0"/></linearGradient></defs><line class="gridline" x1="0" y1="30" x2="720" y2="30"/><line class="gridline" x1="0" y1="75" x2="720" y2="75"/><line class="gridline" x1="0" y1="120" x2="720" y2="120"/><polygon class="area" points="${area}"/><polyline class="line" points="${points.join(' ')}"/>${points.map(point=>{const [x,y]=point.split(',');return `<circle class="point" cx="${x}" cy="${y}" r="3"/>`;}).join('')}</svg></div><p class="trend-note">${formatDate(history[0].date)} — ${formatDate(history[history.length - 1].date)} · ${history.length} 个快照</p>`;
  };
  const renderDetail = (id) => {
    const repo = repoById(id); if (!repo) return `<a class="back-link" href="#explore">← 返回探索库</a>${emptyHtml('找不到这个项目', '它可能已经离开当前快照，返回探索库查看最新候选集。')}`;
    const personal = getPersonalState()[repo.id] || { favorite: false, status: 'want', tags: [], note: '' };
    return `<a class="back-link" href="#explore">← 返回探索库</a><div class="detail-layout"><section><div class="detail-title"><div><div class="eyebrow">PROJECT DETAIL</div><h1>${escapeHtml(repo.name)}</h1><span class="repo-owner">${escapeHtml(repo.fullName)} · ${escapeHtml(repo.language || '未标注')}</span></div><button class="star-button ${personal.favorite ? 'is-saved' : ''}" data-action="favorite" data-id="${escapeHtml(repo.id)}" aria-label="${personal.favorite ? '取消收藏' : '收藏'} ${escapeHtml(repo.fullName)}" aria-pressed="${Boolean(personal.favorite)}">${iconStar(Boolean(personal.favorite))}</button></div><p class="detail-description">${escapeHtml(repo.summary || repo.description)}</p>${repo.description && repo.summary && repo.description !== repo.summary ? `<p class="muted" style="font-size:12px;line-height:1.7;margin:-10px 0 24px"><span class="faint">GitHub 原始描述：</span>${escapeHtml(repo.description)}</p>` : ''}<div class="detail-chips"><span class="pill pill-green">${escapeHtml(categoryOf(repo))}</span>${repo.topics.map(topic=>`<span class="pill">#${escapeHtml(topic)}</span>`).join('')}</div><div class="detail-panel"><h2>项目脉搏</h2><div class="detail-stats"><div class="detail-stat"><span>Stars</span><b>${formatNumber(repo.stars)}</b></div><div class="detail-stat"><span>Forks</span><b>${formatNumber(repo.forks)}</b></div><div class="detail-stat"><span>24h 增长</span><b class="green">${growthLabel(repo)}</b></div></div>${trendSvg(repo)}</div><div class="detail-panel"><h2>为什么在这里</h2><ul class="reason-list">${(repo.reasons && repo.reasons.length ? repo.reasons : ['项目来自当前观察范围。']).map(reason=>`<li>${escapeHtml(reason)}</li>`).join('')}</ul></div></section><aside><div class="detail-panel side-card"><h3>来源与状态</h3><div class="data-row"><span>最后更新</span><strong>${relativeDate(repo.pushedAt)}</strong></div><div class="data-row"><span>许可证</span><strong>${escapeHtml(repo.license || '未标注')}</strong></div><div class="data-row"><span>项目主页</span><strong><a class="cta-link" href="${escapeHtml(repo.url || '#')}" target="_blank" rel="noreferrer">GitHub</a></strong></div></div><div class="detail-panel notes"><h3>加入我的阅读节奏</h3><label class="faint" style="font-size:10px" for="detail-status">阅读状态</label><select class="select status-select" id="detail-status" data-action="status" data-id="${escapeHtml(repo.id)}"><option value="want" ${personal.status === 'want' ? 'selected' : ''}>想试</option><option value="evaluating" ${personal.status === 'evaluating' ? 'selected' : ''}>评估中</option><option value="using" ${personal.status === 'using' ? 'selected' : ''}>使用中</option><option value="archived" ${personal.status === 'archived' ? 'selected' : ''}>归档</option></select><label class="faint" style="font-size:10px" for="detail-tags">标签（逗号分隔）</label><input class="field" id="detail-tags" value="${escapeHtml(personal.tags.join(', '))}" placeholder="例如：agent, python" style="margin:8px 0 14px"><label class="faint" style="font-size:10px" for="detail-note">个人笔记</label><textarea id="detail-note" data-action="note" data-id="${escapeHtml(repo.id)}" placeholder="记下你为什么想看、下一步要试什么…">${escapeHtml(personal.note)}</textarea><div class="action-row"><button class="button primary" data-action="save-note" data-id="${escapeHtml(repo.id)}">保存笔记</button><a class="button" href="${escapeHtml(repo.url || '#')}" target="_blank" rel="noreferrer">打开 GitHub ↗</a></div></div></aside></div>`;
  };

  const renderData = () => { const meta = (payload && payload.meta) || {}; const all = repos(); return `<section class="explore-head"><div><div class="eyebrow">TRANSPARENCY LOG</div><h1 style="margin-top:12px">数据方法</h1><p>知道数据从哪里来、什么时候更新、哪些数字还需要时间积累，才能放心把它放进自己的工作流。</p></div></section><div class="data-layout"><section class="data-card"><h3>当前快照</h3><div class="data-row"><span>状态</span><strong class="${meta.status === 'stale' ? 'faint' : 'green'}">${escapeHtml((meta.status || 'sample').toUpperCase())}</strong></div><div class="data-row"><span>生成时间</span><strong>${formatDateTime(meta.generatedAt)}</strong></div><div class="data-row"><span>上次成功采集</span><strong>${formatDateTime(meta.lastSuccessAt)}</strong></div><div class="data-row"><span>项目数</span><strong>${formatNumber(meta.repositoryCount || all.length)}</strong></div><div class="data-row"><span>来源</span><strong>${escapeHtml(meta.source || 'GitHub REST API')}</strong></div>${Array.isArray(meta.warnings) && meta.warnings.length ? `<div class="banner" style="margin-top:16px;margin-bottom:0"><strong>采集提示</strong><span>${meta.warnings.map(w => escapeHtml(w)).join(' · ')}</span></div>` : ''}</section><section class="data-card"><h3>观察范围</h3><div class="data-row"><span>覆盖说明</span><strong>${escapeHtml(meta.coverage || '当前配置的公开候选集')}</strong></div><div class="data-row"><span>历史窗口</span><strong>${meta.historyDays ?? '—'} 天</strong></div><div class="data-row"><span>下次更新</span><strong>${escapeHtml(meta.nextUpdate || '按计划运行')}</strong></div><div class="data-row"><span>浏览器范围</span><strong>仅当前浏览器</strong></div></section><section class="data-card wide"><h3>从 GitHub 到你的清单</h3><div class="method-steps"><div class="method-step"><b>01 / 采集</b><h4>每日抓取公开信息</h4><p>定时任务读取 GitHub REST API，保留项目描述、语言、星标和更新时间。</p></div><div class="method-step"><b>02 / 解释</b><h4>标注分类与入选理由</h4><p>分类默认落在八个主题中，缺失分类会归入“效率工具”，推荐理由随项目保存。</p></div><div class="method-step"><b>03 / 保留</b><h4>收藏由浏览器保管</h4><p>星标、状态、标签和笔记写入 localStorage。导入导出 JSON 可迁移这份个人视图。</p></div></div></section></div>`; };

  const renderRoute = (route = currentRoute, detailId = routeDetailId) => {
    currentRoute = normalizeRoute(route); routeDetailId = detailId || (currentRoute === 'detail' ? detailIdFromPath(route) : null);
    const app = typeof document !== 'undefined' ? document.getElementById('app') : null;
    if (!app) return { route: currentRoute, html: '' };
    const views = { today: renderToday, explore: renderExplore, rankings: renderRankings, list: renderList, data: renderData, detail: () => renderDetail(routeDetailId) };
    app.innerHTML = (views[currentRoute] || renderToday)();
    document.querySelectorAll('[data-route]').forEach(link => link.classList.toggle('is-active', link.dataset.route === currentRoute));
    if (typeof window !== 'undefined') window.scrollTo({ top: 0, behavior: 'smooth' });
    bindView();
    return { route: currentRoute, html: app.innerHTML };
  };

  const updateStatusHeader = () => {
    const meta = (payload && payload.meta) || {}; const label = document.getElementById('header-status'); const dot = document.querySelector('.status-dot');
    if (label) label.textContent = meta.status === 'live' ? '实时快照' : meta.status === 'stale' ? '使用旧快照' : '演示数据';
    if (dot) dot.classList.toggle('is-stale', meta.status === 'stale' || meta.status === 'partial');
  };
  const bindView = () => {
    const app = document.getElementById('app'); if (!app) return;
    app.querySelectorAll('[data-action="favorite"]').forEach(button => button.addEventListener('click', event => { event.preventDefault(); event.stopPropagation(); const id = button.dataset.id; const current = getPersonalState()[id] || {}; updatePersonal(id, { favorite: !current.favorite }); renderRoute(currentRoute, routeDetailId); }));
    app.querySelectorAll('[data-action="ranking-window"]').forEach(button => button.addEventListener('click', () => { rankingWindow = button.dataset.window || '1d'; renderRoute('rankings'); }));
    app.querySelectorAll('[data-action="tab"]').forEach(button => button.addEventListener('click', () => { exploreState.tab = button.dataset.tab || 'all'; renderRoute('explore'); }));
    const query = app.querySelector('#explore-query'); if (query) query.addEventListener('input', () => { exploreState.query = query.value; const active = document.activeElement === query; renderRoute('explore'); if (active) { const next = document.getElementById('explore-query'); next.focus(); next.setSelectionRange(next.value.length, next.value.length); } });
    ['category', 'language', 'license', 'activity', 'sort'].forEach(key => { const el = app.querySelector(`#explore-${key}`); if (el) el.addEventListener('change', () => { exploreState[key] = el.value; renderRoute('explore'); }); });
    app.querySelectorAll('[data-action="list-filter"]').forEach(button => button.addEventListener('click', () => { app.querySelectorAll('[data-list-status]').forEach(card => { card.hidden = button.dataset.filter !== 'all' && card.dataset.listStatus !== button.dataset.filter; }); app.querySelectorAll('[data-action="list-filter"]').forEach(item => item.classList.toggle('is-active', item === button)); }));
    const exportButton = app.querySelector('[data-action="export"]'); if (exportButton) exportButton.addEventListener('click', () => { const blob = new Blob([exportPersonalState()], { type: 'application/json' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = 'open-radar-list.json'; link.click(); URL.revokeObjectURL(url); });
    const importButton = app.querySelector('[data-action="import"]'); const importFile = app.querySelector('#import-file'); if (importButton && importFile) { importButton.addEventListener('click', () => importFile.click()); importFile.addEventListener('change', async () => { const file = importFile.files && importFile.files[0]; if (!file) return; try { importPersonalState(await file.text()); renderRoute('list'); } catch (error) { window.alert(error.message || '导入失败'); } }); }
    const status = app.querySelector('[data-action="status"]'); if (status) status.addEventListener('change', () => updatePersonal(status.dataset.id, { status: status.value }));
    const saveNote = app.querySelector('[data-action="save-note"]'); if (saveNote) saveNote.addEventListener('click', () => { const note = app.querySelector('#detail-note'); const tags = app.querySelector('#detail-tags'); updatePersonal(saveNote.dataset.id, { note: note ? note.value : '', tags: tags ? tags.value.split(',').map(tag => tag.trim()).filter(Boolean) : [] }); saveNote.textContent = '已保存'; setTimeout(() => { saveNote.textContent = '保存笔记'; }, 1600); });
  };
  const loadData = async () => {
    if (payload) return payload;
    if (typeof fetch !== 'function') throw new Error('当前环境不支持 fetch');
    const response = await fetch('./data/projects.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`数据请求失败（${response.status}）`);
    payload = await response.json();
    if (!payload || !Array.isArray(payload.repositories)) throw new Error('项目数据格式不完整');
    return payload;
  };
  const boot = async () => {
    try { await loadData(); updateStatusHeader(); renderRoute(window.location.hash, detailIdFromPath(window.location.hash)); }
    catch (error) { const app = document.getElementById('app'); if (app) app.innerHTML = `<div class="error-state"><strong>数据暂时不可用</strong><p>${escapeHtml(error.message)}。请确认你是通过本地服务器访问，并在网络恢复后重试。</p><button class="button primary" data-action="retry">重新读取</button></div>`; const retry = app && app.querySelector('[data-action="retry"]'); if (retry) retry.addEventListener('click', () => { payload = null; boot(); }); }
  };
  const RadarApp = { loadData, renderRoute, getPersonalState, configureStorage, resetPersonalState, updatePersonal, exportPersonalState, importPersonalState, normalizeRoute, filterRepositories };
  if (typeof module !== 'undefined' && module.exports) module.exports = { RadarApp };
  if (root) root.RadarApp = RadarApp;
  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    window.addEventListener('hashchange', () => renderRoute(normalizeRoute(window.location.hash), detailIdFromPath(window.location.hash)));
    document.addEventListener('DOMContentLoaded', boot);
  }
})(typeof window !== 'undefined' ? window : globalThis);
