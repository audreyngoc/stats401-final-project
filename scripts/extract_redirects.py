import gzip
import re
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq


SQL_DIR = Path("data/sql")
OUT_DIR = Path("data/processed")
TEMP_DIR = Path("data/duckdb_tmp")

PAGE_INPUT = SQL_DIR / "enwiki-latest-page.sql.gz"
REDIRECT_INPUT = SQL_DIR / "enwiki-latest-redirect.sql.gz"

REDIRECT_SOURCES = OUT_DIR / "redirect_sources.parquet"
REDIRECT_TARGETS = OUT_DIR / "redirect_targets.parquet"
REDIRECT_MAP = OUT_DIR / "redirect_map.parquet"

BATCH_SIZE = 250_000


# page:
# page_id, page_namespace, page_title, page_is_redirect, ...
PAGE_PATTERN = re.compile(
    rb"\((\d+),(-?\d+),'((?:\\.|''|[^'\\])*)',([01]),"
)

# redirect:
# rd_from, rd_namespace, rd_title, rd_interwiki, ...
REDIRECT_PATTERN = re.compile(
    rb"\((\d+),(-?\d+),'((?:\\.|''|[^'\\])*)','((?:\\.|''|[^'\\])*)',"
)


def mysql_unescape(raw):
    raw = raw.replace(b"''", b"'")

    output = bytearray()

    escape_map = {
        ord("0"): 0,
        ord("b"): 8,
        ord("n"): 10,
        ord("r"): 13,
        ord("t"): 9,
        ord("Z"): 26,
        ord("\\"): 92,
        ord("'"): 39,
        ord('"'): 34,
    }

    i = 0

    while i < len(raw):
        byte = raw[i]

        if byte == 92 and i + 1 < len(raw):
            next_byte = raw[i + 1]
            output.append(
                escape_map.get(next_byte, next_byte)
            )
            i += 2
        else:
            output.append(byte)
            i += 1

    return bytes(output).decode(
        "utf-8",
        errors="replace"
    )


def normalize_title(raw):
    title = mysql_unescape(raw)
    return title.replace("_", " ")


def iter_insert_lines(path, table_name):
    """
    Yield physical lines belonging to INSERT statements for
    the requested table without loading the dump into memory.
    """

    prefix = (
        f"INSERT INTO `{table_name}` VALUES"
    ).encode()

    inside = False

    with gzip.open(path, "rb") as f:

        for raw_line in f:

            line = raw_line.rstrip(b"\r\n")

            if not inside:

                if not line.startswith(prefix):
                    continue

                inside = True

                remainder = line[len(prefix):].lstrip()

                if remainder:
                    yield remainder

                    if remainder.rstrip().endswith(b";"):
                        inside = False

            else:

                yield line

                if line.rstrip().endswith(b";"):
                    inside = False


def extract_redirect_sources():

    print()
    print("=== PAGE / REDIRECT SOURCES ===")
    print(f"Reading: {PAGE_INPUT}")
    print()

    schema = pa.schema([
        ("redirect_id", pa.int64()),
        ("redirect_title", pa.string()),
    ])

    temp = OUT_DIR / "redirect_sources.tmp.parquet"

    if temp.exists():
        temp.unlink()

    writer = pq.ParquetWriter(
        temp,
        schema,
        compression="zstd"
    )

    ids = []
    titles = []

    total = 0
    kept = 0

    try:

        for line in iter_insert_lines(
            PAGE_INPUT,
            "page"
        ):

            for match in PAGE_PATTERN.finditer(line):

                total += 1

                raw_id, raw_namespace, raw_title, raw_redirect = (
                    match.groups()
                )

                namespace = int(raw_namespace)
                is_redirect = int(raw_redirect)

                # Only main-namespace redirects
                if namespace != 0 or is_redirect != 1:
                    continue

                ids.append(int(raw_id))
                titles.append(
                    normalize_title(raw_title)
                )

                kept += 1

                if len(ids) >= BATCH_SIZE:

                    table = pa.Table.from_pydict(
                        {
                            "redirect_id": ids,
                            "redirect_title": titles,
                        },
                        schema=schema
                    )

                    writer.write_table(table)

                    ids.clear()
                    titles.clear()

                if kept % 1_000_000 == 0:
                    print(
                        f"Found {kept:,} "
                        f"main-namespace redirect pages"
                    )

        if ids:

            writer.write_table(
                pa.Table.from_pydict(
                    {
                        "redirect_id": ids,
                        "redirect_title": titles,
                    },
                    schema=schema
                )
            )

    finally:
        writer.close()

    temp.replace(REDIRECT_SOURCES)

    print()
    print("PAGE FINISHED")
    print(f"Page rows read: {total:,}")
    print(f"Redirect pages kept: {kept:,}")
    print(f"Saved: {REDIRECT_SOURCES}")


