import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm


INPUT_DIR = Path("data/wikiextractor")
OUTPUT_PATH = Path("data/processed/articles.parquet")

BATCH_SIZE = 50_000


schema = pa.schema([
    ("article_id", pa.int64()),
    ("title", pa.string()),
    ("text", pa.large_string()),
])


def main():

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    files = sorted(
        path
        for path in INPUT_DIR.rglob("wiki_*")
        if path.is_file()
    )

    print(f"Found {len(files)} WikiExtractor files.")

    writer = pq.ParquetWriter(
        OUTPUT_PATH,
        schema,
        compression="zstd"
    )

    article_ids = []
    titles = []
    texts = []

    total_articles = 0

    for path in tqdm(files, desc="Converting to Parquet"):

        with path.open(
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                try:
                    article = json.loads(line)
                except json.JSONDecodeError:
                    continue

                article_ids.append(
                    int(article["id"])
                )

                titles.append(
                    article["title"]
                )

                texts.append(
                    article["text"]
                )

                total_articles += 1

                if len(article_ids) >= BATCH_SIZE:

                    table = pa.Table.from_pydict(
                        {
                            "article_id": article_ids,
                            "title": titles,
                            "text": texts,
                        },
                        schema=schema
                    )

                    writer.write_table(table)

                    article_ids.clear()
                    titles.clear()
                    texts.clear()

    # Final partial batch
    if article_ids:

        table = pa.Table.from_pydict(
            {
                "article_id": article_ids,
                "title": titles,
                "text": texts,
            },
            schema=schema
        )

        writer.write_table(table)

    writer.close()

    print()
    print(f"Finished: {total_articles:,} articles")
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()