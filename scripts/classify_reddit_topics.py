import re
from pathlib import Path

import pandas as pd


# Paths

ROOT = Path(__file__).resolve().parents[1]
POSTS_FILE = ROOT / "data" / "reddit_sc" / "posts.csv"
MATCHES_FILE = ROOT / "data" / "reddit_topic_matches.csv"
SUMMARY_FILE = ROOT / "data" / "reddit_topic_summary.csv"


# Topic keywords
# Keep terms specific enough to provide meaningful evidence.
# A keyword match is still a candidate classification, not proof that the post's main subject belongs to that topic.

TOPIC_KEYWORDS = {
    "Artificial general intelligence": [
        "artificial general intelligence",
        "general artificial intelligence",
        "agi",
        "ai alignment",
        "ai safety",
        "superintelligence",
        "ai takeover",
        "capability control",
    ],

    "Artificial intelligence in video games": [
        "artificial intelligence in video games",
        "game ai",
        "video game ai",
        "npc ai",
        "non-player character",
        "procedural generation",
        "game bot",
    ],

    "Cognition": [
        "cognition",
        "cognitive science",
        "cognitive architecture",
        "artificial consciousness",
        "theory of mind",
        "human reasoning",
    ],

    "Decision-making": [
        "decision-making",
        "decision making",
        "decision theory",
        "automated decision",
        "multi-criteria decision",
    ],

    "Generative AI": [
        "generative ai",
        "genai",
        "chatgpt",
        "gpt-4",
        "gpt-5",
        "large language model",
        "llm",
        "text-to-image",
        "ai generated",
        "stable diffusion",
        "midjourney",
        "openai",
        "claude ai",
        "gemini ai",
    ],

    "Knowledge representation and reasoning": [
        "knowledge representation",
        "knowledge graph",
        "knowledge base",
        "symbolic ai",
        "automated reasoning",
        "theorem proving",
        "logic programming",
        "expert system",
        "ontology",
        "inference engine",
        "formal verification",
        "formal methods",
        "program synthesis",
    ],

    "Machine learning": [
        "machine learning",
        "deep learning",
        "neural network",
        "supervised learning",
        "unsupervised learning",
        "reinforcement learning",
        "random forest",
        "gradient descent",
        "training data",
        "model training",
        "overfitting",
        "pattern recognition and machine learning",
    ],

    "Natural language processing": [
        "natural language processing",
        "language technology",
        "language science and technology",
        "text classification",
        "sentiment analysis",
        "tokenization",
        "named entity recognition",
        "machine translation",
        "speech recognition",
        "language model",
        "text generation",
    ],

    "Operations research": [
        "operations research",
        "linear programming",
        "integer programming",
        "combinatorial optimization",
        "quadratic unconstrained binary optimization",
        "branch-and-bound",
        "optimality gap",
        "constraint optimization",
        "scheduling optimization",
    ],

    "Problem solving": [
        "problem solving",
        "problem-solving",
        "search algorithm",
        "heuristic search",
        "a-star search",
        "a* search",
        "constraint satisfaction",
        "hamiltonicity",
        "shortest path",
        "max flow",
        "minimum cut",
        "algorithm design",
        "brute force algorithm",
        "pathfinding algorithm",
        "program synthesis",
    ],
}


# Reviewed exclusions. These are exact post titles reviewed in the audit. 
# Exclusions apply only to the listed topic, not to other topics.

EXCLUDED_TITLES = {
    "Generative AI": {
        "What does it take to make every machine 'Turing Complete'?",
        "Mechanical Computers",
        "Couldn’t someone reverse a public key’s steps to decrypt?",
    },

    "Cognition": {
        "Learning in Public CS of whole 4 years want feedback",
    },

    "Machine learning": {
        "Books about data collection methodologies?",
        "hi r/computerscience! Join Stanford Prof. Mehran Sahami "
        "on Thursday for an AMA discussing all things computer science",
        "How do you not get overwhelmed with content when doing "
        "research or studying? Also, how do you develop better intuition?",
        "HALAC 0.4.3",
        "Realistically speaking, if you were to pursue a PHD, "
        "what topics can you even research anymore?",
        "Exploring Emerging Areas in Computer Science",
        "A question about fundamental structure of algorithms",
        "What's the difference between IOAI and IAIO (AI Olympiads)?",
    },

    "Natural language processing": {
        "A book that you'd prefer over online resources?",
        "Formal Verification and Mechanistic Interpretability?",
    },

    "Operations research": {
        "How to get through theoretical CS?",
        "How can I find a collaborator for my novel algorithmic paper?",
    },

    "Problem solving": {
        "Charles H. Bennett and Gilles Brassard receive the "
        "2025 ACM A.M. Turing Award",
        "Anyone willing to explain the OSI model to me?",
        "Does this reading list cover the core layers of systems "
        "and algorithm design?",
        "Donald Knuth likes Claude",
    },
    
    "Decision-making": {
        "I've created TrackLog: a collection of Prolog libraries, examples, and guidelines for building a personal knowledge base in pure logic",
    },
}


