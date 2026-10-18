# STATS 401 Final Project GitHub Submission Structure
- `proposal.md` — the formatted project proposal.
- `assets/` — embedded reference figures.

Keep the `assets` folder in the same directory as `proposal.md` so all figures render correctly on GitHub.

## Reddit data collection

Two scrapers are available. Both write the same schema (JSONL + CSV) and are resumable.

### SocialCrawl (`scripts/socialcrawl_scraper.py` → `data/reddit_sc/`)

Uses the SocialCrawl API (credit-billed; the free tier is 100 credits).
Set `SOCIALCRAWL_API_KEY` in `.env`, then e.g.

    python3 scripts/socialcrawl_scraper.py --post-credits 45 --listings new --skip-comments
    python3 scripts/socialcrawl_scraper.py --skip-posts --comment-credits 30

Phases: `--post-credits` walks subreddit listings (1 cr/page), `--comment-credits`
pulls whole comment trees (5 cr/post), `--search-credits` reads Reddit's comment
index scoped to the subreddit (1 cr per page of <=25).

Current dataset (`data/reddit_sc/`, collected Oct 18 2026, r/computerscience only,
96 credits): **604 posts, 1,051 comments across 105 threads.**

Measured yields on that run:

| Phase | Credits | Yield | Notes |
| --- | --- | --- | --- |
| `new` listing | 35 | 604 posts (~17/cr) | Still productive at page 35; best post source |
| Comment trees | 45 | 705 comments (~16/cr) | ~22 top-level per call, all `truncated=True` |
| Comment search | 17 | 346 comments (~20/cr) | Spread over ~100 threads; best breadth |

`hot` and `rising` almost entirely duplicate `new`, and `top` on image-heavy
subreddits is mostly screenshots (dropped by the text-only filter), so
`--listings new` is the efficient default.

Note: the `post/comments` endpoint returned far deeper trees in Sept 2026
(500-1,500 comments per 5-credit call) than in Oct 2026 (~60-156). Re-measure
before budgeting a large comment run.

### Official Reddit Data API (`scripts/reddit_scraper.py` → `data/reddit/`)

Free, for larger volumes. Collects text-only posts and comments from r/jobs and
r/computerscience (OAuth, ≤100 requests/min, descriptive User-Agent, no deleted content stored).

1. Create a **script** app at https://www.reddit.com/prefs/apps.
2. Copy `.env.example` to `.env` and fill in the client id/secret and your username.
3. Run `python3 scripts/reddit_scraper.py --posts 10000 --comments 20000`.

Both runs are resumable — rerun the same command after an interruption.

Reddit's Data API terms require removing content that is later deleted from
Reddit and recommend purging stored user data within 48 hours, so treat the
raw dump as a working file rather than a permanent archive.
