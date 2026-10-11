(async function () {
  'use strict';
  const $=id=>document.getElementById(id);
  const fmt=value=>value==null?'Unavailable':d3.format(',')(value);
  
  window.knowledgeReady = (async () => {
    const [rows,adj,communities,manifest]=await Promise.all([
      d3.csv('data/ai_nodes_enriched.csv'),
      d3.json('data/ai_adjacency.json'),
      d3.json('data/ai_communities.json'),
      d3.json('data/ai_manifest.json')
    ]);
    const model=new KnowledgeModel(rows.map(KnowledgeUtils.parseNode),adj,communities,manifest);
    
    window.knowledge=model; window.snapshotModel=model;
    $('dataset-summary').textContent=`${fmt(model.nodes.length)} articles · ${fmt(manifest.directed_link_count)} directed hyperlinks · Sep 2025-Aug 2026 pageviews`;
    return model;
  })();
  
  function setStatus(message,error=false) { $('search-status').textContent=message; $('search-status').classList.toggle('error',error); }
  
  window.setKnowledgeStatus=setStatus;
  
  window.attachKnowledgeModel=function(model) {
    window.knowledge=model;
    model.on('seed',n=>{ $('current-seed').textContent=n.title; $('seed-search').value=n.title; setStatus('Search uses the supplied dataset and ranks articles with complete 12-month pageview records.'); });
    model.on('select',n=>{
      for(const panel of document.querySelectorAll('.article-detail')) {
        panel.replaceChildren();
        if(!n) { const p=document.createElement('p');p.textContent='Select an article to inspect its statistics and highlight its connections.';panel.append(p);continue; }
        const h=document.createElement('h3');h.textContent=n.title;panel.append(h);
        const dl=document.createElement('dl');
        const vals=[['Pageviews, Sep 2025-Aug 2026',n.pageviews_status==='complete'?fmt(n.total_views_12m):`${fmt(n.observed_views)} observed (${n.months_returned||0}/12 months)`],['Distance from current seed',model.distances.get(n.article_id)??'Unreachable'],['Incoming / outgoing links',`${fmt(n.local_indegree)} / ${fmt(n.local_outdegree)}`],['PageRank',n.pagerank==null?'Unavailable':d3.format('.5f')(n.pagerank)],['Betweenness',n.betweenness==null?'Unavailable':d3.format('.4f')(n.betweenness)],['Community',n.community==null?'Unavailable':`C${n.community+1}`],['Assigned subtopic',n.subtopic_title||'Seed / unassigned']];
        vals.forEach(([label,value])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;dl.append(dt,dd);});panel.append(dl);
        const p=document.createElement('p');p.className='detail-scope';p.textContent='PageRank and link counts use the supplied 10,000-article dataset. Betweenness is estimated from 32 sampled sources.';panel.append(p);
        const a=document.createElement('a');a.textContent='Read on Wikipedia ↗';a.href=`https://en.wikipedia.org/wiki/${encodeURIComponent(n.title.replace(/ /g,'_'))}`;a.target='_blank';a.rel='noopener';panel.append(a);
        const button=document.createElement('button');button.textContent='Explore from this article';button.onclick=()=>window.searchKnowledge(n.title);panel.append(button);
      }
      window.dispatchEvent(new CustomEvent('knowledge:selection',{detail:{articleId:n?.article_id??null,node:n,seedId:model.seedId,mode:model.mode}}));
    });
    model.on('seed',()=>window.dispatchEvent(new CustomEvent('knowledge:seed',{detail:{seedId:model.seedId,articleIds:[...model.distances.keys()],mode:model.mode}})));
    window.dispatchEvent(new CustomEvent('knowledge:model',{detail:model}));
    model.setSeed(model.seedId);
  };
  
  window.searchKnowledge=function(value) {
    try {
      const title=KnowledgeUtils.titleFromInput(value);
      const model=window.snapshotModel,n=model.find(title);
      if(!n) throw Error('No exact match in the supplied 10,000-article dataset. Choose an available article from the suggestions.');
      model.setSeed(n.article_id);
    } catch(e) {setStatus(e.message,true);}
  };
  
  $('seed-form').addEventListener('submit',e=>{e.preventDefault();window.searchKnowledge($('seed-search').value);});
  
  $('seed-search').addEventListener('input',()=>{
    const title=$('seed-search').value;if(/^https?:/i.test(title))return;
    $('article-suggestions').replaceChildren(...window.snapshotModel.suggestions(title).map(n=>{const o=document.createElement('option');o.value=n.title;return o;}));
  });
  
  $('reset-seed').onclick=()=>window.searchKnowledge('Artificial intelligence');
  try { const model=await window.knowledgeReady; window.attachKnowledgeModel(model); }
  catch(e){setStatus('Could not load data. Serve this folder over HTTP (see README), then refresh.',true);console.error(e);}
})();