# Matching helpers

def normalize_title(value):
    """Normalize a title for case-insensitive exact comparisons."""
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def find_keyword_matches(text, keywords):
    """
    Return keywords found using case-insensitive whole-phrase matching.

    Whole-phrase matching helps prevent short terms from matching
    inside unrelated words. It does not eliminate all contextual
    false positives, so reviewed exclusions are applied separately.
    """
    found = []

    for keyword in keywords:
        pattern = (
            r"(?<!\w)"
            + re.escape(keyword)
            + r"(?!\w)"
        )

        if re.search(pattern, text, flags=re.IGNORECASE):
            found.append(keyword)

    return found

# Load posts

if not POSTS_FILE.exists():
    raise FileNotFoundError(
        f"Could not find the posts file: {POSTS_FILE}"
    )

posts = pd.read_csv(POSTS_FILE).fillna("")

required_columns = {"id", "title"}
missing_columns = required_columns - set(posts.columns)

if missing_columns:
    raise ValueError(
        f"Missing required columns in posts.csv: {sorted(missing_columns)}"
    )

if "selftext" not in posts.columns:
    posts["selftext"] = ""

if "created_at" not in posts.columns:
    posts["created_at"] = ""

if "subreddit" not in posts.columns:
    posts["subreddit"] = ""


# Classify posts

results = []

for _, post in posts.iterrows():
    title = str(post["title"]).strip()
    body = str(post["selftext"]).strip()

    # Title and body are both used to find evidence.
    searchable_text = f"{title}\n{body}"

    matched_topics = []
    evidence_by_topic = []

    for topic, keywords in TOPIC_KEYWORDS.items():
        # Skip reviewed false positives for this specific topic.
        excluded_titles = {
            normalize_title(item)
            for item in EXCLUDED_TITLES.get(topic, set())
        }

        if normalize_title(title) in excluded_titles:
            continue

        matched_keywords = find_keyword_matches(
            searchable_text,
            keywords,
        )

        if matched_keywords:
            matched_topics.append(topic)

            evidence_by_topic.append(
                f"{topic}: {', '.join(matched_keywords)}"
            )

    results.append({
        "id": post["id"],
        "created_at": post["created_at"],
        "subreddit": post["subreddit"],
        "title": title,
        "matched_topics": "; ".join(matched_topics),
        "match_evidence": " | ".join(evidence_by_topic),
        "num_topics_matched": len(matched_topics),
    })


# Save post-level matches

matches = pd.DataFrame(results)

MATCHES_FILE.parent.mkdir(parents=True, exist_ok=True)
matches.to_csv(MATCHES_FILE, index=False, encoding="utf-8-sig")


# Save topic summary

summary_rows = []

for topic in TOPIC_KEYWORDS:
    count = matches["matched_topics"].apply(
        lambda value: topic in [
            item.strip()
            for item in str(value).split(";")
            if item.strip()
        ]
    ).sum()

    summary_rows.append({
        "topic": topic,
        "matched_posts": int(count),
    })

summary = pd.DataFrame(summary_rows)
summary.to_csv(SUMMARY_FILE, index=False, encoding="utf-8-sig")


# Print results

matched_post_count = (
    matches["num_topics_matched"].gt(0).sum()
)

total_topic_matches = matches["num_topics_matched"].sum()

print(f"Total posts: {len(matches)}")
print(f"Posts matching at least one topic: {matched_post_count}")
print(f"Posts with no topic match: {len(matches) - matched_post_count}")
print(f"Topic matches (posts can match multiple topics): {total_topic_matches}")

print("\nMatches per topic:")

for _, row in summary.iterrows():
    print(f"  {row['topic']}: {row['matched_posts']}")

print(f"\nSaved: {MATCHES_FILE.relative_to(ROOT)}")
print(f"Saved: {SUMMARY_FILE.relative_to(ROOT)}")
