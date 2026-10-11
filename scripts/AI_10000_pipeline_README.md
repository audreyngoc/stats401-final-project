# Wikipedia AI dataset: 10,000 articles and pageviews

These two scripts work together. **Run them from the root of the Wikipedia project** (the directory containing `data/processed/`). They use the Parquet files already created on my computer; those files are too large to include here.

## Install and run

```bash
python -m pip install duckdb scikit-learn requests
python create_ai_10000_csv.py
python collect_ai_visualization_data.py all
```

`create_ai_10000_csv.py` selects exactly 10,000 **distinct articles** and writes `data/visualization/ai/ai_articles_10000.csv`. It preserves the existing first-hop subtopics and top ten children per subtopic when their interim ranking CSVs are present. It computes new TF-IDF scores for the larger candidate pool, comparing each page's opening text with the parent it was reached from and with the AI seed. If the earlier ranking CSVs are absent, it also computes the first-hop ranking from text. It uses the same 75% parent similarity, 10% seed similarity, 15% global in-degree percentile weighting as the demo for candidate pages. The new CSV includes `relevance_parent_id`, `parent_similarity`, `seed_similarity`, and `relevance_score`, so you can inspect the selection. Inputs are `articles.parquet`, `article_index.parquet`, `edges_final.parquet`, and `global_indegree.parquet`.

The selector samples branch candidates before loading their text (`--count * 2`, with a 3,000-row minimum per branch), considering closer links and higher in-degree first if a branch exceeds that bound. On the usual smaller first-hop lists, every candidate is scored. It expands through the most relevant children only when the direct candidate pool cannot supply the requested number of distinct articles. The default DuckDB memory cap is 2 GB, and it scores one subtopic at a time; adjust `--memory`, `--threads`, or `--temp-dir` if needed.

`collect_ai_visualization_data.py all` makes sequential Wikimedia pageview requests for the selected articles, then exports the data files. **The default period is September 2025 through August 2026**, matching the interim demo. It asks for twelve monthly counts per article using `all-access/user`; it does not make twelve requests for each article. The first run may take a long time because it makes up to 10,000 requests. Each completed response is saved under `data/visualization/ai/pageview_cache/`, so rerunning `all` skips those articles and retries failures. You can stop it and resume later.

For a short trial that makes at most 20 new requests:

```bash
python collect_ai_visualization_data.py all --max-requests 20
```

Then rerun the command **without** `--max-requests` for the full collection. To rebuild the graph and JSON after updating the cache without making API requests, use:

```bash
python collect_ai_visualization_data.py build
```

Set `--articles`, `--edges`, `--output`, and `--expected-count` if your paths or sample size differ. Supply an identifying `--user-agent` if the original project's GitHub URL in the script is no longer appropriate.

## Outputs in `data/visualization/ai/`

| File | Use |
| --- | --- |
| `ai_articles_10000.csv` | Authoritative selection of 10,000 unique articles; created by the first script. |
| `ai_edges.csv` | Every directed hyperlink between articles in that exact selection. |
| `ai_nodes.csv` | Article attributes and PageRank within the selected directed network. |
| `ai_pageviews_monthly.csv` | Long table of observed article-month views for trend charts. |
| `ai_pageviews_summary.csv` | One row per selected article, including month coverage and twelve-month totals where complete. |
| `ai_nodes_with_pageviews.csv` | Network attributes joined to pageviews; read by the scatterplot and linked views. |
| `ai_subtopic_monthly.csv` | Monthly subtopic sums with `articles_reporting` and `articles_in_group` coverage columns. |
| `ai_tree.json`, `ai_neighbors.json` | Initial hierarchy and top sampled outgoing neighbors for article search. |
| `ai_groups.json`, `ai_group_*.json` | Ten-group overview and bounded per-group network details. |
| `ai_graph.json` | Full 10,000-node graph for analysis; the grouped website does not draw it all at once. |
| `ai_manifest.json`, `ai_pageviews_failures.csv` | Counts, definitions, coverage, and request errors. |

The final website from the earlier package reads the CSV and JSON files above from **its own `data/` folder**. Copy `ai_tree.json`, `ai_neighbors.json`, `ai_groups.json`, all `ai_group_*.json`, `ai_nodes_with_pageviews.csv`, and `ai_manifest.json` into that folder after the full run. Serve the site over localhost; opening its HTML with `file://` can block data loading.

## Interpretation

A missing or partial history is **not zero attention**. `total_views_12m` and `avg_daily_views` remain blank until all twelve months are returned. The scatterplot can therefore show fewer than 10,000 marks, and its status line reports how many qualified. The subtopic-month CSV includes article coverage so a low sum is not mistaken for low interest when data are missing. These are pageviews of each exact article title; views of redirect titles are not rolled into the target article.

The ten subtopics are an **assignment for exploration**, not discovered network communities. PageRank describes this selected subgraph, whereas `global_indegree` describes incoming links in the processed Wikipedia corpus. Their denominators differ. The dataset includes the Wikipedia side of the later time-series comparison; Reddit and occupation data require separate sources.
