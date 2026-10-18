# Navigating Knowledge

**An interactive exploration of computing concepts through Wikipedia's
hyperlink network, pageviews, Reddit discussions, and career data.**

-   **Live website:**
    https://audreyngoc.github.io/stats401-final-project/
-   **Repository:**
    https://github.com/audreyngoc/stats401-final-project/
-   **Course:** STATS 401 --- Data Acquisition and Visualization
-   **Team:** Christine Herbst, Ly Minh Ngoc (Audrey) Tran, and Temuulen
    Enkhtamir

## Project overview

Computing knowledge is interconnected, but beginners often encounter it
as a collection of separate articles. This project turns selected
Wikipedia articles and their links into an interactive environment for
exploring how concepts branch, connect, and attract attention. It
combines five core visualizations with an additional career-exploration
view.

The project is designed for learners who want an initial map of a
computing topic, and for readers interested in the differences between
the structure of online knowledge, reader attention, and sampled online
discussion.

## GitHub submission structure

- `proposal.md` — the formatted project proposal.
- `assets/` — embedded reference figures used by `proposal.md`.

Keep the `assets/` folder in the same directory as `proposal.md` so that all relative image paths render correctly on GitHub. Keep the final report and poster in the repository as well, and add links to them in the Project Deliverables section once their filenames are finalized.

## Questions we explore

1.  How does a computing topic expand from a starting Wikipedia article?
2.  Which articles occupy important structural positions in the selected
    hyperlink network?
3.  Where do topic branches cluster, bridge, or reconnect?
4.  Does structural importance correspond to Wikipedia pageview
    attention?
5.  How does pageview attention change over time?
6.  How does the distribution of Wikipedia pageviews compare with topic
    assignments in a sample of Reddit posts?
7.  As an extension, how can computing knowledge areas be explored
    alongside job-posting information?

## Explore the visualizations

1.  **Seed-article search and hierarchical tree** --- start with an
    article and progressively explore related topics. Expansion/collapse
    and depth controls help manage complexity.
2.  **Force-directed knowledge network** --- inspect articles and
    hyperlinks, explore clusters and cross-links, and highlight local
    neighborhoods.
3.  **Structural importance versus popularity** --- compare a network
    measure with pageviews to identify articles with different
    combinations of structural prominence and reader attention.
4.  **Wikipedia pageview streamgraph** --- explore how pageview
    distributions across computing subtopics change over time.
5.  **Wikipedia--Reddit comparative streamgraph** --- compare Wikipedia
    pageview shares with the distribution of classified topic
    assignments in a Reddit sample.
6.  **Career-exploration extension** --- connect knowledge topics with
    job titles and job-posting salary/count summaries.

Interactions vary by visualization and may include search,
expansion/collapse, filtering, selection, highlighting, zooming,
panning, reset controls, and hover details.

## Data sources

### Wikipedia articles and hyperlinks

English Wikipedia article and link data were processed into article and
edge tables. The workflow standardized titles, resolved redirects,
retained main-namespace articles, and removed duplicate links and
unresolved destinations. The selected network contains 10,000 articles
across ten computing-related subtopics, selected through a ranking
procedure combining TF--IDF similarity and in-degree.

-   MediaWiki API documentation:
    https://www.mediawiki.org/wiki/API:Links

### Wikipedia pageviews

Monthly pageviews for selected articles were collected for September
2025--August 2026 and aggregated for temporal exploration.

-   Wikimedia pageviews API:
    https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html

### Reddit discussions

The project includes a collected sample from `r/computerscience`. The current SocialCrawl dataset was collected on October 18, 2026, using 96 credits, and contains **604 posts and 1,051 comments across 105 threads**. For the September 2025–August 2026 comparison period, 427 posts fall within the target dates; 31 posts matched at least one selected topic and generated 34 multi-label topic assignments.

Two Reddit collection scripts are available. They write JSONL and CSV outputs and support resuming interrupted collection.

#### SocialCrawl scraper (`scripts/socialcrawl_scraper.py` → `data/reddit_sc/`)

SocialCrawl is a credit-billed third-party API; its free tier provides 100 credits. Set `SOCIALCRAWL_API_KEY` in a local `.env` file. Do not commit `.env` or API credentials.

Example commands:

```bash
python3 scripts/socialcrawl_scraper.py --post-credits 45 --listings new --skip-comments
python3 scripts/socialcrawl_scraper.py --skip-posts --comment-credits 30
```

