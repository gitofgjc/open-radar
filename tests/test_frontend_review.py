import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
const {RadarApp}=require('./public/app.js');
const base = {meta:{status:'partial',historyDays:0},repositories:[],rankings:{}};
const app={innerHTML:'',querySelectorAll:()=>[],querySelector:()=>null};
global.document={getElementById:id=>id==='app'?app:null,querySelectorAll:()=>[],querySelector:()=>null};
global.fetch=async()=>({ok:true,json:async()=>base});
const store=new Map();
RadarApp.configureStorage({getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)});
'''


class FrontendReviewTests(unittest.TestCase):
    def node(self, code):
        result = subprocess.run(['node','-e',HARNESS+'\n(async()=>{\n'+code+'\n})().catch(e=>{console.error(e);process.exit(1)});'],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)

    def test_growth_sort_uses_absolute_delta_consistently(self):
        result = self.node(r'''
const rows=[{id:'small/a',stars:20,deltas:{'1d':10},growthRates:{'1d':1}},{id:'large/b',stars:10000,deltas:{'1d':100},growthRates:{'1d':0.01}},{id:'rate/c',stars:300,growthRates:{'1d':0.5},deltas:{'1d':null}}];
console.log(JSON.stringify(RadarApp.filterRepositories(rows,{sort:'growth'}).map(r=>r.id)));
''')
        self.assertEqual(result,['large/b','small/a'])

    def test_absent_saved_project_keeps_placeholder_and_real_favorite_state(self):
        result = self.node(r'''
await RadarApp.loadData();
RadarApp.updatePersonal('old/repo',{favorite:false,status:'using',note:'保留'});
const html=RadarApp.renderRoute('list').html;
console.log(JSON.stringify({retained:html.includes('old/repo'),missing:html.includes('不在当前快照'),favoriteFalse:html.includes('aria-pressed="false"')}));
''')
        self.assertEqual(result,{'retained':True,'missing':True,'favoriteFalse':True})

    def test_legacy_saved_status_is_not_silently_deleted(self):
        result = self.node(r'''
RadarApp.importPersonalState({items:{'legacy/repo':{status:'saved',favorite:false,tags:[],note:''}}});
console.log(JSON.stringify(RadarApp.getPersonalState()['legacy/repo']));
''')
        self.assertEqual(result['status'],'want')
        self.assertTrue(result['favorite'])

    def test_external_links_reject_script_schemes_and_partial_has_own_status(self):
        result = self.node(r'''
base.repositories=[{id:'a/a',name:'a',url:'javascript:alert(1)',homepage:'data:text/html,hello',stars:1}];
await RadarApp.loadData();
const detail=RadarApp.renderRoute('project/a%2Fa').html;
console.log(JSON.stringify({unsafe:detail.includes('javascript:'),partial:RadarApp.renderRoute('data').html.includes('部分更新')}));
''')
        self.assertEqual(result,{'unsafe':False,'partial':True})

    def test_explore_paginates_and_today_zero_categories_are_labelled(self):
        result = self.node(r'''
base.repositories=Array.from({length:31},(_,i)=>({id:'a/r'+i,name:'r'+i,stars:i,category:'开发工具'}));
await RadarApp.loadData();
const explore=RadarApp.renderRoute('explore').html;
const today=RadarApp.renderRoute('today').html;
console.log(JSON.stringify({visible:(explore.match(/class="repo-card /g)||[]).length,paging:explore.includes('下一页'),zero:today.includes('0 个项目'),label:today.includes('开发工具')}));
''')
        self.assertEqual(result,{'visible':24,'paging':True,'zero':True,'label':True})

    def test_ime_input_does_not_replace_active_field_until_composition_end(self):
        result = self.node(r'''
let renders=0;const listeners={};
const query={value:'智',addEventListener:(name,fn)=>listeners[name]=fn,focus:()=>{},setSelectionRange:()=>{}};
app.querySelector=selector=>selector==='#explore-query'?query:null;
Object.defineProperty(app,'innerHTML',{get:()=>'',set:()=>renders++});
await RadarApp.loadData();RadarApp.renderRoute('explore');const before=renders;
if(listeners.compositionstart)listeners.compositionstart({});
listeners.input({isComposing:true});const during=renders;
query.value='智能';if(listeners.compositionend)listeners.compositionend({});
console.log(JSON.stringify({before,during,after:renders}));
''')
        self.assertEqual(result['during'],result['before'])
        self.assertGreater(result['after'],result['during'])

    def test_trend_points_include_timestamp_labels(self):
        result = self.node(r'''
base.repositories=[{id:'a/a',name:'a',stars:2,history:[{date:'2026-11-07T00:00:00Z',stars:1},{date:'2026-11-07T05:00:00Z',stars:2}]}];
await RadarApp.loadData();
const detail=RadarApp.renderRoute('project/a%2Fa').html;
console.log(JSON.stringify({pointTitles:(detail.match(/<title>/g)||[]).length,includesTimes:detail.includes('00:00')&&detail.includes('05:00')}));
''')
        self.assertEqual(result,{'pointTitles':2,'includesTimes':True})


if __name__ == '__main__':
    unittest.main()
