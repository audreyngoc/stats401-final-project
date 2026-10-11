const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('fs'),assert=require('assert');
const root=require('path').resolve(__dirname,'..');

const requests=[];const errors=[]; 
const vc=new VirtualConsole();
vc.on('jsdomError',e=>errors.push(e.stack));
vc.on('error',(...e)=>errors.push(e.map(String).join(' ')));

(async()=>{
    const dom=new JSDOM(
        fs.readFileSync(root+'/index.html','utf8'),{
                runScripts:'outside-only',pretendToBeVisual:true,url:'http://127.0.0.1:8000/',virtualConsole:vc,beforeParse(w){
                    w.fetch=async(url,opts)=>{const u=new URL(url,'http://127.0.0.1:8000/');requests.push(u.href);assert.equal(u.origin,'http://127.0.0.1:8000','External data request forbidden');return new Response(fs.readFileSync(root+u.pathname),{status:200});};w.AbortController=AbortController;
                    Object.defineProperty(w.SVGElement.prototype,'viewBox',{get(){const a=(this.getAttribute('viewBox')||'0 0 1140 670').split(/\s+/).map(Number);return {baseVal:{x:a[0],y:a[1],width:a[2],height:a[3]}};}});
            }
        }
    );

    const w=dom.window;
    for(const tag of w.document.querySelectorAll('script[src]'))w.eval(fs.readFileSync(root+'/'+tag.getAttribute('src'),'utf8'));
    const model=await w.knowledgeReady;await new Promise(r=>setTimeout(r,1800));

    console.log('initial',model.nodes.length,w.document.querySelectorAll('.tree-node').length,w.document.querySelectorAll('.network-node').length,w.document.querySelectorAll('.scatter-point').length);

    assert.equal(model.nodes.length,10000);
    assert.equal(model.distances.size,9985);
    assert.equal(model.neighbors(1164).length,10);
    assert.equal(model.neighbors(1164)[0].title,'ChatGPT');

    assert.equal(w.document.querySelectorAll('.tree-node').length,11);
    assert.equal(w.document.querySelectorAll('.network-node').length,14);

    w.document.getElementById('tree-expand').click();await new Promise(r=>setTimeout(r,200));
    assert.equal(w.document.querySelectorAll('.tree-node').length,111);

    const ids=model.neighbors(1164).map(n=>n.article_id);
    for(const id of ids){assert.equal(model.neighbors(id,[1164,id]).length,10);}

    w.document.getElementById('network-articles').click();
    await new Promise(r=>setTimeout(r,250));
    assert.equal(w.document.querySelectorAll('.network-node').length,80);

    model.select(72417803);
    assert(w.document.querySelectorAll('.tree-node.is-selected').length>0);
    assert.equal(w.document.querySelectorAll('.network-node.is-selected').length,1);
    assert(w.document.querySelector('.article-detail h3').textContent==='ChatGPT');

    assert(w.document.querySelector('.network-link[marker-end]'));

    const links=Array.from(w.document.querySelectorAll('.network-link'));
    console.log('selected incident links',links.length);

    w.document.getElementById('clear-selection').click();
    assert.equal(model.selectedId,null);

    w.document.getElementById('tree-collapse').click();
    assert.equal(w.document.querySelectorAll('.tree-node').length,11);

    await w.searchKnowledge('https://en.wikipedia.org/wiki/Machine_learning');
    assert.equal(model.seedId,233488);
    assert.equal(w.document.getElementById('current-seed').textContent,'Machine learning');

    await w.searchKnowledge('not an existing title 123456');
    assert(w.document.getElementById('search-status').textContent.includes('No exact match'));
    assert.equal(model.seedId,233488);

    await w.searchKnowledge('https://example.com/wiki/Bad');
    assert(w.document.getElementById('search-status').textContent.includes('English Wikipedia'));

    w.document.getElementById('reset-seed').click();
    await new Promise(r=>setTimeout(r,200));
    assert.equal(model.seedId,1164);

    // Directed BFS and missingness behavior on a small asymmetric fixture.

    const ns=[1,2,3,4].map(id=>({article_id:id,title:'N'+id,is_seed:id===1,pageviews_status:id===3?'partial':'complete',total_views_12m:100+id}));
    const tiny=new w.KnowledgeModel(ns,[[1],[2],[],[]],[],{});
    assert.equal(tiny.distances.get(3),2);assert(!tiny.distances.has(4));
    assert.equal(tiny.neighbors(2).length,0);

    assert.equal(w.document.getElementById('live-search'),null);
    assert.equal(typeof w.LiveWikipedia,'undefined');
    assert(requests.length>0);assert(requests.every(url=>new URL(url).pathname.startsWith('/data/')));
    console.log('PASS: every data request uses local supplied files; no external acquisition code or controls.');

    assert.deepEqual(errors,[]);
    console.log('PASS: snapshot load, full data, rankings, 10x10 tree, collapse, directed BFS, linked selection, arrows, network cap, URL search, invalid search preservation, missing pageviews.');
    dom.window.close();
})().catch(e=>{console.error(e,errors);process.exit(1)});
