"""Export exactly 10,000 distinct AI-related Wikipedia articles to one CSV.

Run from the project root after build_graph.py, resolve_redirects.py, and
compute_global_indegree.py:
    python create_ai_10000_csv.py

Requires duckdb and scikit-learn. Existing relevance CSVs retain the interim
demo's first-level choices and its ten visible children per branch. All other
candidate articles are ranked with TF-IDF against the parent they were reached
from; global in-degree is a small tie-breaking signal, not the main selector
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import duckdb
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

MAX_TEXT_CHARS = 6000


def percentile(values):
    """Average percentile rank, matching pandas rank(method='average', pct=True)."""
    values = np.asarray(values, dtype=float)
    order = np.argsort(values, kind='stable')
    result = np.empty(len(values), dtype=float)
    pos = 0
    while pos < len(values):
        end = pos + 1
        while end < len(values) and values[order[end]] == values[order[pos]]:
            end += 1
        result[order[pos:end]] = (pos + 1 + end) / (2 * len(values))
        pos = end
    return result


def options():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--processed', type=Path, default=Path('data/processed'))
    p.add_argument('--first-ranking', type=Path,
                   default=Path('data/visualization/ai/ai_first_hop_relevance_ranked.csv'))
    p.add_argument('--second-ranking', type=Path,
                   default=Path('data/visualization/ai/ai_second_hop_relevance_ranked.csv'))
    p.add_argument('--output', type=Path, default=Path('data/visualization/ai/ai_articles_10000.csv'))
    p.add_argument('--seed', default='Artificial intelligence')
    p.add_argument('--count', type=int, default=10000)
    p.add_argument('--memory', default='2GB')
    p.add_argument('--threads', type=int, default=4)
    p.add_argument('--temp-dir', type=Path, default=Path('data/duckdb_tmp'))
    return p.parse_args()


def read_csv(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def main():
    a = options()
    if a.count < 11:
        raise ValueError('--count must be at least 11 (seed plus ten subtopics)')
    paths = {name: a.processed / name for name in (
        'article_index.parquet', 'articles.parquet', 'edges_final.parquet', 'global_indegree.parquet')}
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(f'Required processed Wikipedia file is missing: {path}')
    a.temp_dir.mkdir(parents=True, exist_ok=True)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    index, articles, edges, degrees = (str(paths[n].resolve()) for n in paths)
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{a.memory}'")
    con.execute(f'SET threads={a.threads}')
    con.execute(f"SET temp_directory='{str(a.temp_dir.resolve()).replace(chr(39), chr(39)*2)}'")
    con.execute('SET preserve_insertion_order=false')
    try:
        seed = con.execute('SELECT article_id,title FROM read_parquet(?) WHERE title=?',
                           [index, a.seed]).fetchone()
        if seed is None:
            raise ValueError(f'{a.seed!r} is not in article_index.parquet')
        seed_id, seed_title = int(seed[0]), seed[1]
        seed_degree = con.execute('SELECT coalesce(max(global_indegree),0) '
                                  'FROM read_parquet(?) WHERE article_id=?',
                                  [degrees,seed_id]).fetchone()[0]
        seed_text = con.execute('SELECT left(coalesce(text,\'\'), ?) '
                                'FROM read_parquet(?) WHERE article_id=?',
                                [MAX_TEXT_CHARS,articles,seed_id]).fetchone()
        seed_document = seed_title + '. ' + (seed_text[0] if seed_text else '')

        ranked_first = []
        if a.first_ranking.is_file():
            seen = set()
            for row in read_csv(a.first_ranking):
                try:
                    article_id = int(row['article_id'])
                except (KeyError, ValueError, TypeError):
                    continue
                if article_id not in seen and article_id != seed_id:
                    ranked_first.append(article_id)
                    seen.add(article_id)
                if len(ranked_first) == 10:
                    break
        first_info = {}
        if ranked_first:
            placeholders = ','.join('?' for _ in ranked_first)
            for id_, title, degree in con.execute(
                f'SELECT a.article_id,a.title,coalesce(d.global_indegree,0) '
                f'FROM read_parquet(?) a LEFT JOIN read_parquet(?) d USING(article_id) '
                f'WHERE a.article_id IN ({placeholders})',
                [index, degrees, *ranked_first]).fetchall():
                first_info[int(id_)] = (title, int(degree))
        first = [(id_, *first_info[id_]) for id_ in ranked_first if id_ in first_info]
        if len(first) < 10:
            fallback = con.execute(
                'SELECT DISTINCT e.target_id,a.title,coalesce(d.global_indegree,0) AS degree,'
                'left(coalesce(a.text,\'\'),?) AS body '
                'FROM read_parquet(?) e JOIN read_parquet(?) a ON e.target_id=a.article_id '
                'LEFT JOIN read_parquet(?) d ON e.target_id=d.article_id '
                'WHERE e.source_id=? AND e.target_id!=?',
                [MAX_TEXT_CHARS,edges,articles,degrees,seed_id,seed_id]).fetchall()
            documents = [seed_document] + [title + '. ' + (body or '')
                                           for _,title,_,body in fallback]
            try:
                matrix = TfidfVectorizer(stop_words='english',ngram_range=(1,2),
                                         min_df=2,max_df=0.95,max_features=60000,
                                         sublinear_tf=True).fit_transform(documents)
            except ValueError:
                matrix = TfidfVectorizer(stop_words='english',ngram_range=(1,2),
                                         min_df=1,max_df=1.0,max_features=60000,
                                         sublinear_tf=True).fit_transform(documents)
            sim = np.asarray(matrix[1:].multiply(matrix[0]).sum(axis=1)).ravel()
            score = (.85*percentile(sim) + .15*percentile(
                np.log1p([int(r[2]) for r in fallback])))
            fallback = [fallback[i] for i in sorted(range(len(fallback)),
                        key=lambda i:(-score[i],-sim[i],int(fallback[i][0])))]
            seen = {id_ for id_,_,_ in first}
            for id_,title,degree,_ in fallback:
                if int(id_) not in seen:
                    first.append((int(id_),title,int(degree)))
                    seen.add(int(id_))
                if len(first) == 10:
                    break
        if len(first) != 10:
            raise ValueError('The seed has fewer than ten linked, indexed subtopics.')
        first_ids = [row[0] for row in first]
        first_titles = {id_: title for id_,title,_ in first}
        print('First-level subtopics:', ', '.join(first_titles.values()), flush=True)
        print('First-level method:', 'existing relevance CSV' if len(first_info)==10
              else 'TF-IDF seed relevance (plus available interim ranking)', flush=True)
        con.execute('CREATE TEMP TABLE first_ids (group_id BIGINT)')
        con.executemany('INSERT INTO first_ids VALUES (?)', [(x,) for x in first_ids])
        con.execute('CREATE TEMP TABLE direct AS '
                    'SELECT DISTINCT g.group_id,e.target_id AS article_id '
                    'FROM read_parquet(?) e JOIN first_ids g ON e.source_id=g.group_id '
                    'WHERE e.target_id!=?', [edges,seed_id])
        print('Direct linked candidates:', con.execute('SELECT count(DISTINCT article_id) FROM direct').fetchone()[0], flush=True)

        # Preserve the ten visible children of each branch from the interim.
        # The remaining articles are independently scored below with TF-IDF.
        second_ranked = defaultdict(list)
        if a.second_ranking.is_file():
            for row in read_csv(a.second_ranking):
                try:
                    group, child = int(row['parent_id']), int(row['child_id'])
                    rank = int(row['child_rank'])
                except (KeyError, ValueError, TypeError):
                    continue
                if group in first_titles and child not in second_ranked[group]:
                    second_ranked[group].append((rank,child))
            for group in first_ids:
                second_ranked[group].sort()
                second_ranked[group] = [child for _,child in second_ranked[group]]
        pinned = {group: list(dict.fromkeys(second_ranked[group][:10])) for group in first_ids}

        def candidate_rows(parent_limit, center_order):
            con.execute('CREATE OR REPLACE TEMP TABLE candidate AS '
                        'SELECT group_id,article_id,2 AS depth,group_id AS parent_id,'
                        '0 AS parent_priority FROM direct')
            if parent_limit:
                parent_records = []
                for group in first_ids:
                    centers = list(dict.fromkeys(second_ranked[group][:10] +
                                                  center_order.get(group, [])))[:parent_limit]
                    parent_records.extend((group,child,rank) for rank,child in enumerate(centers))
                con.execute('CREATE OR REPLACE TEMP TABLE centers '
                            '(group_id BIGINT,parent_id BIGINT,parent_priority INTEGER)')
                if parent_records:
                    con.executemany('INSERT INTO centers VALUES (?,?,?)',parent_records)
                    con.execute('INSERT INTO candidate '
                                'SELECT p.group_id,e.target_id,3,p.parent_id,p.parent_priority '
                                'FROM read_parquet(?) e '
                                'JOIN centers p ON e.source_id=p.parent_id WHERE e.target_id!=?',
                                [edges,seed_id])
            # Choose the closest available parent for duplicate candidate links.
            # Bound each branch before retrieving text into Python.
            limit = max(3000,a.count * 2)
            con.execute(
                'CREATE OR REPLACE TEMP TABLE scoped AS '
                'SELECT group_id,article_id,title,depth,parent_id,global_indegree FROM ('
                'SELECT c.group_id,c.article_id,a.title,c.depth,c.parent_id,c.parent_priority,'
                'coalesce(d.global_indegree,0) AS global_indegree '
                'FROM candidate c JOIN read_parquet(?) a ON c.article_id=a.article_id '
                'LEFT JOIN read_parquet(?) d ON c.article_id=d.article_id '
                'WHERE c.article_id!=? AND c.article_id NOT IN (SELECT group_id FROM first_ids) '
                'QUALIFY row_number() OVER (PARTITION BY c.group_id,c.article_id '
                'ORDER BY c.depth,c.parent_priority,c.parent_id)=1) q '
                'QUALIFY row_number() OVER (PARTITION BY group_id '
                'ORDER BY depth,global_indegree DESC,article_id) <= ?',
                [index,degrees,seed_id,limit])

            by_group = defaultdict(list)
            for group in first_ids:
                # A separate branch keeps the dense TF-IDF matrix out of memory;
                # sparse vectors and the 6k-character article openings are bounded.
                result = con.execute(
                    'SELECT s.article_id,s.title,s.depth,s.global_indegree,s.parent_id,'
                    'left(coalesce(a.text,\'\'),?) FROM scoped s '
                    'JOIN read_parquet(?) a USING(article_id) WHERE s.group_id=?',
                    [MAX_TEXT_CHARS,articles,group]).fetchall()
                if not result:
                    continue
                parent_ids = sorted({int(r[4]) for r in result})
                con.execute('CREATE OR REPLACE TEMP TABLE parent_ids (article_id BIGINT)')
                con.executemany('INSERT INTO parent_ids VALUES (?)',[(x,) for x in parent_ids])
                parent_docs = {int(id_): title + '. ' + (body or '') for id_,title,body in con.execute(
                    'SELECT a.article_id,a.title,left(coalesce(a.text,\'\'),?) '
                    'FROM read_parquet(?) a JOIN parent_ids p USING(article_id)',
                    [MAX_TEXT_CHARS,articles]).fetchall()}
                if len(parent_docs) != len(parent_ids):
                    missing = set(parent_ids) - parent_docs.keys()
                    raise RuntimeError(f'Missing parent article text for {len(missing)} pages')
                documents = [seed_document] + [parent_docs[x] for x in parent_ids] + [
                    title + '. ' + (body or '') for _,title,_,_,_,body in result]
                try:
                    matrix = TfidfVectorizer(stop_words='english', ngram_range=(1,2),
                                             min_df=2, max_df=0.95, max_features=40000,
                                             sublinear_tf=True).fit_transform(documents)
                except ValueError:  # tiny or unusually sparse branches
                    matrix = TfidfVectorizer(stop_words='english', ngram_range=(1,2),
                                             min_df=1, max_df=1.0, max_features=40000,
                                             sublinear_tf=True).fit_transform(documents)
                offset = 1 + len(parent_ids)
                parents = {id_: i+1 for i,id_ in enumerate(parent_ids)}
                parent_sim = np.asarray(matrix[offset:].multiply(
                    matrix[[parents[int(r[4])] for r in result]]).sum(axis=1)).ravel()
                seed_sim = np.asarray(matrix[offset:].multiply(matrix[0]).sum(axis=1)).ravel()
                structural = percentile(np.log1p([int(r[3]) for r in result]))
                scores = (.75 * percentile(parent_sim) + .10 * percentile(seed_sim)
                          + .15 * structural)
                for i,(id_,title,depth,degree,parent_id,_) in enumerate(result):
                    by_group[group].append((int(id_),title,int(depth),int(degree),
                                            int(parent_id),float(parent_sim[i]),float(seed_sim[i]),
                                            float(scores[i])))
                by_group[group].sort(key=lambda r:(-r[7],r[2],-r[3],r[0]))
                print(f'  {first_titles[group]}: TF-IDF ranked {len(result):,} candidates',flush=True)
            return by_group

        def choose(by_group):
            selected = {seed_id: {'article_id':seed_id,'title':seed_title,'subtopic_id':'',
                                  'subtopic_title':'','depth_from_seed':0,'global_indegree':int(seed_degree),
                                  'selection_method':'seed'}}
            for group,title,degree in first:
                selected[group] = {'article_id':group,'title':title,'subtopic_id':group,
                                   'subtopic_title':title,'depth_from_seed':1,
                                   'global_indegree':degree,'selection_method':'first-level subtopic'}
            # Pin ranked second-level articles before round-robin expansion.
            row_maps = {group:{r[0]:r for r in by_group[group]} for group in first_ids}
            for slot in range(10):
                for group in first_ids:
                    if slot >= len(pinned[group]):
                        continue
                    row = row_maps[group].get(pinned[group][slot])
                    if row and row[0] not in selected and len(selected)<a.count:
                        id_,title,depth,degree,parent_id,parent_sim,seed_sim,score=row
                        selected[id_] = {'article_id':id_,'title':title,'subtopic_id':group,
                                         'subtopic_title':first_titles[group], 'depth_from_seed':depth,
                                         'global_indegree':degree,'relevance_parent_id':parent_id,
                                         'parent_similarity':parent_sim,'seed_similarity':seed_sim,
                                         'relevance_score':score,'selection_method':'ranked branch child'}
            cursors = {group:0 for group in first_ids}
            while len(selected) < a.count:
                advanced = False
                for group in first_ids:
                    rows = by_group[group]
                    while cursors[group] < len(rows):
                        id_,title,depth,degree,parent_id,parent_sim,seed_sim,score = rows[cursors[group]]
                        cursors[group] += 1
                        if id_ not in selected:
                            selected[id_] = {'article_id':id_,'title':title,'subtopic_id':group,
                                             'subtopic_title':first_titles[group], 'depth_from_seed':depth,
                                             'global_indegree':degree,'relevance_parent_id':parent_id,
                                             'parent_similarity':parent_sim,'seed_similarity':seed_sim,
                                             'relevance_score':score,
                                             'selection_method':'TF-IDF parent relevance'}
                            advanced = True
                            break
                    if len(selected) == a.count:
                        break
                if not advanced:
                    break
            return selected

        selected = {}
        center_order = {}
        for parent_limit in (0,50,200):
            print(f'Selecting with {parent_limit} second-level expansion centers per branch...',flush=True)
            rows = candidate_rows(parent_limit,center_order)
            selected = choose(rows)
            print(f'  unique selected articles: {len(selected):,}',flush=True)
            if len(selected) == a.count:
                break
            center_order = {group:[r[0] for r in rows[group] if r[2]==2]
                            for group in first_ids}
        if len(selected) != a.count:
            raise RuntimeError(f'Could find only {len(selected):,} indexed articles within this scope; '
                               f'no partial CSV was written. Try a broader seed or expand parent limits.')

        con.execute('CREATE TEMP TABLE selected_ids (article_id BIGINT)')
        con.executemany('INSERT INTO selected_ids VALUES (?)',[(id_,) for id_ in selected])
        local_in,local_out,cross_out = defaultdict(int),defaultdict(int),defaultdict(int)
        cursor = con.execute('SELECT DISTINCT e.source_id,e.target_id FROM read_parquet(?) e '
                             'JOIN selected_ids s ON e.source_id=s.article_id '
                             'JOIN selected_ids t ON e.target_id=t.article_id '
                             'WHERE e.source_id!=e.target_id',[edges])
        edge_count=0
        while batch := cursor.fetchmany(100000):
            for source,target in batch:
                source,target=int(source),int(target)
                local_out[source]+=1
                local_in[target]+=1
                if selected[source]['subtopic_id'] != selected[target]['subtopic_id']:
                    cross_out[source]+=1
                edge_count+=1
        fields = ('article_id','title','subtopic_id','subtopic_title','depth_from_seed',
                  'global_indegree','local_indegree','local_outdegree',
                  'cross_subtopic_outdegree','relevance_parent_id','parent_similarity',
                  'seed_similarity','relevance_score','selection_method')
        staging = a.output.with_name(a.output.name+'.partial')
        with staging.open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields)
            writer.writeheader()
            for row in selected.values():
                id_=row['article_id']
                writer.writerow({**row,'local_indegree':local_in[id_],
                                 'local_outdegree':local_out[id_],
                                 'cross_subtopic_outdegree':cross_out[id_]})
        staging.replace(a.output)
        print(f'Wrote exactly {len(selected):,} unique articles to {a.output}',flush=True)
        print(f'Internal directed hyperlinks counted: {edge_count:,}',flush=True)
        print('Pageviews are not included; fetch them separately before plotting attention.',flush=True)
    finally:
        con.close()


if __name__ == '__main__':
    main()
