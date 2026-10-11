(function () {
  'use strict';
  let model, root, depth=2;
  const expanded=new Set();
  const svg=d3.select('#tree').append('svg').attr('role','img').attr('aria-label','Popular outgoing Wikipedia article links in a collapsible tree');
  const layer=svg.append('g');
  
  function dataForSeed() {
    const seed=model.get(model.seedId);
    return {node:seed,key:'root',ancestors:[seed.article_id],children:model.neighbors(seed.article_id).map(n=>({node:n,key:`root/${n.article_id}`,ancestors:[seed.article_id,n.article_id]}))};
  }
  
  function expand(d) {
    model.select(d.data.node.article_id);
    if(d.depth!==1||depth<2)return;
    const id=d.data.node.article_id;
    if(expanded.has(id)){expanded.delete(id);render();return;}
    expanded.add(id);render();
  }
  
  function render() {
    if(!model)return;
    root=dataForSeed();
    if(depth===2)root.children.forEach(b=>{if(expanded.has(b.node.article_id))b.children=model.neighbors(b.node.article_id,b.ancestors).map(n=>({node:n,key:`${b.key}/${n.article_id}`,ancestors:[...b.ancestors,n.article_id]}));});
    const hierarchy=d3.hierarchy(root);
    d3.tree().nodeSize([37,380])(hierarchy);
    const xs=hierarchy.descendants().map(d=>d.x),min=d3.min(xs),height=Math.max(420,d3.max(xs)-min+90);
    svg.attr('width',1320).attr('height',height).attr('viewBox',`0 0 1320 ${height}`);layer.attr('transform',`translate(70,${45-min})`);
    const color=d=>d.depth===0?'#172939':d3.schemeTableau10[(d.depth===1?root.children.findIndex(b=>b.node.article_id===d.data.node.article_id):root.children.findIndex(b=>b.node.article_id===d.parent.data.node.article_id))%10];
    layer.selectAll('path.tree-link').data(hierarchy.links(),d=>d.target.data.key).join('path').attr('class','tree-link').attr('d',d3.linkHorizontal().x(d=>d.y).y(d=>d.x)).attr('stroke',d=>color(d.target));
    const groups=layer.selectAll('g.tree-node').data(hierarchy.descendants(),d=>d.data.key).join(enter=>{const g=enter.append('g').attr('class','tree-node');g.append('circle');g.append('text').attr('class','tree-title');g.append('text').attr('class','tree-value');g.append('text').attr('class','tree-toggle');g.append('title');return g;});
    groups.attr('transform',d=>`translate(${d.y},${d.x})`).attr('tabindex',0).attr('role','button').attr('aria-label',d=>`${d.data.node.title}; ${d.depth===1?'select and expand or collapse branch':'select article'}`).on('click',(e,d)=>expand(d)).on('keydown',(e,d)=>{if(['Enter',' '].includes(e.key)){e.preventDefault();expand(d);}});
    groups.select('circle').attr('r',d=>d.depth===0?10:d.depth===1?8:5).attr('fill',color);
    groups.select('.tree-title').attr('x',18).attr('y',-5).text(d=>{const name=d.data.node.title;return name.length>44?name.slice(0,41)+'…':name;});
    groups.select('.tree-value').attr('x',18).attr('y',12).text(d=>`${d.data.node.total_views_12m==null?'Unavailable':d3.format(',')(d.data.node.total_views_12m)} views${d.depth===2&&model.distances.get(d.data.node.article_id)===1?' · also a direct seed link':''}`);
    groups.select('.tree-toggle').attr('x',-24).attr('y',4).text(d=>d.depth===1&&depth===2?(expanded.has(d.data.node.article_id)?'−':'+'):'');
    groups.select('title').text(d=>`${d.data.node.title}\n${d3.format(',')(d.data.node.total_views_12m)} pageviews, Sep 2025-Aug 2026\nShortest directed distance: ${model.distances.get(d.data.node.article_id)??'unavailable'}\nClick ${d.depth===1?'to select and toggle the branch':'to select'}`);
    document.getElementById('tree-summary').textContent=`${root.children.length} popular first-level links · ${hierarchy.descendants().length} article occurrences displayed. Only complete 12-month pageview records are ranked. Repeated articles mark reconnections; ancestors are excluded from their own branches.`;
    const legend=d3.select('#branch-legend').selectAll('span.branch-legend-item').data(root.children).join('span').attr('class','branch-legend-item');
    legend.text((d,i)=>`${i+1}. ${d.node.title}`).style('border-color',(d,i)=>d3.schemeTableau10[i%10]);
    selection();
    model.emit('tree',hierarchy.descendants().map(d=>d.data.node.article_id));
  }
  
  function selection(){layer.selectAll('.tree-node').classed('is-selected',d=>d.data.node.article_id===model.selectedId);}
  
  window.addEventListener('knowledge:model',e=>{
    model=e.detail;expanded.clear();model.on('seed',()=>{expanded.clear();render();});model.on('select',selection);render();
  });
  
  document.getElementById('tree-depth').onchange=e=>{depth=Number(e.target.value);render();};
  document.getElementById('tree-collapse').onclick=()=>{expanded.clear();render();};
  document.getElementById('tree-expand').onclick=()=>{if(!model)return;for(const b of dataForSeed().children)expanded.add(b.node.article_id);render();};
})();
