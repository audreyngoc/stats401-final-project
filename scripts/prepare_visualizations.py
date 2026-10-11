"""Enrich the supplied snapshot; no new or invented Wikipedia observations.
Usage: python scripts/prepare_visualizations.py /path/to/ai
Requires: networkx>=3.4, numpy, scipy. Run from the project root.
"""
import csv,json,collections,sys,time
from pathlib import Path
import networkx as nx

source=Path(sys.argv[1]); dest=Path('data'); dest.mkdir(exist_ok=True)
read=lambda name:list(csv.DictReader((source/name).open(encoding='utf-8')))
nodes=read('ai_nodes_with_pageviews.csv'); edges=read('ai_edges.csv')
G=nx.DiGraph(); G.add_nodes_from(int(n['article_id']) for n in nodes)
G.add_edges_from((int(e['source_id']),int(e['target_id'])) for e in edges)
assert len(G)==10000 and G.number_of_edges()==699092
print('Detecting communities...',flush=True)
U=G.to_undirected()
communities=nx.community.louvain_communities(U,seed=401)
communities.sort(key=lambda c:(-len(c),min(c)))
assignment={v:i for i,c in enumerate(communities) for v in c}
print('Estimating directed betweenness (32 sampled sources)...',flush=True)
between=nx.betweenness_centrality(G,k=32,normalized=True,seed=401)
depths=nx.single_source_shortest_path_length(G,1164)
monthly=read('ai_pageviews_monthly.csv'); totals=collections.Counter();counts=collections.Counter();pairs=set()
for r in monthly:
 key=(int(r['article_id']),r['month']);assert key not in pairs;pairs.add(key)
 totals[key[0]]+=int(r['views']);counts[key[0]]+=1
fields=list(nodes[0])+['observed_views']+['assigned_subtopic_index','selection_depth','betweenness_method','community_method']
for n in nodes:
 v=int(n['article_id']);n['observed_views']=totals[v] if counts[v] else '';n['assigned_subtopic_index']=n['community'];n['community']=assignment[v]
 n['selection_depth']=n['depth'];n['depth']=depths.get(v,'')
 n['betweenness']=between[v];n['betweenness_method']='directed approximation; k=32; seed=401'
 n['community_method']='Louvain; undirected projection; seed=401'
with (dest/'ai_nodes_enriched.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(nodes)
# Index-based adjacency reduces transfer size substantially; article order is fixed.
index={int(n['article_id']):i for i,n in enumerate(nodes)}
adj=[[] for _ in nodes]
for s,t in G.edges:adj[index[s]].append(index[t])
(dest/'ai_adjacency.json').write_text(json.dumps(adj,separators=(',',':')))
by={int(n['article_id']):n for n in nodes}
summary=[]
for i,c in enumerate(communities):
 ranked=sorted(c,key=lambda v:-float(by[v]['pagerank']))
 summary.append({'id':i,'count':len(c),'label':' / '.join(by[v]['title'] for v in ranked[:2]),'top_article_ids':ranked[:10]})
(dest/'ai_communities.json').write_text(json.dumps(summary,ensure_ascii=False,separators=(',',':')))
manifest=json.loads((source/'ai_manifest.json').read_text())
manifest.update({'enrichment':{'community_method':'Louvain on undirected projection; resolution=1; random seed=401','detected_community_count':len(communities),'betweenness_method':'Directed normalized approximation using 32 uniformly sampled sources; seed=401','metric_scope':'Full selected 10,000-article / 699,092-edge graph','depth_method':'Directed BFS from article 1164; empty depth means unreachable','unreachable_count':len(G)-len(depths),'source_depth_warning':'Original depth represents selection tiers, not shortest hyperlink distance','source_community_warning':'Original community is assigned TF-IDF subtopic, not detected graph community'}})
(dest/'ai_manifest.json').write_text(json.dumps(manifest,indent=2))
# Integrity, pageview coverage and totals.
assert all(counts[int(n['article_id'])]==int(n['months_returned']) for n in nodes)
assert all(totals[int(n['article_id'])]==int(n['total_views_12m']) for n in nodes if n['pageviews_status']=='complete')
stats={'nodes':len(G),'edges':G.number_of_edges(),'monthly_rows':len(monthly),'pageview_coverage':manifest['pageview_coverage'],'detected_communities':len(communities),'bfs_reachable':len(depths),'source_depth_mismatches':sum(str(depths.get(int(n['article_id']),''))!=n['selection_depth'] for n in nodes),'duplicate_node_ids':0,'duplicate_edges':len(edges)-G.number_of_edges(),'missing_edge_endpoints':0,'pageview_sum_mismatches':0,'month_count_mismatches':0,'directed_bfs_depth_distribution':dict(collections.Counter(depths.values()))}
(dest/'ai_validation.json').write_text(json.dumps(stats,indent=2))
print(json.dumps(stats,indent=2),flush=True)
