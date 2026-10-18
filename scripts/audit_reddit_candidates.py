
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "data" / "reddit_sc" / "posts.csv"
MATCHES = ROOT / "data" / "reddit_topic_matches.csv"

# Specific phrases first; generic terms such as "logic" and "language"
# are excluded because they create too many irrelevant matches.
TERMS = [
    "artificial general intelligence",
    "AI alignment",
    "AI safety",
    "game AI",
    "NPC AI",
    "cognitive science",
    "cognitive architecture",
    "decision theory",
    "decision tree",
    "generative AI",
    "large language model",
    "ChatGPT",
    "retrieval augmented generation",
    "knowledge representation",
    "knowledge graph",
    "automated reasoning",
    "theorem proving",
    "formal verification",
    "formal methods",
    "program synthesis",
    "natural language processing",
    "language technology",
    "speech recognition",
    "sentiment analysis",
    "machine learning",
    "neural network",
    "deep learning",
    "reinforcement learning",
    "operations research",
    "linear programming",
    "combinatorial optimization",
    "constraint satisfaction",
    "heuristic search",
    "problem solving",
    "Hamiltonicity",
    "shortest path",
    "max flow",
]

def contains_phrase(text, term):
    pattern = r"(?<!\w)" + re.escape(term).replace(r"\ ", r"\s+") + r"(?!\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None

with POSTS.open(encoding="utf-8-sig", newline="") as f:
    posts = {r["id"]: r for r in csv.DictReader(f)}

with MATCHES.open(encoding="utf-8-sig", newline="") as f:
    matches = list(csv.DictReader(f))

candidates = []

for match in matches:
    if match["matched_topics"].strip():
        continue

    post = posts.get(match["id"], {})
    title = post.get("title", "")
    body = post.get("selftext", "")
    full_text = f"{title}\n{body}"

    found = [term for term in TERMS if contains_phrase(full_text, term)]

    if found:
        candidates.append((post, found))

print(f"Unmatched posts with specific candidate phrases: {len(candidates)}")

for i, (post, found) in enumerate(candidates[:60], 1):
    print(f"\n{i:02d}. {post.get('title', '')}")
    print(f"    Phrases: {', '.join(found)}")
    body = (post.get("selftext") or "").replace("\n", " ")
    print(f"    Body: {body[:250] or '[No body text]'}")