def extract_redirect_targets():

    print()
    print("=== REDIRECT TARGETS ===")
    print(f"Reading: {REDIRECT_INPUT}")
    print()

    schema = pa.schema([
        ("redirect_id", pa.int64()),
        ("target_title", pa.string()),
    ])

    temp = OUT_DIR / "redirect_targets.tmp.parquet"

    if temp.exists():
        temp.unlink()

    writer = pq.ParquetWriter(
        temp,
        schema,
        compression="zstd"
    )

    ids = []
    titles = []

    total = 0
    kept = 0

    try:

        for line in iter_insert_lines(
            REDIRECT_INPUT,
            "redirect"
        ):

            for match in REDIRECT_PATTERN.finditer(line):

                total += 1

                (
                    raw_id,
                    raw_namespace,
                    raw_title,
                    raw_interwiki
                ) = match.groups()

                namespace = int(raw_namespace)

                # We only want redirects whose target is in
                # Wikipedia's main article namespace.
                if namespace != 0:
                    continue

                interwiki = mysql_unescape(
                    raw_interwiki
                )

                # Exclude redirects to other Wikimedia projects/sites.
                if interwiki:
                    continue

                ids.append(int(raw_id))
                titles.append(
                    normalize_title(raw_title)
                )

                kept += 1

                if len(ids) >= BATCH_SIZE:

                    table = pa.Table.from_pydict(
                        {
                            "redirect_id": ids,
                            "target_title": titles,
                        },
                        schema=schema
                    )

                    writer.write_table(table)

                    ids.clear()
                    titles.clear()

                if kept % 1_000_000 == 0:
                    print(
                        f"Found {kept:,} "
                        f"main-namespace redirect targets"
                    )

        if ids:

            writer.write_table(
                pa.Table.from_pydict(
                    {
                        "redirect_id": ids,
                        "target_title": titles,
                    },
                    schema=schema
                )
            )

    finally:
        writer.close()

    temp.replace(REDIRECT_TARGETS)

    print()
    print("REDIRECT FINISHED")
    print(f"Redirect rows read: {total:,}")
    print(f"Redirect targets kept: {kept:,}")
    print(f"Saved: {REDIRECT_TARGETS}")


def build_redirect_map():

    print()
    print("=== BUILDING REDIRECT MAP ===")

    TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    con = duckdb.connect()

    con.execute("SET memory_limit='2GB'")
    con.execute("SET threads=4")
    con.execute(
        f"SET temp_directory='{TEMP_DIR}'"
    )
    con.execute(
        "SET preserve_insertion_order=false"
    )

    if REDIRECT_MAP.exists():
        REDIRECT_MAP.unlink()

    con.execute(f"""
        COPY (
            SELECT
                s.redirect_id,
                s.redirect_title,
                t.target_title
            FROM read_parquet(
                '{REDIRECT_SOURCES}'
            ) s
            INNER JOIN read_parquet(
                '{REDIRECT_TARGETS}'
            ) t
                USING (redirect_id)
        )
        TO '{REDIRECT_MAP}'
        (
            FORMAT PARQUET,
            COMPRESSION ZSTD,
            ROW_GROUP_SIZE 250000
        )
    """)

    count = con.execute(f"""
        SELECT COUNT(*)
        FROM read_parquet('{REDIRECT_MAP}')
    """).fetchone()[0]

    print(
        f"Redirect mappings: {count:,}"
    )
    print(
        f"Saved: {REDIRECT_MAP}"
    )

    con.close()


def main():

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    extract_redirect_sources()
    extract_redirect_targets()
    build_redirect_map()

    print()
    print("=== DONE ===")


if __name__ == "__main__":
    main()