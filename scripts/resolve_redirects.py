from pathlib import Path
import duckdb


PROCESSED = Path("data/processed")
TEMP = Path("data/duckdb_tmp")
DB_PATH = Path("data/redirect_resolution.duckdb")

TEMP.mkdir(parents=True, exist_ok=True)

ARTICLE_INDEX = PROCESSED / "article_index.parquet"
REDIRECT_MAP = PROCESSED / "redirect_map.parquet"

LINKTARGET = PROCESSED / "linktarget_main.parquet"
PAGELINKS = PROCESSED / "pagelinks_main.parquet"

DIRECT_EDGES = PROCESSED / "edges_direct.parquet"

RESOLVED_REDIRECTS = (
    PROCESSED / "resolved_redirects.parquet"
)

REDIRECT_TARGET_MAP = (
    PROCESSED / "redirect_target_map.parquet"
)

REDIRECT_EDGES = (
    PROCESSED / "edges_redirect.parquet"
)

FINAL_EDGES = (
    PROCESSED / "edges_final.parquet"
)

MAX_DEPTH = 15


def count(con, table):
    return con.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]


def main():

    con = duckdb.connect(str(DB_PATH))

    con.execute("SET memory_limit='2GB'")
    con.execute("SET threads=4")
    con.execute(
        f"SET temp_directory='{TEMP}'"
    )
    con.execute(
        "SET preserve_insertion_order=false"
    )

    # -----------------------------------------------------
    # Views over existing Parquet files
    # -----------------------------------------------------

    con.execute(f"""
        CREATE OR REPLACE VIEW articles AS
        SELECT *
        FROM read_parquet('{ARTICLE_INDEX}')
    """)

    con.execute(f"""
        CREATE OR REPLACE VIEW redirects AS
        SELECT *
        FROM read_parquet('{REDIRECT_MAP}')
    """)

    # -----------------------------------------------------
    # Starting frontier
    #
    # redirect_title -> current target title
    # -----------------------------------------------------

    print()
    print("=== RESOLVING REDIRECT CHAINS ===")

    con.execute("""
        CREATE OR REPLACE TABLE frontier AS

        SELECT
            redirect_title,
            target_title AS current_title,
            1 AS depth

        FROM redirects
    """)

    con.execute("""
        DROP TABLE IF EXISTS resolved
    """)

    con.execute("""
        CREATE TABLE resolved (
            redirect_title VARCHAR,
            target_id BIGINT,
            depth INTEGER
        )
    """)

    starting = count(con, "frontier")

    print(
        f"Starting redirects: {starting:,}"
    )

    total_resolved = 0
    total_dead = 0

    # -----------------------------------------------------
    # Resolve chains iteratively
    # -----------------------------------------------------

    for depth in range(1, MAX_DEPTH + 1):

        frontier_count = count(
            con,
            "frontier"
        )

        if frontier_count == 0:
            print()
            print(
                "No redirects remain unresolved."
            )
            break

        print()
        print(
            f"Depth {depth}: "
            f"{frontier_count:,} redirects to examine"
        )

        # ---------------------------------------------
        # Which current targets are real articles?
        # ---------------------------------------------

        con.execute("""
            CREATE OR REPLACE TABLE newly_resolved AS

            SELECT
                f.redirect_title,
                a.article_id AS target_id,
                f.depth

            FROM frontier f

            INNER JOIN articles a
                ON f.current_title = a.title
        """)

        newly_count = count(
            con,
            "newly_resolved"
        )

        con.execute("""
            INSERT INTO resolved
            SELECT *
            FROM newly_resolved
        """)

        total_resolved += newly_count

        # ---------------------------------------------
        # For unresolved targets:
        #
        # Is the current destination itself another
        # redirect?
        # ---------------------------------------------

        con.execute("""
            CREATE OR REPLACE TABLE next_frontier AS

            SELECT
                f.redirect_title,
                r.target_title AS current_title,
                f.depth + 1 AS depth

            FROM frontier f

            LEFT JOIN articles a
                ON f.current_title = a.title

            INNER JOIN redirects r
                ON f.current_title =
                   r.redirect_title

            WHERE a.article_id IS NULL
        """)

        next_count = count(
            con,
            "next_frontier"
        )

        dead_count = (
            frontier_count
            - newly_count
            - next_count
        )

        total_dead += dead_count

        print(
            f"  resolved here: {newly_count:,}"
        )

        print(
            f"  continue chain: {next_count:,}"
        )

        print(
            f"  dead/unmatched: {dead_count:,}"
        )

        con.execute("""
            CREATE OR REPLACE TABLE frontier AS
            SELECT *
            FROM next_frontier
        """)

    # -----------------------------------------------------
    # Remaining rows after MAX_DEPTH are likely loops or
    # unusually long chains.
    # -----------------------------------------------------

    remaining = count(
        con,
        "frontier"
    )

    resolved_count = count(
        con,
        "resolved"
    )

    print()
    print("=== REDIRECT SUMMARY ===")

    print(
        f"Resolved to articles: "
        f"{resolved_count:,}"
    )

    print(
        f"Dead/unmatched: "
        f"{total_dead:,}"
    )

    print(
        f"Still unresolved after "
        f"{MAX_DEPTH} hops: {remaining:,}"
    )

    # -----------------------------------------------------
    # Save resolved redirect-title -> article-ID mapping
    # -----------------------------------------------------

    if RESOLVED_REDIRECTS.exists():
        RESOLVED_REDIRECTS.unlink()

    con.execute(f"""
        COPY (
            SELECT
                redirect_title,
                target_id,
                depth

            FROM resolved
        )

        TO '{RESOLVED_REDIRECTS}'
        (
            FORMAT PARQUET,
            COMPRESSION ZSTD,
            ROW_GROUP_SIZE 250000
        )
    """)

    print()
    print(
        f"Saved: {RESOLVED_REDIRECTS}"
    )

    # -----------------------------------------------------
    # Convert Wikipedia linktarget IDs whose titles are
    # redirects into final article IDs.
    # -----------------------------------------------------

    print()
    print(
        "=== MATCHING LINKTARGET IDs TO REDIRECTS ==="
    )

    if REDIRECT_TARGET_MAP.exists():
        REDIRECT_TARGET_MAP.unlink()

    con.execute(f"""
        COPY (
            SELECT
                l.target_link_id,
                r.target_id

            FROM read_parquet(
                '{LINKTARGET}'
            ) l

            INNER JOIN read_parquet(
                '{RESOLVED_REDIRECTS}'
            ) r
                ON l.target_title =
                   r.redirect_title
        )

        TO '{REDIRECT_TARGET_MAP}'
        (
            FORMAT PARQUET,
            COMPRESSION ZSTD,
            ROW_GROUP_SIZE 250000
        )
    """)

    redirect_target_count = con.execute(f"""
        SELECT COUNT(*)
        FROM read_parquet(
            '{REDIRECT_TARGET_MAP}'
        )
    """).fetchone()[0]

    print(
        f"Redirect link targets resolved: "
        f"{redirect_target_count:,}"
    )

    # -----------------------------------------------------
    # Recover actual hyperlink edges that point through
    # redirects.
    # -----------------------------------------------------

    print()
    print(
        "=== RECOVERING REDIRECTED EDGES ==="
    )

    if REDIRECT_EDGES.exists():
        REDIRECT_EDGES.unlink()

    con.execute(f"""
        COPY (
            SELECT
                p.source_id,
                r.target_id

            FROM read_parquet(
                '{PAGELINKS}'
            ) p

            INNER JOIN read_parquet(
                '{REDIRECT_TARGET_MAP}'
            ) r
                ON p.target_link_id =
                   r.target_link_id

            INNER JOIN articles a
                ON p.source_id =
                   a.article_id
        )

        TO '{REDIRECT_EDGES}'
        (
            FORMAT PARQUET,
            COMPRESSION ZSTD,
            ROW_GROUP_SIZE 250000
        )
    """)

    redirect_edge_count = con.execute(f"""
        SELECT COUNT(*)
        FROM read_parquet(
            '{REDIRECT_EDGES}'
        )
    """).fetchone()[0]

    print(
        f"Recovered redirect edges: "
        f"{redirect_edge_count:,}"
    )

    # -----------------------------------------------------
    # Combine direct + redirect-resolved edges.
    #
    # DISTINCT is deliberate:
    #
    # An article can link both:
    #     [[United States]]
    # and
    #     [[USA]]
    #
    # Once USA resolves to United States those become the
    # same graph edge.
    # -----------------------------------------------------

    print()
    print(
        "=== BUILDING FINAL DEDUPLICATED GRAPH ==="
    )

    if FINAL_EDGES.exists():
        FINAL_EDGES.unlink()

    con.execute(f"""
        COPY (
            SELECT DISTINCT
                source_id,
                target_id

            FROM (
                SELECT
                    source_id,
                    target_id

                FROM read_parquet(
                    '{DIRECT_EDGES}'
                )

                UNION ALL

                SELECT
                    source_id,
                    target_id

                FROM read_parquet(
                    '{REDIRECT_EDGES}'
                )
            )
        )

        TO '{FINAL_EDGES}'
        (
            FORMAT PARQUET,
            COMPRESSION ZSTD,
            ROW_GROUP_SIZE 250000
        )
    """)

    final_count = con.execute(f"""
        SELECT COUNT(*)
        FROM read_parquet(
            '{FINAL_EDGES}'
        )
    """).fetchone()[0]

    direct_count = con.execute(f"""
        SELECT COUNT(*)
        FROM read_parquet(
            '{DIRECT_EDGES}'
        )
    """).fetchone()[0]

    print()
    print("=== FINAL RESULT ===")

    print(
        f"Direct edges: "
        f"{direct_count:,}"
    )

    print(
        f"Redirect edges recovered: "
        f"{redirect_edge_count:,}"
    )

    print(
        f"Final unique edges: "
        f"{final_count:,}"
    )

    print(
        f"Saved: {FINAL_EDGES}"
    )

    con.close()


if __name__ == "__main__":
    main()