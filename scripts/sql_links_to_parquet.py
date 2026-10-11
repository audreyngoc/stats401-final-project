import argparse
import gzip
import re
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


SQL_DIR = Path("data/sql")
OUT_DIR = Path("data/processed")

LINKTARGET_INPUT = SQL_DIR / "enwiki-latest-linktarget.sql.gz"
PAGELINKS_INPUT = SQL_DIR / "enwiki-latest-pagelinks.sql.gz"

LINKTARGET_OUTPUT = OUT_DIR / "linktarget_main.parquet"
PAGELINKS_OUTPUT = OUT_DIR / "pagelinks_main.parquet"

BATCH_SIZE = 250_000


# Current schemas:
#
# linktarget:
#   (lt_id, lt_namespace, lt_title)
#
# pagelinks:
#   (pl_from, pl_target_id, pl_from_namespace)

LINKTARGET_PATTERN = re.compile(
    rb"\((\d+),(-?\d+),'((?:\\.|''|[^'\\])*)'\)"
)

PAGELINKS_PATTERN = re.compile(
    rb"\((\d+),(\d+),(-?\d+)\)"
)


def mysql_unescape(raw):
    """
    Decode MySQL dump escaping inside a quoted string.
    """

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

        if byte == 92 and i + 1 < len(raw):  # backslash
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


def iter_insert_blocks(path, table_name):
    """
    Stream only the data belonging to:

        INSERT INTO `table_name` VALUES

    Handles the Wikimedia format where VALUES may be followed
    by a newline before the tuples begin.
    """

    prefix = (
        f"INSERT INTO `{table_name}` VALUES"
    ).encode()

    inside_insert = False

    with gzip.open(path, "rb") as file:

        for raw_line in file:

            line = raw_line.rstrip(b"\r\n")

            if not inside_insert:

                if not line.startswith(prefix):
                    continue

                inside_insert = True

                # There may or may not be data after VALUES
                remainder = line[len(prefix):].lstrip()

                if remainder:
                    finished = remainder.rstrip().endswith(b";")

                    yield remainder, finished

                    if finished:
                        inside_insert = False

            else:

                finished = line.rstrip().endswith(b";")

                yield line, finished

                if finished:
                    inside_insert = False


def iter_regex_rows(path, table_name, pattern):
    """
    Stream tuples without holding an entire INSERT statement
    in memory.

    A small carry buffer handles the unlikely case that a tuple
    is split between physical lines.
    """

    carry = b""

    for chunk, finished in iter_insert_blocks(
        path,
        table_name
    ):

        carry += chunk

        last_end = 0
        found = False

        for match in pattern.finditer(carry):

            found = True
            last_end = match.end()

            yield match.groups()

        if found:
            carry = carry[last_end:]

        # Remove separators left between tuples
        carry = carry.lstrip(b", \t\r\n")

        if finished:

            leftover = carry.strip(
                b",; \t\r\n"
            )

            if leftover:
                raise RuntimeError(
                    "Could not parse part of an INSERT statement.\n"
                    f"Beginning of unparsed data:\n"
                    f"{leftover[:500]!r}"
                )

            carry = b""

        # A tuple is tiny. If carry becomes huge, something
        # unexpected has happened and we should stop rather
        # than consume lots of RAM.
        if len(carry) > 1_000_000:

            raise RuntimeError(
                "Parser carry buffer exceeded 1 MB. "
                "The dump format appears different than expected.\n"
                f"Beginning of buffer:\n{carry[:500]!r}"
            )


