#!/usr/bin/env python3
"""
Reddit scraper for STATS 401 using the SocialCrawl API (https://www.socialcrawl.dev).

Collects text-only posts and comments from r/jobs and r/computerscience.
SocialCrawl bills per request in credits, so the script is budget-driven:
it spends at most --post-credits on post listings and --comment-credits on
comment trees, then stops. Output is resumable JSONL + CSV in data/reddit_sc/.

Costs (Reddit platform):
  subreddit listing   1 credit / page (~15-25 posts)
  post/comments       5 credits / post (full threaded tree)
  search/comments     1 credit / page (<=25 comments)

Usage:
    python scripts/socialcrawl_scraper.py --post-credits 50 --comment-credits 45
    python scripts/socialcrawl_scraper.py --help
"""

import argparse
import collections
import csv
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

import requests

API_BASE = "https://www.socialcrawl.dev/v1"
DEFAULT_SUBREDDITS = ["jobs", "computerscience"]

# Listings to walk, in priority order (each page = 1 credit).
LISTINGS = (
    [("new", {}), ("hot", {})]
    + [("top", {"timeframe": t}) for t in ("all", "year", "month", "week")]
    + [("rising", {})]
)
# Credits spent on any one listing before moving on, so a single deep
# listing doesn't eat the whole budget.
MAX_PAGES_PER_LISTING = 8

# Terms for the comment-search phase (`search/comments`, 1 credit per page of
# <=25). Reddit's comment index is scoped with `subreddit:<name> <terms>`.
# A spread of core CS topics keeps the sample broad rather than letting a few
# mega-threads dominate; each term pulls from different discussions.
COMMENT_QUERIES = [
    "algorithm", "complexity", "data structures", "recursion", "compiler",
    "operating system", "memory", "pointer", "database", "networking",
    "machine learning", "neural network", "theory of computation",
    "turing machine", "graph", "sorting", "cache", "concurrency",
    "functional programming", "assembly", "cryptography", "distributed systems",
    "discrete math", "proof", "programming language", "career", "degree",
    "textbook", "research", "internship",
]

IMG_HOSTS = re.compile(
    r"i\.redd\.it|v\.redd\.it|preview\.redd\.it|reddit\.com/gallery|imgur\.com|"
    r"giphy\.com|gfycat|\.(png|jpe?g|gif|webp|mp4)(\?|$)", re.I)
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
MD_LINK_RE = re.compile(r"!?\[[^\]]*\]\([^)]*\)")
MD_IMG_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)|preview\.redd\.it|i\.redd\.it|giphy\.com", re.I)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def load_dotenv(path=".env"):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def log(*args):
    print(time.strftime("%H:%M:%S"), *args, flush=True)


def dig(obj, *path, default=None):
    """Safe nested lookup: dig(d, 'a', 'b') -> d['a']['b'] or default."""
    for key in path:
        if isinstance(obj, dict) and key in obj:
            obj = obj[key]
        else:
            return default
    return obj if obj is not None else default


def text_without_links(text):
    text = MD_LINK_RE.sub(" ", text)
    text = URL_RE.sub(" ", text)
    return re.sub(r"[\s\W_]+", " ", text).strip()


def is_link_only(text):
    return len(text_without_links(text)) == 0


def is_deleted(text):
    return (text or "").strip() in ("[deleted]", "[removed]", "")


# --------------------------------------------------------------------------- #
# SocialCrawl client
# --------------------------------------------------------------------------- #


class BudgetExhausted(Exception):
    pass


class SocialCrawl:
    def __init__(self, api_key, reserve=2):
        self.s = requests.Session()
        self.s.headers.update({"x-api-key": api_key,
                               "User-Agent": "stats401-reddit-scraper/1.0"})
        self.reserve = reserve            # never spend below this balance
        self.remaining = None
        self.spent = 0

    def balance(self):
        r = self.s.get(f"{API_BASE}/credits/balance", timeout=30)
        r.raise_for_status()
        self.remaining = r.json()["data"]["balance"]
        return self.remaining

    def get(self, resource, params, cost, max_retries=4):
        """GET /v1/reddit/<resource>. `cost` is the expected credit charge,
        checked against the balance before the call."""
        if self.remaining is not None and self.remaining - cost < self.reserve:
            raise BudgetExhausted(
                f"balance {self.remaining} - cost {cost} would go below "
                f"reserve {self.reserve}")
        idem = str(uuid.uuid4())
        for attempt in range(max_retries):
            try:
                r = self.s.get(f"{API_BASE}/reddit/{resource}", params=params,
                               headers={"Idempotency-Key": idem}, timeout=60)
            except requests.RequestException as e:
                log(f"network error {e!r}; retry")
                time.sleep(2 ** attempt)
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                wait = float(r.headers.get("Retry-After", 2 ** attempt))
                log(f"{r.status_code} on {resource}; retry in {wait:.0f}s")
                time.sleep(wait)
                continue
            payload = r.json()
            used = payload.get("credits_used", 0) or 0
            self.spent += used
            if payload.get("credits_remaining") is not None:
                self.remaining = payload["credits_remaining"]
            if r.status_code == 402:
                raise BudgetExhausted(payload.get("error"))
            if not payload.get("success"):
                log(f"error {r.status_code} on {resource} {params}: "
                    f"{payload.get('error')}")
                return None
            return payload
        log(f"giving up on {resource} {params}")
        return None


