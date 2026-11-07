import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"


class FrontendContractTests(unittest.TestCase):
    def run_node(self, script):
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if result.returncode:
            self.fail(f"node failed:\nSTDOUT\n{result.stdout}\nSTDERR\n{result.stderr}")
        return json.loads(result.stdout)

    def test_shell_has_required_routes_and_accessible_hooks(self):
        html = (PUBLIC / "index.html").read_text(encoding="utf-8")
        for label in ("今日", "探索", "排行", "我的清单", "数据方法"):
            self.assertIn(label, html)
        for hook in ('id="app"', 'data-route="today"', 'data-route="explore"', 'data-route="rankings"', 'data-route="list"', 'data-route="data"'):
            self.assertIn(hook, html)

    def test_routes_filter_and_sort_are_observable(self):
        script = r'''
const { RadarApp } = require('./public/app.js');
const repos = [
  {id:'alpha/a', fullName:'alpha/a', name:'a', owner:'alpha', summary:'智能体工作流', description:'agents', category:'AI 与智能体', language:'Python', stars:500, forks:4, pushedAt:'2026-11-01T00:00:00Z', featured:true, topics:['agent'], growthRates:{'1d':12}},
  {id:'beta/b', fullName:'beta/b', name:'b', owner:'beta', summary:'终端工具', description:'cli tools', category:'开发工具', language:'Go', stars:1200, forks:4, pushedAt:'2026-11-02T00:00:00Z', featured:false, topics:['cli'], growthRates:{'1d':3}},
  {id:'gamma/c', fullName:'gamma/c', name:'c', owner:'gamma', summary:'数据分析', description:'analytics', category:'数据与分析', language:'Python', stars:700, forks:8, pushedAt:'2026-11-03T00:00:00Z', featured:false, topics:['data'], growthRates:{'1d':null}}
];
const filtered = RadarApp.filterRepositories(repos, {query:'智能体', category:'all', language:'all', sort:'stars'});
const ranked = RadarApp.filterRepositories(repos, {query:'', category:'all', language:'all', sort:'stars'}).map(r => r.id);
const routeNames = ['/', '/explore', '/rankings', '/list', '/data', '/project/alpha/a', 'detail'].map(RadarApp.normalizeRoute);
console.log(JSON.stringify({filtered:filtered.map(r=>r.id), ranked, routeNames}));
'''
        result = self.run_node(script)
        self.assertEqual(result["filtered"], ["alpha/a"])
        self.assertEqual(result["ranked"], ["beta/b", "gamma/c", "alpha/a"])
        self.assertEqual(result["routeNames"], ["explore", "explore", "rankings", "list", "data", "detail", "detail"])

    def test_unknown_category_is_searchable_under_efficiency_tools(self):
        result = self.run_node(r'''
const { RadarApp } = require('./public/app.js');
const repos = [{id:'alpha/a', stars:10, category:'不支持的分类', summary:'Useful tool'}];
console.log(JSON.stringify(RadarApp.filterRepositories(repos, {category:'效率工具'}).map(r=>r.id)));
''')
        self.assertEqual(result, ["alpha/a"])

    def test_empty_hash_opens_explore_and_growth_does_not_fallback_to_stars(self):
        result = self.run_node(r'''
const { RadarApp } = require('./public/app.js');
const repos = [{id:'alpha/a', stars:100, growthRates:{'1d':null}, deltas:{'1d':null}}];
console.log(JSON.stringify({route:RadarApp.normalizeRoute('/'), growth:RadarApp.filterRepositories(repos,{sort:'growth'}).length}));
''')
        self.assertEqual(result, {"route": "explore", "growth": 0})

    def test_local_state_persists_favorites_status_tags_notes(self):
        script = r'''
const { RadarApp } = require('./public/app.js');
const store = new Map();
const storage = {getItem:key=>store.has(key)?store.get(key):null, setItem:(key,value)=>store.set(key,value), removeItem:key=>store.delete(key)};
RadarApp.configureStorage(storage);
RadarApp.resetPersonalState();
RadarApp.updatePersonal('alpha/a', {favorite:true, status:'want', tags:['agents','python'], note:'试读 README'});
const first = RadarApp.getPersonalState();
const exported = RadarApp.exportPersonalState();
RadarApp.resetPersonalState();
RadarApp.importPersonalState(exported);
console.log(JSON.stringify({saved:first, restored:RadarApp.getPersonalState()}));
'''
        result = self.run_node(script)
        expected = {"favorite": True, "status": "want", "tags": ["agents", "python"], "note": "试读 README"}
        self.assertEqual(result["saved"]["alpha/a"], expected)
        self.assertEqual(result["restored"]["alpha/a"], expected)


if __name__ == "__main__":
    unittest.main()