The scraper supports three collection phases:

- `--post-credits` walks subreddit listings (approximately 1 credit per page).
- `--comment-credits` retrieves comment trees (approximately 5 credits per post).
- `--search-credits` searches Reddit's comment index within the subreddit (approximately 1 credit per page of up to 25 results).

Measured yields from the October 18, 2026 run:

| Phase | Credits | Yield | Notes |
| --- | ---: | --- | --- |
| `new` listing | 35 | 604 posts (about 17 per credit) | Most productive post source in this run |
| Comment trees | 45 | 705 comments (about 16 per credit) | About 22 top-level comments per call; returned trees were truncated |
| Comment search | 17 | 346 comments (about 20 per credit) | Broader coverage across approximately 100 threads |

The yields are observations from that run, not guarantees. `hot` and `rising` largely duplicated `new` in the observed collection. Comment-tree response sizes also varied substantially between September and October 2026, so re-measure yields before budgeting a large run.

#### Official Reddit Data API scraper (`scripts/reddit_scraper.py` → `data/reddit/`)

A second scraper uses Reddit's official Data API and can collect text-only posts and comments from `r/jobs` and `r/computerscience`. It uses OAuth, a descriptive User-Agent, and a request rate of no more than 100 requests per minute; deleted content is not stored.

Setup:

1. Create a **script** app at https://www.reddit.com/prefs/apps.
2. Copy `.env.example` to `.env`.
3. Fill in the required client ID, client secret, and username in `.env`.
4. Run the scraper, for example:

   ```bash
   python3 scripts/reddit_scraper.py --posts 10000 --comments 20000
   ```

Both scrapers support resuming collection after an interruption. Confirm the scripts' current arguments and required credentials before running them.

**Data retention:** Reddit's Data API terms require removing content that is later deleted and recommend purging stored user data within 48 hours. Treat raw Reddit exports as working data, not as a permanent archive, and follow the current API terms and applicable course requirements.

- SocialCrawl: https://www.socialcrawl.dev/
- Reddit API terms and policies: https://www.redditinc.com/policies/data-api-terms

### Job-posting dataset

The career extension uses the "Job Dataset for IT Professionals,"
containing 8,797 job postings with titles, descriptions, skills,
experience requirements, and salary ranges. Add the dataset's full
bibliographic citation and license/terms here before final submission.

## Important interpretation notes

-   The Wikipedia network is a selected subset, not a complete
    representation of all computing knowledge.
-   Hyperlinks indicate article-to-article links, not necessarily causal
    or semantic relationships.
-   Pageviews measure observed readership, not comprehension, quality,
    or expert-defined importance.
-   Reddit represents a limited sample from one subreddit, not all
    Reddit users or public opinion.
-   Reddit topic classification uses keyword-based, multi-label
    matching. A post may contribute to multiple topic assignments.
-   Wikipedia and Reddit percentages use different denominators:
    pageview shares versus classified assignment shares. They support
    comparison of relative composition, not comparison of absolute
    audience size.
-   A month with no classified Reddit assignments means no matches were
    observed in this sample and method; it does not prove that no
    relevant discussion occurred.
-   Salary estimates based on the midpoint of posted ranges are
    descriptive summaries, not guarantees of compensation or employment
    outcomes.

## Technology

-   **Frontend:** HTML, CSS, JavaScript
-   **Visualization:** D3.js
-   **Data processing and analysis:** Python, NetworkX, scikit-learn,
    PyArrow, DuckDB
-   **Deployment:** GitHub Pages

## Repository guide

The following files are specifically used by the temporal
visualizations; verify the current repository before relying on this
list as a complete inventory.

```text
.
├── proposal.md                 # Formatted project proposal
├── assets/                     # Reference figures embedded in proposal.md
├── index.html                  # Main project website
├── data/
│   ├── ai_subtopic_monthly.csv # Monthly Wikipedia subtopic pageviews
│   ├── reddit_sc/              # SocialCrawl JSONL/CSV outputs
│   ├── reddit/                 # Official Reddit API outputs, if collected
│   ├── reddit_topic_matches.csv
│   ├── reddit_topic_summary.csv
│   └── reddit_subtopic_monthly.csv
├── scripts/
│   ├── socialcrawl_scraper.py  # SocialCrawl collection
│   ├── reddit_scraper.py      # Official Reddit Data API collection
│   ├── inspect_reddit_data.py
│   ├── audit_reddit_candidates.py
│   ├── classify_reddit_topics.py
│   ├── review_reddit_matches.py
│   └── build_reddit_monthly.py
├── js/
│   ├── streamgraph.js          # Wikipedia pageview streamgraph
│   └── comparative-streamgraph.js
└── css/
    ├── style.css               # Shared website styles
    ├── streamgraph.css
    └── comparative-streamgraph.css
```

