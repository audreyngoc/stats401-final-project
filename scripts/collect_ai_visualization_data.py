"""Complete the 10,000-article Wikipedia data for the first three views.

Run from the project root after create_ai_10000_csv.py:
    python collect_ai_visualization_data.py all

Other modes:
    python collect_ai_visualization_data.py collect  # resumable API requests only
    python collect_ai_visualization_data.py build    # rebuild graph/JSON from cached CSVs

Dependencies: duckdb and requests. No Parquet files are copied to the
website. Pageview API data are monthly; missing months are never imputed as 0.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import json
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import duckdb
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = ('https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/'
            'en.wikipedia.org/all-access/user/')
# The project URL came from the identifying User-Agent in the old demo script.
DEFAULT_AGENT = 'stats401-final-project/2.0 (https://github.com/audreyngoc/stats401-final-project)'


def arguments():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('stage', nargs='?', choices=('all', 'collect', 'build'), default='all')
    p.add_argument('--articles', type=Path, default=Path('data/visualization/ai/ai_articles_10000.csv'))
    p.add_argument('--edges', type=Path, default=Path('data/processed/edges_final.parquet'))
    p.add_argument('--output', type=Path, default=Path('data/visualization/ai'))
    p.add_argument('--start', default='20250901', help='first day of first month (YYYYMMDD)')
    p.add_argument('--end', default='20260831', help='last day of last month (YYYYMMDD)')
    p.add_argument('--expected-count', type=int, default=10000)
    p.add_argument('--delay', type=float, default=0.25, help='pause after each uncached request, in seconds')
    p.add_argument('--user-agent', default=DEFAULT_AGENT)
    p.add_argument('--max-requests', type=int, default=None, help='optional small trial; rerun without it')
    p.add_argument('--detail-size', type=int, default=120)
    p.add_argument('--temp-dir', type=Path, default=Path('data/duckdb_tmp'))
    return p.parse_args()


def months_in_range(start, end):
    first = datetime.strptime(start, '%Y%m%d').date()
    last = datetime.strptime(end, '%Y%m%d').date()
    if first.day != 1 or last.day != calendar.monthrange(last.year, last.month)[1]:
        raise ValueError('Use the first day of a start month and the last day of an end month.')
    result = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        result.append(f'{year:04d}{month:02d}')
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    if len(result) != 12:
        raise ValueError('This pipeline compares exactly twelve complete calendar months.')
    return result, (last - first).days + 1


def read_articles(path, expected):
    if not path.is_file():
        raise FileNotFoundError(f'Run create_ai_10000_csv.py first: {path}')
    with path.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    required = {'article_id', 'title', 'subtopic_id', 'subtopic_title',
                'depth_from_seed', 'global_indegree'}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f'{path} needs columns: {", ".join(sorted(required))}')
    if len(rows) != expected:
        raise ValueError(f'Expected {expected:,} article rows; found {len(rows):,} in {path}')
    articles = {}
    for row in rows:
        article_id = int(row['article_id'])
        if article_id in articles or not row['title']:
            raise ValueError(f'Duplicate article ID or empty title: {article_id}')
        row['article_id'] = article_id
        row['subtopic_id'] = int(row['subtopic_id']) if row['subtopic_id'] else None
        row['depth_from_seed'] = int(row['depth_from_seed'])
        row['global_indegree'] = int(row['global_indegree'])
        articles[article_id] = row
    if sum(r['depth_from_seed'] == 0 for r in rows) != 1:
        raise ValueError('The article CSV must contain one seed at depth 0.')
    if sum(r['depth_from_seed'] == 1 for r in rows) != 10:
        raise ValueError('The article CSV must contain ten subtopics at depth 1.')
    return articles


def cache_path(cache_dir, article, start, end):
    digest = hashlib.sha256(article['title'].encode('utf-8')).hexdigest()[:12]
    return cache_dir / f"{article['article_id']}_{digest}_{start}_{end}.json"


def load_cache(path, article, start, end, expected_months):
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    if (data.get('article_id') != article['article_id'] or
        data.get('title') != article['title'] or
        data.get('start') != start or data.get('end') != end):
        raise ValueError(f'Cache metadata differs from the article/period: {path}')
    values = data.get('monthly')
    if not isinstance(values, dict) or not set(values).issubset(expected_months):
        raise ValueError(f'Invalid month keys in cache: {path}')
    if any(not isinstance(v, int) or v < 0 for v in values.values()):
        raise ValueError(f'Invalid pageview values in cache: {path}')
    return values


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + '.partial')
    with partial.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    partial.replace(path)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + '.partial')
    with partial.open('w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    partial.replace(path)


def directed_pagerank(ids, adjacency, alpha=0.85, tolerance=1e-8, max_iterations=100):
    """Power iteration with standard redistribution of dangling-node mass."""
    n = len(ids)
    scores = {id_: 1.0 / n for id_ in ids}
    for _ in range(max_iterations):
        dangling = sum(scores[id_] for id_ in ids if not adjacency[id_])
        base = (1.0 - alpha + alpha * dangling) / n
        next_scores = dict.fromkeys(ids, base)
        for source, targets in adjacency.items():
            if targets:
                contribution = alpha * scores[source] / len(targets)
                for target in targets:
                    next_scores[target] += contribution
        change = sum(abs(next_scores[id_] - scores[id_]) for id_ in ids)
        scores = next_scores
        if change < tolerance:
            break
    return scores


def request_monthly(session, article, start, end, expected_months):
    encoded = quote(article['title'].replace(' ', '_'), safe='')
    url = f'{BASE_URL}{encoded}/monthly/{start}/{end}'
    response = session.get(url, timeout=40)
    if response.status_code == 429:
        raise RuntimeError('Wikimedia returned HTTP 429 after retries. Stop and resume later; cached successes remain saved.')
    response.raise_for_status()
    result = {}
    for item in response.json().get('items', []):
        month = str(item['timestamp'])[:6]
        if month in expected_months:
            if month in result:
                raise ValueError(f'Duplicate monthly record for {article["title"]}: {month}')
            result[month] = int(item['views'])
    return result


def export_pageviews(articles, args, expected_months, days):
    cache_dir = args.output / 'pageview_cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    monthly_rows, summaries, failures = [], [], []
    for article in articles.values():
        path = cache_path(cache_dir, article, args.start, args.end)
        try:
            monthly = load_cache(path, article, args.start, args.end, set(expected_months))
        except (ValueError, json.JSONDecodeError) as exc:
            monthly = None
            failures.append({'article_id': article['article_id'], 'title': article['title'],
                             'reason': f'Invalid cache: {exc}'})
        for month in expected_months:
            if monthly is not None and month in monthly:
                monthly_rows.append({'article_id': article['article_id'], 'title': article['title'],
                                     'month': month[:4] + '-' + month[4:], 'views': monthly[month]})
        count = len(monthly) if monthly is not None else 0
        complete = count == len(expected_months)
        summaries.append({'article_id': article['article_id'], 'title': article['title'],
                          'start': args.start, 'end': args.end, 'months_returned': count,
                          'pageviews_status': 'complete' if complete else 'partial' if count else 'missing',
                          'total_views_12m': sum(monthly.values()) if complete else '',
                          'avg_daily_views': round(sum(monthly.values()) / days, 2) if complete else ''})
    write_csv(args.output / 'ai_pageviews_monthly.csv',
              ('article_id', 'title', 'month', 'views'), monthly_rows)
    write_csv(args.output / 'ai_pageviews_summary.csv',
              ('article_id', 'title', 'start', 'end', 'months_returned', 'pageviews_status',
               'total_views_12m', 'avg_daily_views'), summaries)
    write_csv(args.output / 'ai_pageviews_failures.csv', ('article_id', 'title', 'reason'), failures)
    print(f"Pageviews: {sum(r['pageviews_status']=='complete' for r in summaries):,} complete, "
          f"{sum(r['pageviews_status']=='partial' for r in summaries):,} partial, "
          f"{sum(r['pageviews_status']=='missing' for r in summaries):,} missing.", flush=True)
    return {r['article_id']: r for r in summaries}, monthly_rows


def collect(articles, args, expected_months, days):
    if args.delay < 0:
        raise ValueError('--delay cannot be negative')
    cache_dir = args.output / 'pageview_cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({'User-Agent': args.user_agent, 'Accept': 'application/json'})
    retry = Retry(total=4, connect=4, read=2, backoff_factor=2,
                  status_forcelist=[429, 500, 502, 503, 504],
                  respect_retry_after_header=True, allowed_methods=['GET'])
    session.mount('https://', HTTPAdapter(max_retries=retry))
    attempted, failures = 0, []
    for i, article in enumerate(articles.values(), 1):
        path = cache_path(cache_dir, article, args.start, args.end)
        try:
            if load_cache(path, article, args.start, args.end, set(expected_months)) is not None:
                continue
        except (ValueError, json.JSONDecodeError):
            pass  # Replace invalid caches after a successful request.
        if args.max_requests is not None and attempted >= args.max_requests:
            print(f'Stopped after {attempted} uncached requests as requested.', flush=True)
            break
        attempted += 1
        try:
            monthly = request_monthly(session, article, args.start, args.end, set(expected_months))
            write_json(path, {'article_id': article['article_id'], 'title': article['title'],
                              'start': args.start, 'end': args.end, 'monthly': monthly})
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                raise RuntimeError('Rate limited after retries. Rerun later to resume from cache.') from exc
            failures.append({'article_id': article['article_id'], 'title': article['title'],
                             'reason': str(exc)})
        except requests.exceptions.RetryError as exc:
            if '429' in str(exc):
                raise RuntimeError('Rate limited after retries. Rerun later to resume from cache.') from exc
            failures.append({'article_id': article['article_id'], 'title': article['title'],
                             'reason': str(exc)})
        except (requests.RequestException, KeyError, ValueError) as exc:
            failures.append({'article_id': article['article_id'], 'title': article['title'],
                             'reason': str(exc)})
        if attempted % 100 == 0:
            print(f'{i:,}/{len(articles):,} articles visited; {attempted:,} new requests; '
                  f'{len(failures):,} current failures', flush=True)
        time.sleep(args.delay)
    summaries, monthly_rows = export_pageviews(articles, args, expected_months, days)
    # The failure list includes HTTP and network errors not represented in cache.
    write_csv(args.output / 'ai_pageviews_failures.csv',
              ('article_id', 'title', 'reason'), failures)
    return summaries, monthly_rows


def load_summary(articles, args, expected_months, days):
    summary_path = args.output / 'ai_pageviews_summary.csv'
    if not summary_path.exists():
        return export_pageviews(articles, args, expected_months, days)
    with summary_path.open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    if len(rows) != len(articles) or {int(r['article_id']) for r in rows} != set(articles):
        raise ValueError('Pageview summary does not match the article IDs. Run the collect stage again.')
    result = {}
    for row in rows:
        article = articles[int(row['article_id'])]
        if row['title'] != article['title'] or row['start'] != args.start or row['end'] != args.end:
            raise ValueError('Pageview summary uses a different article title or date period. Rerun collect.')
        result[article['article_id']] = row
    monthly_path = args.output / 'ai_pageviews_monthly.csv'
    if not monthly_path.exists():
        raise FileNotFoundError(f'{monthly_path}; run the collect stage again.')
    with monthly_path.open(newline='', encoding='utf-8') as f:
        monthly = list(csv.DictReader(f))
    return result, monthly


def build(articles, args, expected_months, days, summaries=None, monthly_rows=None):
    if not args.edges.is_file():
        raise FileNotFoundError(f'Missing resolved hyperlink Parquet: {args.edges}')
    if summaries is None or monthly_rows is None:
        summaries, monthly_rows = load_summary(articles, args, expected_months, days)
    args.temp_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET memory_limit='2GB'")
    con.execute('SET threads=4')
    con.execute(f"SET temp_directory='{str(args.temp_dir.resolve()).replace(chr(39), chr(39)*2)}'")
    con.execute('SET preserve_insertion_order=false')
    con.execute('CREATE TEMP TABLE selected_ids (article_id BIGINT)')
    con.executemany('INSERT INTO selected_ids VALUES (?)', [(id_,) for id_ in articles])
    cursor = con.execute('SELECT DISTINCT e.source_id,e.target_id FROM read_parquet(?) e '
                         'JOIN selected_ids s ON e.source_id=s.article_id '
                         'JOIN selected_ids t ON e.target_id=t.article_id '
                         'WHERE e.source_id!=e.target_id', [str(args.edges.resolve())])
    edge_rows = []
    while batch := cursor.fetchmany(100000):
        edge_rows.extend((int(s), int(t)) for s, t in batch)
    con.close()
    adjacency = {id_: set() for id_ in articles}
    indegree = Counter()
    for source, target in edge_rows:
        adjacency[source].add(target)
        indegree[target] += 1
    pagerank = directed_pagerank(articles, adjacency)
    seed = next(r for r in articles.values() if r['depth_from_seed'] == 0)
    groups = sorted((r for r in articles.values() if r['depth_from_seed'] == 1),
                    key=lambda r: list(articles).index(r['article_id']))
    group_ids = [g['article_id'] for g in groups]
    group_titles = {g['article_id']: g['title'] for g in groups}
    if any(r['subtopic_id'] not in (*group_ids, None) for r in articles.values()):
        raise ValueError('Every article must belong to one of the ten first-level subtopics.')
    group_ord = {id_: i for i, id_ in enumerate(group_ids)}
    view_by_id = {int(id_): r for id_, r in summaries.items()}
    nodes = []
    for article in articles.values():
        id_, group = article['article_id'], article['subtopic_id']
        views = view_by_id[id_]
        node = {'article_id': id_, 'title': article['title'],
                'depth': article['depth_from_seed'], 'group_id': group or '',
                'subtopic_title': article['subtopic_title'],
                'global_indegree': article['global_indegree'],
                'local_indegree': indegree[id_], 'local_outdegree': len(adjacency[id_]),
                'pagerank': pagerank[id_], 'betweenness': '',
                'community': group_ord.get(group, -1), 'is_seed': id_ == seed['article_id'],
                'months_returned': int(views['months_returned']),
                'pageviews_status': views['pageviews_status'],
                'total_views_12m': views['total_views_12m'],
                'avg_daily_views': views['avg_daily_views']}
        nodes.append(node)
    base_cols = ('article_id', 'title', 'depth', 'group_id', 'subtopic_title',
                 'global_indegree', 'local_indegree', 'local_outdegree',
                 'pagerank', 'betweenness', 'community', 'is_seed')
    write_csv(args.output / 'ai_nodes.csv', base_cols, nodes)
    write_csv(args.output / 'ai_nodes_with_pageviews.csv',
              (*base_cols, 'months_returned', 'pageviews_status', 'total_views_12m',
               'avg_daily_views'), nodes)
    write_csv(args.output / 'ai_edges.csv', ('source_id', 'target_id'),
              ({'source_id': s, 'target_id': t} for s, t in edge_rows))
    node_map = {n['article_id']: n for n in nodes}
    def neighbor_key(target):
        v = view_by_id[target]
        measured = v['pageviews_status'] == 'complete'
        return (not measured, -int(v['total_views_12m']) if measured else 0,
                -articles[target]['global_indegree'], articles[target]['title'])
    neighbors = {str(source): sorted(adjacency[source], key=neighbor_key)[:10]
                 for source in articles}
    write_json(args.output / 'ai_neighbors.json', neighbors)
    tree_children = []
    for group in groups:
        parent = group['article_id']
        child_ids = [id_ for id_ in neighbors[str(parent)] if id_ != seed['article_id']]
        tree_children.append({'name': group['title'], 'article_id': parent,
                              'global_indegree': group['global_indegree'],
                              'children': [{'name': articles[id_]['title'], 'article_id': id_,
                                            'global_indegree': articles[id_]['global_indegree']}
                                           for id_ in child_ids[:10]]})
    write_json(args.output / 'ai_tree.json',
               {'name': seed['title'], 'article_id': seed['article_id'],
                'children': tree_children})
    weights = Counter()
    for source, target in edge_rows:
        left, right = articles[source]['subtopic_id'], articles[target]['subtopic_id']
        if left and right and left != right:
            weights[(left, right)] += 1
    group_records = []
    for group in groups:
        id_ = group['article_id']
        members = [n for n in nodes if n['group_id'] == id_]
        group_records.append({'article_id': id_, 'title': group['title'],
                              'count': len(members), 'pagerank': sum(n['pagerank'] for n in members),
                              'filename': f'ai_group_{id_}.json'})
        featured = sorted(members, key=lambda n:(n['pagerank'], n['local_indegree']),
                          reverse=True)[:max(1,args.detail_size)]
        featured_ids = {n['article_id'] for n in featured}
        if id_ not in featured_ids:
            featured = [node_map[id_], *featured[:-1]]
            featured_ids = {n['article_id'] for n in featured}
        write_json(args.output / f'ai_group_{id_}.json',
                   {'group_id': id_, 'total_count': len(members), 'nodes': featured,
                    'links': [{'source': s, 'target': t} for s,t in edge_rows
                              if s in featured_ids and t in featured_ids]})
    write_json(args.output / 'ai_groups.json',
               {'seed': {'article_id': seed['article_id'], 'title': seed['title']},
                'groups': group_records,
                'links': [{'source': s, 'target': t, 'weight': w}
                          for (s,t),w in sorted(weights.items())]})
    write_json(args.output / 'ai_graph.json',
               {'seed': {'article_id': seed['article_id'], 'title': seed['title']},
                'nodes': nodes, 'links': [{'source': s, 'target': t} for s,t in edge_rows]})
    subtopic_monthly = defaultdict(lambda: [0, set()])
    for r in monthly_rows:
        id_, month = int(r['article_id']), r['month']
        group = articles[id_]['subtopic_id']
        if group is not None:
            entry = subtopic_monthly[(group,month)]
            entry[0] += int(r['views'])
            entry[1].add(id_)
    group_count = {g['article_id']: sum(a['subtopic_id']==g['article_id'] for a in articles.values())
                   for g in groups}
    trend_rows = []
    for group in groups:
        for key in expected_months:
            month = key[:4] + '-' + key[4:]
            total, observed = subtopic_monthly[(group['article_id'], month)]
            trend_rows.append({'subtopic_id': group['article_id'], 'subtopic_title': group['title'],
                               'month': month, 'views': total if observed else '',
                               'articles_reporting': len(observed),
                               'articles_in_group': group_count[group['article_id']]})
    write_csv(args.output / 'ai_subtopic_monthly.csv',
              ('subtopic_id', 'subtopic_title', 'month', 'views',
               'articles_reporting', 'articles_in_group'), trend_rows)
    status_counts = Counter(n['pageviews_status'] for n in nodes)
    manifest = {'seed': seed['title'], 'article_count': len(nodes),
                'directed_link_count': len(edge_rows), 'group_count': len(groups),
                'pageview_start': args.start, 'pageview_end': args.end,
                'pageview_coverage': dict(status_counts),
                'pageview_metric': 'Monthly all-access user views for exact article title; redirects not rolled up',
                'tree_neighbors': 'Most 12-month views when complete, otherwise global in-degree',
                'network_metric': 'PageRank on the directed selected-article hyperlink graph',
                'source_article_csv': str(args.articles), 'source_edges_parquet': str(args.edges)}
    write_json(args.output / 'ai_manifest.json', manifest)
    print(f'Built {len(nodes):,} nodes, {len(edge_rows):,} directed links, ten groups and tree/network JSON.', flush=True)
    print(f'Complete 12-month pageviews for {status_counts["complete"]:,}/{len(nodes):,} articles.',flush=True)


def main():
    args = arguments()
    expected_months, days = months_in_range(args.start,args.end)
    articles = read_articles(args.articles,args.expected_count)
    args.output.mkdir(parents=True, exist_ok=True)
    summaries = monthly = None
    if args.stage in ('all','collect'):
        summaries, monthly = collect(articles,args,expected_months,days)
    if args.stage in ('all','build'):
        build(articles,args,expected_months,days,summaries,monthly)


if __name__ == '__main__':
    main()
