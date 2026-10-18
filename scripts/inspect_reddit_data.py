
import csv
import json
import os
from collections import Counter
from datetime import datetime, timezone

FILES = [
    "data/reddit_sc/posts.csv",
    "data/reddit_sc/comments.csv",
    "data/reddit_sc/posts.jsonl",
    "data/reddit_sc/comments.jsonl",
]

DATE_HINTS = ("date", "time", "created", "timestamp", "utc")
SUBREDDIT_HINTS = ("subreddit", "community")
TEXT_HINTS = ("title", "body", "text", "content", "selftext", "comment")


def parse_date(value):
    if value is None or str(value).strip() == "":
        return None

    value = str(value).strip()

    # Unix timestamps, commonly used in Reddit datasets.
    try:
        number = float(value)
        if number > 1_000_000_000:
            return datetime.fromtimestamp(number, tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        pass

    # ISO dates and common timestamp formats.
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value[:10], fmt).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue

    return None


def inspect_csv(path):
    print(f"\n{'=' * 70}\nFILE: {path}")

    with open(path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        columns = reader.fieldnames or []

        print("Columns:", columns)

        if not columns:
            print("No header found.")
            return

        date_columns = [
            c for c in columns
            if any(h in c.lower() for h in DATE_HINTS)
        ]
        subreddit_columns = [
            c for c in columns
            if any(h in c.lower() for h in SUBREDDIT_HINTS)
        ]
        text_columns = [
            c for c in columns
            if any(h in c.lower() for h in TEXT_HINTS)
        ]

        print("Possible date columns:", date_columns)
        print("Possible subreddit columns:", subreddit_columns)
        print("Possible text columns:", text_columns)

        total = 0
        date_counts = Counter()
        subreddit_counts = Counter()
        valid_dates = []

        for row in reader:
            total += 1

            for col in date_columns:
                dt = parse_date(row.get(col))
                if dt:
                    valid_dates.append(dt)
                    date_counts[dt.strftime("%Y-%m")] += 1
                    break

            for col in subreddit_columns:
                value = (row.get(col) or "").strip()
                if value:
                    subreddit_counts[value] += 1
                    break

            # Show only the first two records, with long text shortened.
            if total <= 2:
                sample = {}
                for key, value in row.items():
                    value = value or ""
                    sample[key] = (
                        value[:180] + "..."
                        if len(value) > 180 else value
                    )
                print(f"Sample row {total}:")
                print(json.dumps(sample, indent=2, ensure_ascii=False))

    print("\nTotal records:", f"{total:,}")
    print("Records with recognized dates:", f"{len(valid_dates):,}")

    if valid_dates:
        print("Earliest date:", min(valid_dates).isoformat())
        print("Latest date:", max(valid_dates).isoformat())
        print("Monthly record counts:")
        for month, count in sorted(date_counts.items()):
            print(f"  {month}: {count:,}")

    if subreddit_counts:
        print("Most frequent subreddits:")
        for name, count in subreddit_counts.most_common(15):
            print(f"  r/{name}: {count:,}")


def inspect_jsonl(path):
    print(f"\n{'=' * 70}\nFILE: {path}")
    total = 0

    with open(path, "r", encoding="utf-8-sig") as file:
        for line in file:
            if not line.strip():
                continue
            total += 1
            if total <= 2:
                try:
                    obj = json.loads(line)
                    print(f"Sample row {total} keys:", list(obj.keys()))
                    sample = {
                        k: str(v)[:180]
                        for k, v in obj.items()
                    }
                    print(json.dumps(sample, indent=2, ensure_ascii=False))
                except json.JSONDecodeError:
                    print("Could not parse sample JSON line.")

    print("Total JSONL records:", f"{total:,}")


def main():
    for path in FILES:
        if not os.path.exists(path):
            print(f"\nMISSING FILE: {path}")
            continue

        if path.endswith(".csv"):
            inspect_csv(path)
        elif path.endswith(".jsonl"):
            inspect_jsonl(path)


if __name__ == "__main__":
    main()