def convert_linktarget():

    print()
    print("=== LINKTARGET ===")
    print(f"Reading: {LINKTARGET_INPUT}")
    print()

    schema = pa.schema([
        ("target_link_id", pa.int64()),
        ("target_title", pa.string()),
    ])

    temp_output = OUT_DIR / "linktarget_main.tmp.parquet"

    if temp_output.exists():
        temp_output.unlink()

    writer = pq.ParquetWriter(
        temp_output,
        schema,
        compression="zstd"
    )

    target_ids = []
    target_titles = []

    total = 0
    kept = 0

    try:

        for raw_id, raw_namespace, raw_title in iter_regex_rows(
            LINKTARGET_INPUT,
            "linktarget",
            LINKTARGET_PATTERN
        ):

            total += 1

            namespace = int(raw_namespace)

            # Target must be a normal encyclopedia article.
            if namespace != 0:
                continue

            target_id = int(raw_id)

            title = mysql_unescape(
                raw_title
            )

            # Database titles use underscores.
            # articles.parquet uses spaces.
            title = title.replace("_", " ")

            target_ids.append(target_id)
            target_titles.append(title)

            kept += 1

            if len(target_ids) >= BATCH_SIZE:

                table = pa.Table.from_pydict(
                    {
                        "target_link_id": target_ids,
                        "target_title": target_titles,
                    },
                    schema=schema
                )

                writer.write_table(table)

                target_ids.clear()
                target_titles.clear()

            if total % 1_000_000 == 0:

                print(
                    f"Read {total:,} linktargets "
                    f"| kept {kept:,} main-namespace targets"
                )

        if target_ids:

            table = pa.Table.from_pydict(
                {
                    "target_link_id": target_ids,
                    "target_title": target_titles,
                },
                schema=schema
            )

            writer.write_table(table)

    finally:
        writer.close()

    temp_output.replace(
        LINKTARGET_OUTPUT
    )

    print()
    print("LINKTARGET FINISHED")
    print(f"Rows read: {total:,}")
    print(f"Rows kept: {kept:,}")
    print(f"Saved: {LINKTARGET_OUTPUT}")


def convert_pagelinks():

    print()
    print("=== PAGELINKS ===")
    print(f"Reading: {PAGELINKS_INPUT}")
    print()

    schema = pa.schema([
        ("source_id", pa.int64()),
        ("target_link_id", pa.int64()),
    ])

    temp_output = OUT_DIR / "pagelinks_main.tmp.parquet"

    if temp_output.exists():
        temp_output.unlink()

    writer = pq.ParquetWriter(
        temp_output,
        schema,
        compression="zstd"
    )

    source_ids = []
    target_ids = []

    total = 0
    kept = 0

    try:

        for (
            raw_source,
            raw_source_namespace,
            raw_target
        ) in iter_regex_rows(
            PAGELINKS_INPUT,
            "pagelinks",
            PAGELINKS_PATTERN
        ):

            total += 1

            source_namespace = int(
                raw_source_namespace
            )

            # Only links FROM normal encyclopedia articles.
            if source_namespace != 0:
                continue

            source_id = int(raw_source)
            target_id = int(raw_target)

            source_ids.append(source_id)
            target_ids.append(target_id)

            kept += 1

            if len(source_ids) >= BATCH_SIZE:

                table = pa.Table.from_pydict(
                    {
                        "source_id": source_ids,
                        "target_link_id": target_ids,
                    },
                    schema=schema
                )

                writer.write_table(table)

                source_ids.clear()
                target_ids.clear()

            if total % 5_000_000 == 0:

                print(
                    f"Read {total:,} pagelinks "
                    f"| kept {kept:,} main-article sources"
                )

        if source_ids:

            table = pa.Table.from_pydict(
                {
                    "source_id": source_ids,
                    "target_link_id": target_ids,
                },
                schema=schema
            )

            writer.write_table(table)

    finally:
        writer.close()

    temp_output.replace(
        PAGELINKS_OUTPUT
    )

    print()
    print("PAGELINKS FINISHED")
    print(f"Rows read: {total:,}")
    print(f"Rows kept: {kept:,}")
    print(f"Saved: {PAGELINKS_OUTPUT}")


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--only",
        choices=[
            "linktarget",
            "pagelinks",
            "both",
        ],
        default="both"
    )

    args = parser.parse_args()

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    if args.only in {
        "linktarget",
        "both",
    }:
        convert_linktarget()

    if args.only in {
        "pagelinks",
        "both",
    }:
        convert_pagelinks()


if __name__ == "__main__":
    main()