# --------------------------------------------------------------------------- #
# Storage (resumable JSONL, same layout as reddit_scraper.py)
# --------------------------------------------------------------------------- #


class Store:
    def __init__(self, out_dir):
        self.out = Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.posts_path = self.out / "posts.jsonl"
        self.comments_path = self.out / "comments.jsonl"
        self.state_path = self.out / "state.json"
        self.state = {"listing_cursors": {}, "comments_fetched": [],
                      "credits_spent": 0}
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text())
        self.posts = {}
        self.comment_ids = set()
        if self.posts_path.exists():
            for line in self.posts_path.open():
                p = json.loads(line)
                self.posts[p["id"]] = p
        if self.comments_path.exists():
            for line in self.comments_path.open():
                self.comment_ids.add(json.loads(line)["id"])
        self._pf = self.posts_path.open("a")
        self._cf = self.comments_path.open("a")

    def add_post(self, p):
        if p["id"] in self.posts:
            return False
        self.posts[p["id"]] = p
        self._pf.write(json.dumps(p, ensure_ascii=False) + "\n")
        return True

    def add_comment(self, c):
        if c["id"] in self.comment_ids:
            return False
        self.comment_ids.add(c["id"])
        self._cf.write(json.dumps(c, ensure_ascii=False) + "\n")
        return True

    def flush(self):
        self._pf.flush()
        self._cf.flush()
        self.state_path.write_text(json.dumps(self.state, indent=1))

    def dump_raw(self, name, payload):
        (self.out / f"raw_{name}.json").write_text(
            json.dumps(payload, indent=1, ensure_ascii=False))

    def export_csv(self):
        for name, path in (("posts", self.posts_path),
                           ("comments", self.comments_path)):
            if not path.exists():
                continue
            rows = [json.loads(l) for l in path.open()]
            if rows:
                with (self.out / f"{name}.csv").open("w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                    w.writeheader()
                    w.writerows(rows)


# --------------------------------------------------------------------------- #
# Record shaping / filtering (SocialCrawl canonical Post / Comment objects)
# --------------------------------------------------------------------------- #


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def post_id_from_url(url):
    m = re.search(r"/comments/([a-z0-9]+)", url or "")
    return m.group(1) if m else None


def shape_post(row, subreddit, source):
    p = row.get("post", row)
    url = p.get("url") or dig(p, "ext", "permalink") or ""
    pid = post_id_from_url(url) or p.get("id")
    title = dig(p, "ext", "title") or p.get("title") or ""
    body = dig(p, "ext", "selftext")
    if body is None:
        # content.text is title + body joined; strip the title prefix.
        text = dig(p, "content", "text", default="") or ""
        body = text[len(title):].strip() if text.startswith(title) else text
    return {
        "id": pid,
        "subreddit": dig(p, "ext", "subreddit") or subreddit,
        "title": title,
        "selftext": body,
        "author": dig(p, "author", "username"),
        "created_utc": dig(p, "ext", "published_at_epoch"),
        "created_at": p.get("published_at"),
        "score": dig(p, "engagement", "likes"),
        "upvote_ratio": dig(p, "ext", "upvote_ratio"),
        "num_comments": dig(p, "engagement", "comments"),
        "link_flair_text": dig(p, "ext", "flair"),
        "media_urls": as_list(dig(p, "content", "media_urls")),
        "url": url,
        "source_listing": source,
    }


def post_is_text_only(sp):
    body = sp["selftext"] or ""
    if is_deleted(body) or is_deleted(sp["title"]):
        return False
    if sp["author"] in (None, "[deleted]"):
        return False
    media = [m if isinstance(m, str) else json.dumps(m)
             for m in (sp["media_urls"] or [])]
    own = sp["id"] or "\0"
    external = [m for m in media if own not in m]
    if any(IMG_HOSTS.search(m) for m in external):
        return False                      # image / video / gallery post
    if MD_IMG_RE.search(body) or is_link_only(body):
        return False
    return True


def shape_comment(row, post_id, depth):
    c = row.get("comment", row)
    return {
        "id": c.get("id"),
        "post_id": post_id,
        "parent_id": c.get("parent_id"),
        "subreddit": dig(c, "ext", "subreddit"),
        "author": dig(c, "author", "username"),
        "body": c.get("text") or dig(c, "content", "text"),
        "created_utc": dig(c, "ext", "published_at_epoch"),
        "created_at": c.get("published_at"),
        "score": dig(c, "engagement", "likes"),
        "depth": dig(c, "ext", "depth", default=depth),
        "is_submitter": dig(c, "ext", "is_submitter"),
        "sentiment": dig(row, "computed", "labels", "sentiment", "score_0_1"),
        "url": c.get("url"),
    }


def comment_is_text(sc):
    body = sc["body"] or ""
    if is_deleted(body) or sc["author"] in (None, "[deleted]"):
        return False
    if MD_IMG_RE.search(body) or is_link_only(body):
        return False
    return True


def walk_tree(rows, depth=0):
    for row in rows:
        c = row.get("comment", row)
        yield row, depth
        for reply in c.get("replies") or row.get("replies") or []:
            yield from walk_tree([reply], depth + 1)


# --------------------------------------------------------------------------- #
# Phases
# --------------------------------------------------------------------------- #


def collect_posts(client, store, subreddits, credits, only=None,
                  max_pages=MAX_PAGES_PER_LISTING):
    """Walk listings round-robin across subreddits until `credits` spent."""
    spent = 0
    jobs = []
    for name, params in LISTINGS:
        if only and name not in only:
            continue
        for sub in subreddits:
            jobs.append((f"{sub}/{name}/{params.get('timeframe', '')}",
                         sub, name, params))
    cursors = store.state["listing_cursors"]
    active = [j for j in jobs if cursors.get(j[0]) != "DONE"]
    pages = collections.Counter()
    dumped = False

    while active and spent < credits:
        for job in list(active):
            if spent >= credits:
                break
            key, sub, name, params = job
            q = {"subreddit": sub, "sort": name, **params}
            if cursors.get(key):
                q["cursor"] = cursors[key]
            payload = client.get("subreddit", q, cost=1)
            if payload is None:
                active.remove(job)
                continue
            spent += payload.get("credits_used", 0) or 0
            if not dumped:
                store.dump_raw("subreddit_page", payload)
                dumped = True
            items = dig(payload, "data", "items", default=[])
            kept = 0
            for row in items:
                sp = shape_post(row, sub, key)
                if sp["id"] and post_is_text_only(sp) and store.add_post(sp):
                    kept += 1
            pages[key] += 1
            has_more = dig(payload, "pagination", "has_more", default=False)
            nxt = dig(payload, "pagination", "next_cursor")
            if not has_more or not nxt or not items:
                cursors[key] = "DONE"
                active.remove(job)
            else:
                cursors[key] = nxt
                if pages[key] >= max_pages:
                    active.remove(job)     # park it; resumes on next run
            store.state["credits_spent"] += payload.get("credits_used", 0) or 0
            store.flush()
            log(f"[{key}] page={pages[key]} rows={len(items)} kept={kept} "
                f"posts={len(store.posts)} credits_left={client.remaining}")
    return spent


def collect_comments(client, store, credits, max_per_post):
    """Fetch full comment trees (5 cr each) for the most-commented posts,
    alternating subreddits."""
    spent = 0
    fetched = set(store.state["comments_fetched"])
    queues = collections.defaultdict(list)
    for p in store.posts.values():
        if p["id"] not in fetched and (p.get("num_comments") or 0) > 0:
            queues[p["subreddit"].lower()].append(p)
    for q in queues.values():
        q.sort(key=lambda p: p["num_comments"], reverse=True)
    order = []
    while any(queues.values()):
        for sub in list(queues):
            if queues[sub]:
                order.append(queues[sub].pop(0))

    dumped = False
    for p in order:
        if spent + 5 > credits:
            break
        payload = client.get("post/comments", {"url": p["url"]}, cost=5)
        if payload is None:
            continue
        spent += payload.get("credits_used", 0) or 0
        if not dumped:
            store.dump_raw("post_comments", payload)
            dumped = True
        items = dig(payload, "data", "items", default=[])
        added = seen = 0
        for row, depth in walk_tree(items):
            seen += 1
            if max_per_post and added >= max_per_post:
                break
            sc = shape_comment(row, p["id"], depth)
            sc["subreddit"] = sc["subreddit"] or p["subreddit"]
            if sc["id"] and comment_is_text(sc) and store.add_comment(sc):
                added += 1
        store.state["comments_fetched"].append(p["id"])
        store.state["credits_spent"] += payload.get("credits_used", 0) or 0
        store.flush()
        log(f"[comments r/{p['subreddit']} {p['id']}] reported="
            f"{p['num_comments']} received={seen} kept={added} "
            f"truncated={dig(payload, 'data', 'truncated')} "
            f"total={len(store.comment_ids)} credits_left={client.remaining}")
    return spent


def collect_comment_search(client, store, subreddit, credits, queries=None):
    """Pull comments from Reddit's comment index, scoped to one subreddit.

    `search/comments` costs 1 credit for a page of <=25 comments, which beats
    a 5-credit comment tree whenever the tree is not huge, and it spreads the
    sample over many threads instead of a handful of mega-threads.
    """
    spent = 0
    queries = queries or COMMENT_QUERIES
    done = store.state.setdefault("search_queries_done", [])
    for term in queries:
        if spent >= credits:
            break
        if term in done:
            continue
        cursor, pages, kept_total = None, 0, 0
        while spent < credits:
            params = {"query": f"subreddit:{subreddit} {term}", "sort": "new"}
            if cursor:
                params["cursor"] = cursor
            payload = client.get("search/comments", params, cost=1)
            if payload is None:
                break
            spent += payload.get("credits_used", 0) or 0
            store.state["credits_spent"] += payload.get("credits_used", 0) or 0
            items = dig(payload, "data", "items", default=[])
            kept = 0
            for row in items:
                c = row.get("comment", row)
                sc_row = shape_comment(row, c.get("post_id"), 0)
                sc_row["subreddit"] = sc_row["subreddit"] or subreddit
                # The index is loosely ranked and can stray off-subreddit.
                if sc_row["subreddit"].lower() != subreddit.lower():
                    continue
                if sc_row["id"] and comment_is_text(sc_row) and \
                        store.add_comment(sc_row):
                    kept += 1
            pages += 1
            kept_total += kept
            cursor = dig(payload, "pagination", "next_cursor")
            if not dig(payload, "pagination", "has_more", default=False) \
                    or not cursor or not items:
                break
        done.append(term)
        store.flush()
        log(f"[search '{term}'] pages={pages} kept={kept_total} "
            f"comments={len(store.comment_ids)} credits_left={client.remaining}")
    return spent


# --------------------------------------------------------------------------- #


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subreddits", nargs="+", default=DEFAULT_SUBREDDITS)
    ap.add_argument("--post-credits", type=int, default=50,
                    help="credits to spend on post listings (1 cr/page)")
    ap.add_argument("--comment-credits", type=int, default=45,
                    help="credits to spend on comment trees (5 cr/post)")
    ap.add_argument("--listings", nargs="+", default=None,
                    help="restrict to these sorts, e.g. --listings new "
                         "(new is by far the highest text-post yield)")
    ap.add_argument("--max-pages", type=int, default=MAX_PAGES_PER_LISTING,
                    help="pages to walk per listing before parking it "
                         "(raise it to deep-paginate a single subreddit)")
    ap.add_argument("--max-comments-per-post", type=int, default=0,
                    help="cap per post (0 = keep the whole tree)")
    ap.add_argument("--search-credits", type=int, default=0,
                    help="credits for the comment-search phase "
                         "(1 cr per page of <=25 comments)")
    ap.add_argument("--reserve", type=int, default=2,
                    help="never let the balance drop below this")
    ap.add_argument("--out", default="data/reddit_sc")
    ap.add_argument("--skip-posts", action="store_true")
    ap.add_argument("--skip-comments", action="store_true")
    args = ap.parse_args()

    load_dotenv()
    key = os.environ.get("SOCIALCRAWL_API_KEY")
    if not key:
        sys.exit("Set SOCIALCRAWL_API_KEY in .env")

    client = SocialCrawl(key, reserve=args.reserve)
    store = Store(args.out)
    log(f"balance={client.balance()} posts_on_disk={len(store.posts)} "
        f"comments_on_disk={len(store.comment_ids)}")
    try:
        if not args.skip_posts:
            collect_posts(client, store, args.subreddits, args.post_credits,
                          args.listings, args.max_pages)
        if not args.skip_comments:
            collect_comments(client, store, args.comment_credits,
                             args.max_comments_per_post)
        if args.search_credits:
            collect_comment_search(client, store, args.subreddits[0],
                                   args.search_credits)
    except BudgetExhausted as e:
        log(f"stopping: {e}")
    except KeyboardInterrupt:
        log("interrupted — progress saved, rerun to resume")
    finally:
        store.flush()
        store.export_csv()
        log(f"done: posts={len(store.posts)} comments={len(store.comment_ids)} "
            f"credits_spent_this_run={client.spent} balance={client.remaining}")


if __name__ == "__main__":
    main()
