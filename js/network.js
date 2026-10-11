(function () {
  'use strict';
  let model, simulation, mode='groups', group=null, treeIds=[], currentNodes=[], allLinks=[], nodeMarks, labels, linkLayer, zoom, selected=null;
  
  const width=1140,height=670,colors=d3.schemeTableau10;
  const color=c=>d3.interpolateRainbow((c*0.61803398875)%1);
  const $=id=>document.getElementById(id);
  const svg=d3.select('#network').append('svg').attr('viewBox',`0 0 ${width} ${height}`).attr('role','img').attr('aria-label','Interactive directed knowledge network. Drag articles; scroll to zoom.');
  svg.append('defs').append('marker').attr('id','link-arrow').attr('viewBox','0 -5 10 10').attr('refX',17).attr('refY',0).attr('markerWidth',5).attr('markerHeight',5).attr('orient','auto').append('path').attr('d','M0,-5L10,0L0,5').attr('fill','#718799');
  const layer=svg.append('g');
  
  zoom=d3.zoom().scaleExtent([.15,6]).on('zoom',e=>layer.attr('transform',e.transform));svg.call(zoom);
  svg.on('click',e=>{if(e.target===svg.node()&&model)model.select(null);});
  
  function scope() {
    const max=Number($('network-depth').value);
    return model.nodes.filter(n=>model.distances.has(n.article_id)&&(!max||model.distances.get(n.article_id)<=max));
  }
  
  function summarize(scoped) {
    const ids=new Set(scoped.map(n=>n.article_id)),by=new Map();
    scoped.forEach(n=>{const c=n.community??0;if(!by.has(c))by.set(c,{id:`c${c}`,community:c,count:0,pagerank:0,title:`C${c+1}`,kind:'group'});const g=by.get(c);g.count++;g.pagerank+=n.pagerank||0;});
    const weights=new Map();
    scoped.forEach(n=>{for(const t of model.out.get(n.article_id)||[])if(ids.has(t)){const target=model.get(t),a=n.community??0,b=target.community??0;if(a!==b){const key=`${a}/${b}`;weights.set(key,(weights.get(key)||0)+1);}}});
    for(const g of by.values()) {
      const info=model.communities.find(c=>c.id===g.community);g.title=`C${g.community+1}`;g.description=info?.label||'Connected concepts';
      g.internal=scoped.filter(n=>(n.community??0)===g.community).reduce((sum,n)=>sum+(model.out.get(n.article_id)||[]).filter(t=>ids.has(t)&&(model.get(t).community??0)===g.community).length,0);
    }
    return {nodes:[...by.values()],links:[...weights].map(([key,weight])=>{const [a,b]=key.split('/');return {source:`c${a}`,target:`c${b}`,weight};})};
  }
  
  function articleGraph(scoped) {
    const cap=Number($('node-limit').value);
    const pool=(group==null?scoped:scoped.filter(n=>n.community===group)).sort((a,b)=>(b.pagerank||0)-(a.pagerank||0));
    const chosen=new Map();
    
    function add(id){const n=pool.find(n=>n.article_id===id);if(n)chosen.set(id,n);}
    add(model.selectedId);if(group==null) {add(model.seedId);treeIds.forEach(add);}
    // Enforce the stated bound even when every tree branch is expanded.
    const preferred=[...chosen.values()].slice(0,cap);chosen.clear();preferred.forEach(n=>chosen.set(n.article_id,n));
    for(const n of pool)if(chosen.size<cap)chosen.set(n.article_id,n);
    const nodes=[...chosen.values()].map(n=>({...n,id:n.article_id,kind:'article',count:1}));
    return {nodes,links:model.edges(nodes.map(n=>n.id))};
  }
  
  function render(){
    if(!model)return;simulation?.stop();selected=model.selectedId;const scoped=scope();
    const graph=mode==='groups'?summarize(scoped):articleGraph(scoped);currentNodes=graph.nodes;allLinks=graph.links;
    layer.selectAll('*').remove();linkLayer=layer.append('g');
    const metric=$('size-metric').value;
    const size=mode==='groups'?d3.scaleSqrt().domain([0,d3.max(currentNodes,n=>n.count)||1]).range([0,58]):d3.scaleSqrt().domain([0,d3.max(currentNodes,n=>n[metric]||0)||1]).range([4,20]);
    currentNodes.forEach((n,i)=>{const angle=2*Math.PI*i/Math.max(1,currentNodes.length);n.x=width/2+Math.cos(angle)*(mode==='groups'?210:250);n.y=height/2+Math.sin(angle)*(mode==='groups'?185:225);n.radius=size(mode==='groups'?n.count:n[metric]||0);});
    nodeMarks=layer.append('g').selectAll('circle').data(currentNodes,n=>n.id).join('circle').attr('class','network-node').attr('r',n=>n.radius).attr('fill',n=>n.id===model.seedId?'#172939':color(n.community??0)).attr('tabindex',0).attr('role','button').attr('aria-label',n=>mode==='groups'?`${n.title}, ${n.count} articles; open community`:n.title)
      .on('click',(e,n)=>{e.stopPropagation();if(mode==='groups'){mode='articles';group=n.community;render();}else model.select(n.article_id);})
      .on('keydown',(e,n)=>{if(['Enter',' '].includes(e.key)){e.preventDefault();if(mode==='groups'){mode='articles';group=n.community;render();}else model.select(n.article_id);}})
      .call(d3.drag().on('start',(e,n)=>{if(!e.active)simulation.alphaTarget(.15).restart();n.fx=n.x;n.fy=n.y;}).on('drag',(e,n)=>{n.fx=e.x;n.fy=e.y;}).on('end',(e,n)=>{if(!e.active)simulation.alphaTarget(0);n.fx=null;n.fy=null;}));
    nodeMarks.append('title').text(n=>mode==='groups'?`${n.title}: ${n.description}\n${d3.format(',')(n.count)} articles; ${d3.format(',')(n.internal)} internal links\nClick to explore top-ranked articles`:`${n.title}\nPageRank: ${d3.format('.5f')(n.pagerank||0)}\nIncoming / outgoing: ${n.local_indegree} / ${n.local_outdegree}\nCommunity: C${(n.community??0)+1}`);
    labels=layer.append('g').selectAll('text').data(currentNodes).join('text').attr('class','network-label').text(n=>mode==='groups'?`${n.title} · ${d3.format(',')(n.count)}`:n.title.length>30?n.title.slice(0,27)+'…':n.title);
    const anchors=new Map();const communities=[...new Set(currentNodes.map(n=>n.community))];communities.forEach((c,i)=>anchors.set(c,{x:width/2+250*Math.cos(i*2*Math.PI/communities.length),y:height/2+180*Math.sin(i*2*Math.PI/communities.length)}));
    // Sparse force backbone, while all true visible links remain selectable.
    const backbone=mode==='groups'?allLinks:thinLinks(allLinks);
    simulation=d3.forceSimulation(currentNodes).randomSource(d3.randomLcg(.401)).force('links',d3.forceLink(backbone.map(l=>({...l}))).id(n=>n.id).distance(mode==='groups'?280:95).strength(mode==='groups'?.015:.05)).force('charge',d3.forceManyBody().strength(mode==='groups'?-700:-60)).force('collision',d3.forceCollide(n=>n.radius+(mode==='groups'?32:8))).force('x',d3.forceX(n=>mode==='groups'?width/2:(anchors.get(n.community)?.x??width/2)).strength(.07)).force('y',d3.forceY(n=>mode==='groups'?height/2:(anchors.get(n.community)?.y??height/2)).strength(.07)).on('tick',tick);
    $('network-back').hidden=mode==='groups';$('network-articles').hidden=mode==='articles';
    $('network-title').textContent=mode==='groups'?'Community overview':group==null?'Articles around the current seed':`Articles in C${group+1}`;
    $('network-summary').textContent=mode==='groups'?`${d3.format(',')(scoped.length)} reachable articles grouped into ${currentNodes.length} detected communities. Click a circle to inspect its articles. Link width shows directed cross-community hyperlink count.`:`${currentNodes.length} articles shown from ${group==null?scoped.length:scoped.filter(n=>n.community===group).length} in this scope · ${d3.format(',')(allLinks.length)} directed links among them. Metrics retain full-dataset scope.`;
    const entries=mode==='groups'?currentNodes:communities.map(c=>({community:c,title:`C${c+1}`,description:model.communities.find(g=>g.id===c)?.label||''}));
    const legend=d3.select('#community-legend').selectAll('button').data(entries).join('button').attr('class','community-legend-item').style('border-left',n=>`5px solid ${color(n.community)}`).text(n=>`${n.title}${n.description?' · '+n.description:''}`).on('click',(e,n)=>{mode='articles';group=n.community;render();});
    updateSelection();svg.call(zoom.transform,d3.zoomIdentity);
  }
  
  function thinLinks(links){const counts=new Map();return [...links].sort((a,b)=>(model.get(b.target)?.pagerank||0)-(model.get(a.target)?.pagerank||0)).filter(l=>{const c=counts.get(l.source)||0;if(c>=3)return false;counts.set(l.source,c+1);return true;});}
  
  function updateSelection(){
    if(!nodeMarks)return;selected=model.selectedId;const selectedNode=model.get(selected);
    let links=allLinks;
    if(mode==='articles') {
      const edgeMode=$('edge-mode').value;
      links=selected!=null?allLinks.filter(l=>l.source===selected||l.target===selected):edgeMode==='all'?allLinks:thinLinks(allLinks);
    }
    const max=d3.max(links,l=>l.weight)||1;
    linkLayer.selectAll('line').data(links,l=>`${l.source}/${l.target}`).join('line').attr('class','network-link').attr('stroke-width',l=>mode==='groups'?1+4*Math.sqrt((l.weight||1)/max):l.source===selected||l.target===selected?1.8:.7).attr('stroke',l=>l.source===selected?'#b54922':l.target===selected?'#18798a':'#9faeb9').attr('opacity',mode==='groups'?.2:selected!=null?.75:$('edge-mode').value==='all'?.09:.3).attr('marker-end',mode==='articles'&&selected!=null?'url(#link-arrow)':null).each(function(l){d3.select(this).selectAll('title').data([l]).join('title').text(mode==='groups'?`${l.weight} directed hyperlinks`: `${model.get(l.source)?.title} → ${model.get(l.target)?.title}`);});
    const connected=new Set([selected]);links.forEach(l=>{if(l.source===selected)connected.add(l.target);if(l.target===selected)connected.add(l.source);});
    nodeMarks.attr('opacity',n=>selected==null||mode==='groups'||connected.has(n.id)?1:.18).classed('is-selected',n=>mode==='groups'?selectedNode?.community===n.community:n.id===selected);
    labels.attr('display',n=>mode==='groups'||n.id===selected||($('show-labels').checked&&(n.id===model.seedId||currentNodes.indexOf(n)<12))?null:'none').attr('opacity',n=>selected==null||mode==='groups'||connected.has(n.id)?1:.3);
    $('links-summary').textContent=`${d3.format(',')(links.length)} / ${d3.format(',')(allLinks.length)} visible-scope links drawn${selected!=null&&mode==='articles'?' · arrows point toward the target; orange outgoing, teal incoming':''}.`;
    tick();
  }
  
  function tick(){
    const by=new Map(currentNodes.map(n=>[n.id,n]));
    linkLayer?.selectAll('line').attr('x1',l=>by.get(l.source)?.x).attr('y1',l=>by.get(l.source)?.y).attr('x2',l=>by.get(l.target)?.x).attr('y2',l=>by.get(l.target)?.y);
    nodeMarks?.attr('cx',n=>n.x).attr('cy',n=>n.y);labels?.attr('x',n=>n.x+n.radius+6).attr('y',n=>n.y+4);
  }
  
  window.addEventListener('knowledge:model',e=>{model=e.detail;mode='groups';group=null;treeIds=[];model.on('seed',()=>{mode='groups';group=null;render();});model.on('select',()=>{if(mode==='articles'&&model.selectedId!=null&&!currentNodes.some(n=>n.id===model.selectedId)){group=null;render();}else updateSelection();});model.on('tree',ids=>{treeIds=ids;if(mode==='articles'&&group==null)render();});render();});
  $('network-back').onclick=()=>{mode='groups';group=null;render();};$('network-articles').onclick=()=>{mode='articles';group=null;render();};
  ['network-depth','node-limit','size-metric'].forEach(id=>$(id).onchange=render);
  ['edge-mode','show-labels'].forEach(id=>$(id).onchange=updateSelection);
  
  $('clear-selection').onclick=()=>model?.select(null);
  
  $('network-fit').onclick=()=>{
    if(!currentNodes.length)return;const x0=d3.min(currentNodes,n=>n.x-n.radius-10),x1=d3.max(currentNodes,n=>n.x+n.radius+150),y0=d3.min(currentNodes,n=>n.y-n.radius-20),y1=d3.max(currentNodes,n=>n.y+n.radius+20);const k=Math.min(2,.9*Math.min(width/(x1-x0||1),height/(y1-y0||1)));svg.transition().duration(250).call(zoom.transform,d3.zoomIdentity.translate(width/2-k*(x0+x1)/2,height/2-k*(y0+y1)/2).scale(k));
  };
})();
