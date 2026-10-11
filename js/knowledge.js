/* Shared article identity, directed adjacency, and coordinated selection. */
(function (global) {
  'use strict';
  const numeric = value => value === '' || value == null ? null : Number(value);
  const normalize = title => title.replace(/_/g, ' ').trim().toLocaleLowerCase('en');
  
  function titleFromInput(value) {
    const text = value.trim();
    if (/^https?:/i.test(text)) {
      const url = new URL(text);
      if (!['en.wikipedia.org', 'en.m.wikipedia.org'].includes(url.hostname)) throw Error('Use an English Wikipedia article URL.');
      const title = url.pathname.startsWith('/wiki/') ? decodeURIComponent(url.pathname.slice(6)) : url.searchParams.get('title');
      if (!title) throw Error('This URL does not identify an article.');
      return title.replace(/_/g, ' ');
    }
    if (!text) throw Error('Enter an article title or English Wikipedia URL.');
    return text.replace(/_/g, ' ');
  }
  
  function parseNode(r) {
    const n = {...r, article_id: Number(r.article_id)};
    ['depth','selection_depth','global_indegree','local_indegree','local_outdegree','pagerank','betweenness','community','group_id','months_returned','total_views_12m','avg_daily_views','observed_views'].forEach(k => n[k] = numeric(r[k]));
    n.is_seed = String(r.is_seed).toLowerCase() === 'true';
    return n;
  }
  
  class KnowledgeModel {
    constructor(nodes, adjacency, communities, manifest) {
      this.nodes = nodes; this.byId = new Map(nodes.map(n => [n.article_id, n]));
      this.byTitle = new Map(nodes.map(n => [normalize(n.title), n]));
      this.out = new Map(); this.in = new Map(nodes.map(n => [n.article_id, []]));
      nodes.forEach((n,i) => {
        const targets = adjacency[i].map(j => nodes[j].article_id);
        this.out.set(n.article_id, targets);
        targets.forEach(t => this.in.get(t).push(n.article_id));
      });
      this.communities = communities; this.manifest = manifest; this.seedId = nodes.find(n=>n.is_seed)?.article_id ?? nodes[0]?.article_id;
      this.selectedId = null; this.mode = 'snapshot'; this.listeners = new Map();
      this.setSeed(this.seedId);
    }
    on(event,fn) { if (!this.listeners.has(event)) this.listeners.set(event,[]); this.listeners.get(event).push(fn); }
    emit(event,value) { (this.listeners.get(event)||[]).forEach(fn => fn(value)); }
    get(id) { return this.byId.get(Number(id)); }
    find(title) { return this.byTitle.get(normalize(title)); }
    setSeed(id) {
      if (!this.get(id)) throw Error('Article is unavailable.');
      this.seedId=Number(id); this.distances=this.bfs(this.seedId); this.selectedId=null;
      this.emit('seed',this.get(id)); this.emit('select',null);
    }
    bfs(seed) {
      const depths = new Map([[seed,0]]), queue=[seed];
      for(let i=0;i<queue.length;i++) for(const t of this.out.get(queue[i])||[]) if(!depths.has(t)) {depths.set(t,depths.get(queue[i])+1);queue.push(t);}
      return depths;
    }
    select(id) { this.selectedId=id==null?null:Number(id); this.emit('select',this.get(id)||null); }
    neighbors(id, exclude=[], limit=10) {
      const banned=new Set(exclude);
      return (this.out.get(Number(id))||[]).map(t=>this.get(t)).filter(n=>n&&!banned.has(n.article_id)&&n.pageviews_status==='complete'&&n.total_views_12m!=null)
        .sort((a,b)=>b.total_views_12m-a.total_views_12m||a.title.localeCompare(b.title)).slice(0,limit);
    }
    edges(ids) {
      const set=new Set(ids), edges=[];
      for(const s of set) for(const t of this.out.get(s)||[]) if(set.has(t)) edges.push({source:s,target:t});
      return edges;
    }
    suggestions(text,limit=12) {
      const query=normalize(text); if(!query) return [];
      return this.nodes.filter(n=>normalize(n.title).includes(query)).sort((a,b)=>Number(normalize(b.title).startsWith(query))-Number(normalize(a.title).startsWith(query))||(b.total_views_12m||0)-(a.total_views_12m||0)).slice(0,limit);
    }
  }
  global.KnowledgeModel=KnowledgeModel; global.KnowledgeUtils={parseNode,titleFromInput,normalize};
})(typeof window !== 'undefined' ? window : globalThis);