The file tree above documents the files identified during project
development and is not guaranteed to include every current file. Confirm
paths and stylesheet references against the current `main` branch before
submitting.

## Run locally

Because the interface loads CSV/JSON files, run it through a local web
server rather than opening `index.html` directly.

1.  Clone the repository:

    ``` bash
    git clone https://github.com/audreyngoc/stats401-final-project.git
    cd stats401-final-project
    ```

2.  Start a local static server from the repository root. For example,
    with Python:

    ``` bash
    python -m http.server 8000
    ```

3.  Open `http://localhost:8000` in your browser.

4.  If the website fails to load data, check the browser console and
    Network tab for missing files or incorrect relative paths.

No build step is described here because the project is presented as a
static HTML/CSS/JavaScript site. If the current repository introduces a
package manager or build tool, update these instructions accordingly.

## Running the data pipeline

### Reddit data collection

For SocialCrawl, first configure `SOCIALCRAWL_API_KEY` in `.env`, then run one or more collection phases as needed:

```bash
python3 scripts/socialcrawl_scraper.py --post-credits 45 --listings new --skip-comments
python3 scripts/socialcrawl_scraper.py --skip-posts --comment-credits 30
```

To use the official Reddit Data API instead, configure the OAuth fields in `.env` using `.env.example` as a guide, then run:

```bash
python3 scripts/reddit_scraper.py --posts 10000 --comments 20000
```

Do not commit `.env`, client secrets, API keys, or other credentials. Both collection scripts are resumable; rerun the relevant command after an interruption. Check the current script help and API terms before collecting more data.

### Reddit topic processing

The project includes these topic-processing scripts:

```bash
python3 scripts/inspect_reddit_data.py
python3 scripts/classify_reddit_topics.py
python3 scripts/review_reddit_matches.py
python3 scripts/build_reddit_monthly.py
```

These commands describe the intended workflow, not a guarantee that every script can run without configuration. Check each script's arguments, dependencies, and expected input files before execution. The monthly builder creates the aggregated Reddit topic data used by the comparative streamgraph.

### Run the website locally

Because the interface loads CSV/JSON files, run it through a local web server rather than opening `index.html` directly:

```bash
git clone https://github.com/audreyngoc/stats401-final-project.git
cd stats401-final-project
python3 -m http.server 8000
```

Then open `http://localhost:8000`. If a visualization does not load, inspect the browser console and Network tab for missing files, incorrect relative paths, or data-loading errors. Check `package.json` and `package-lock.json` for any additional project-specific scripts or dependencies.

## Team responsibilities

-   **Christine Herbst:** Wikipedia data acquisition and cleaning;
    seed-article tree and force-directed network.
-   **Temuulen Enkhtamir:** Reddit and job-posting data
    acquisition/cleaning; structural-importance versus popularity and
    career-exploration visualizations.
-   **Ly Minh Ngoc (Audrey) Tran:** proposal and interim writing;
    Wikipedia pageview and Wikipedia--Reddit streamgraphs; interaction
    design, webpage layout, and styling.
-   **All team members:** planning, design decisions, integration,
    testing, interpretation, documentation, and presentation
    preparation.

## Project deliverables

-   [Live interactive
    website](https://audreyngoc.github.io/stats401-final-project/)
-   [GitHub source
    repository](https://github.com/audreyngoc/stats401-final-project/)
-   `proposal.md` — project proposal
-   `assets/` — figures embedded by the proposal
-   Final report and project poster (add links here when committed)

## References

-   MediaWiki API: Links --- https://www.mediawiki.org/wiki/API:Links
-   Wikimedia Analytics API: Pageviews ---
    https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html
-   SocialCrawl --- https://www.socialcrawl.dev/
-   "Job Dataset for IT Professionals" --- **add the exact source
    citation, version/date, and license here**.
