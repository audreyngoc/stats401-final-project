from pathlib import Path
import duckdb

PROCESSED = Path("data/processed")
TEMP = Path("data/duckdb_tmp")

TEMP.mkdir(parents=True, exist_ok=True)

con = duckdb.connect()

# Keep this friendly to my MacBook Air. (Don't crash it like last time)
con.execute("SET memory_limit = '2GB'")
con.execute("SET threads = 4")
con.execute(f"SET temp_directory = '{TEMP}'")
con.execute("SET preserve_insertion_order = false")

articles = PROCESSED / "articles.parquet"
linktargets = PROCESSED / "linktarget_main.parquet"
pagelinks = PROCESSED / "pagelinks_main.parquet"

article_index = PROCESSED / "article_index.parquet"
target_map = PROCESSED / "target_map.parquet"
edges = PROCESSED / "edges_direct.parquet"


print("STEP 1: Creating compact article index...")

con.execute(f"""
COPY (
    SELECT
        article_id,
        title
    FROM read_parquet('{articles}')
)
TO '{article_index}'
(
    FORMAT PARQUET,
    COMPRESSION ZSTD,
    ROW_GROUP_SIZE 250000
)
""")

count = con.execute(
    f"SELECT COUNT(*) FROM read_parquet('{article_index}')"
).fetchone()[0]

print(f"Article index: {count:,} rows")


print()
print("STEP 2: Resolving link-target IDs to real article IDs...")

con.execute(f"""
COPY (
    SELECT
        l.target_link_id,
        a.article_id AS target_id
    FROM read_parquet('{linktargets}') AS l
    INNER JOIN read_parquet('{article_index}') AS a
        ON l.target_title = a.title
)
TO '{target_map}'
(
    FORMAT PARQUET,
    COMPRESSION ZSTD,
    ROW_GROUP_SIZE 250000
)
""")

count = con.execute(
    f"SELECT COUNT(*) FROM read_parquet('{target_map}')"
).fetchone()[0]

print(f"Resolved target IDs: {count:,}")


print()
print("STEP 3: Building article-to-article edge list...")

con.execute(f"""
COPY (
    SELECT
        p.source_id,
        t.target_id
    FROM read_parquet('{pagelinks}') AS p

    INNER JOIN read_parquet('{target_map}') AS t
        ON p.target_link_id = t.target_link_id

    INNER JOIN read_parquet('{article_index}') AS s
        ON p.source_id = s.article_id
)
TO '{edges}'
(
    FORMAT PARQUET,
    COMPRESSION ZSTD,
    ROW_GROUP_SIZE 250000
)
""")

count = con.execute(
    f"SELECT COUNT(*) FROM read_parquet('{edges}')"
).fetchone()[0]

print()
print(f"Finished!")
print(f"Direct article-to-article edges: {count:,}")
print(f"Saved to: {edges}")