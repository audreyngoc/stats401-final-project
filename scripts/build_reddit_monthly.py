
from pathlib import Path

import pandas as pd


# Paths
ROOT = Path(__file__).resolve().parents[1]
MATCHES_FILE = ROOT / "data" / "reddit_topic_matches.csv"
POSTS_FILE = ROOT / "data" / "reddit_sc" / "posts.csv"
OUTPUT_FILE = ROOT / "data" / "reddit_subtopic_monthly.csv"

# Study period: September 2025 through August 2026
MONTHS = pd.period_range(
    start="2025-09",
    end="2026-08",
    freq="M",
)

TOPICS = [
    "Artificial general intelligence",
    "Artificial intelligence in video games",
    "Cognition",
    "Decision-making",
    "Generative AI",
    "Knowledge representation and reasoning",
    "Machine learning",
    "Natural language processing",
    "Operations research",
    "Problem solving",
]


# Load the datasets
matches = pd.read_csv(MATCHES_FILE).fillna("")
posts = pd.read_csv(POSTS_FILE).fillna("")

if "created_at" not in matches.columns:
    raise ValueError("reddit_topic_matches.csv needs a created_at column.")

if "matched_topics" not in matches.columns:
    raise ValueError("reddit_topic_matches.csv needs a matched_topics column.")

if "id" not in matches.columns or "id" not in posts.columns:
    raise ValueError("Both datasets must contain an id column.")

# Use the original post timestamp if the match timestamp is missing.
if "created_at" not in posts.columns:
    raise ValueError("posts.csv needs a created_at column.")

matches["created_at"] = matches["created_at"].replace("", pd.NA)
matches = matches.merge(
    posts[["id", "created_at"]].rename(
        columns={"created_at": "original_created_at"}
    ),
    on="id",
    how="left",
    suffixes=("", "_post"),
)

matches["created_at"] = matches["created_at"].fillna(
    matches["original_created_at"]
)

# Parse timestamps, supporting ISO dates and Unix timestamps.
timestamps = matches["created_at"]

numeric_timestamps = pd.to_numeric(timestamps, errors="coerce")
is_numeric = numeric_timestamps.notna()

dates = pd.Series(
    pd.NaT,
    index=matches.index,
    dtype="datetime64[ns, UTC]",
)

if is_numeric.any():
    values = numeric_timestamps[is_numeric]
    unit = "ms" if values.abs().median() > 1e12 else "s"
    dates.loc[is_numeric] = pd.to_datetime(
        values,
        unit=unit,
        errors="coerce",
        utc=True,
    )

if (~is_numeric).any():
    dates.loc[~is_numeric] = pd.to_datetime(
        timestamps[~is_numeric],
        errors="coerce",
        utc=True,
    )

matches["month"] = dates.dt.strftime("%Y-%m")

if matches["month"].isna().any():
    print(
        "Warning:",
        int(matches["month"].isna().sum()),
        "posts have unparseable timestamps and will be excluded.",
    )

# Keep only the 12-month study period.
month_labels = {str(month) for month in MONTHS}

study_posts = matches[
    matches["month"].isin(month_labels)
].copy()

# Count each unique post once in the sample total.
sample_counts = (
    study_posts.drop_duplicates("id")
    .groupby("month")
    .size()
    .to_dict()
)

# Expand multi-label assignments into one row per post and topic.
assignment_rows = []

for _, post in study_posts.iterrows():
    topics = [
        topic.strip()
        for topic in str(post["matched_topics"]).split(";")
        if topic.strip() in TOPICS
    ]

    for topic in set(topics):
        assignment_rows.append({
            "id": post["id"],
            "month": post["month"],
            "subtopic_title": topic,
        })

assignments = pd.DataFrame(
    assignment_rows,
    columns=["id", "month", "subtopic_title"],
).drop_duplicates(["id", "month", "subtopic_title"])

# Count unique posts assigned to each topic each month.
if assignments.empty:
    topic_counts = pd.DataFrame(
        columns=["month", "subtopic_title", "posts"]
    )
else:
    topic_counts = (
        assignments.groupby(["month", "subtopic_title"])["id"]
        .nunique()
        .reset_index(name="posts")
    )

# Create all 120 month-topic combinations, including zero counts.
grid = pd.MultiIndex.from_product(
    [month_labels, TOPICS],
    names=["month", "subtopic_title"],
).to_frame(index=False)

# Preserve chronological month order.
month_order = {str(month): i for i, month in enumerate(MONTHS)}
grid["month_order"] = grid["month"].map(month_order)

monthly = grid.merge(
    topic_counts,
    on=["month", "subtopic_title"],
    how="left",
)

monthly["posts"] = monthly["posts"].fillna(0).astype(int)

# Add sample and classification totals for each month.
classified_counts = (
    assignments.groupby("month")["id"].nunique().to_dict()
    if not assignments.empty
    else {}
)

assignment_totals = (
    assignments.groupby("month").size().to_dict()
    if not assignments.empty
    else {}
)

monthly["reddit_posts_in_month"] = (
    monthly["month"].map(sample_counts).fillna(0).astype(int)
)

monthly["classified_posts_in_month"] = (
    monthly["month"].map(classified_counts).fillna(0).astype(int)
)

monthly["topic_assignments_in_month"] = (
    monthly["month"].map(assignment_totals).fillna(0).astype(int)
)

# Share of all topic assignments, not share of all Reddit posts.
monthly["topic_share_of_assignments"] = (
    monthly["posts"]
    / monthly["topic_assignments_in_month"].replace(0, pd.NA)
).fillna(0)

monthly = monthly.sort_values(
    ["month_order", "subtopic_title"]
).drop(columns=["month_order"])

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
monthly.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

# Report validation checks.
print(f"Posts in study period: {study_posts['id'].nunique()}")
print(f"Classified posts in study period: {len(set(assignments['id'])) if not assignments.empty else 0}")
print(f"Topic assignments in study period: {len(assignments)}")
print(f"Rows written: {len(monthly)}")
print(f"Months covered: {monthly['month'].nunique()}")
print(f"Topics covered: {monthly['subtopic_title'].nunique()}")
print(f"Saved: {OUTPUT_FILE.relative_to(ROOT)}")

print("\nMonthly sample sizes:")
print(
    monthly[["month", "reddit_posts_in_month"]]
    .drop_duplicates()
    .to_string(index=False)
)
