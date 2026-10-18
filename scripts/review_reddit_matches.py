
import pandas as pd

matches = pd.read_csv("data/reddit_topic_matches.csv").fillna("")
posts = pd.read_csv("data/reddit_sc/posts.csv").fillna("")

# Join original post text to the classifier's results.
# The Reddit post ID is the common identifier.
if "id" in posts.columns and "id" in matches.columns:
    text_columns = [
        col for col in ["id", "selftext"]
        if col in posts.columns
    ]
    matches = matches.merge(
        posts[text_columns].drop_duplicates("id"),
        on="id",
        how="left",
    )

topic_order = [
    "Generative AI",
    "Knowledge representation and reasoning",
    "Machine learning",
    "Natural language processing",
    "Operations research",
    "Problem solving",
]

for topic in topic_order:
    subset = matches[
        matches["matched_topics"].apply(
            lambda value: topic in [
                item.strip() for item in str(value).split(";")
            ]
        )
    ]

    print(f"\n{'=' * 75}")
    print(f"{topic}: {len(subset)} matched posts")
    print("=" * 75)

    for _, row in subset.iterrows():
        print(f"\nTitle: {row['title']}")
        print(f"Evidence: {row['match_evidence']}")

        body = str(row.get("selftext", "")).strip()
        if body and body.lower() != "nan":
            print(f"Body: {body[:500]}")
        else:
            print("Body: [empty or unavailable]")

        print("-" * 50)
