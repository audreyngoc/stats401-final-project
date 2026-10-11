from pathlib import Path
import duckdb


PROCESSED = Path("data/processed")
TEMP = Path("data/duckdb_tmp")

EDGES = PROCESSED / "edges_final.parquet"
OUTPUT = PROCESSED / "global_indegree.parquet"

TEMP.mkdir(parents=True, exist_ok=True)

con = duckdb.connect()

con.execute("SET memory_limit='2GB'")
con.execute("SET threads=4")
con.execute(f"SET temp_directory='{TEMP}'")
con.execute("SET preserve_insertion_order=false")

print("Calculating global Wikipedia in-degree...")
print("This scans all edges once.")

if OUTPUT.exists():
    OUTPUT.unlink()

con.execute(f"""
COPY (
    SELECT
        target_id AS article_id,
        COUNT(*)::BIGINT AS global_indegree

    FROM read_parquet('{EDGES}')

    GROUP BY target_id
)
TO '{OUTPUT}'
(
    FORMAT PARQUET,
    COMPRESSION ZSTD,
    ROW_GROUP_SIZE 250000
)
""")

count = con.execute(f"""
    SELECT COUNT(*)
    FROM read_parquet('{OUTPUT}')
""").fetchone()[0]

print()
print(f"Articles with incoming links: {count:,}")
print(f"Saved: {OUTPUT}")

con.close()