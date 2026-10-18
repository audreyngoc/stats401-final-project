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

The following directory tree documents the main project files, visualization code, datasets, and data-processing scripts. It includes all files currently present in the `scripts/`, `data/`, `css/`, and `js/` directories.

```text
.
├── index.html
├── README.md
├── proposal.md
├── .gitignore
├── package.json
├── package-lock.json
│
├── assets/                                  # Supporting figures and images for project documentation
│
├── css/
│   ├── comparative-streamgraph.css          # Styles for the Wikipedia–Reddit comparison
│   ├── jobs.css                             # Styles for career exploration
│   ├── knowledge.css                        # Styles for knowledge-tree and network views
│   ├── streamgraph.css                      # Styles for the Wikipedia pageview streamgraph
│   └── style.css                            # Global website layout and shared styles
│
├── js/
│   ├── app.js                               # Initializes shared application behavior and article data
│   ├── comparative-streamgraph.js           # Visualization 5: Wikipedia–Reddit comparison
│   ├── jobs.js                              # Visualization 6: career exploration
│   ├── knowledge.js                         # Shared knowledge-graph data and article-selection logic
│   ├── network.js                           # Visualization 2: force-directed knowledge network
│   ├── scatter.js                           # Visualization 3: structural importance versus popularity
│   ├── streamgraph.js                       # Visualization 4: Wikipedia pageview streamgraph
│   └── tree.js                              # Visualization 1: seed-article search and hierarchical tree
│
├── data/
│   ├── ai_adjacency.json                    # Article adjacency information for network exploration
│   ├── ai_articles_10000.csv                # Article dataset containing the selected 10,000 articles
│   ├── ai_communities.json                  # Detected knowledge-network communities
│   ├── ai_edges.csv                         # Edge list representing article hyperlinks
│   ├── ai_graph.json                        # Graph data in JSON format
│   ├── ai_group_106238.json                 # Article-group data for group ID 106238
│   ├── ai_group_1467948.json                # Article-group data for group ID 1467948
│   ├── ai_group_1654769.json                # Article-group data for group ID 1654769
│   ├── ai_group_16920.json                  # Article-group data for group ID 16920
│   ├── ai_group_21652.json                  # Article-group data for group ID 21652
│   ├── ai_group_233488.json                 # Article-group data for group ID 233488
│   ├── ai_group_265752.json                 # Article-group data for group ID 265752
│   ├── ai_group_43476.json                  # Article-group data for group ID 43476
│   ├── ai_group_586357.json                 # Article-group data for group ID 586357
│   ├── ai_group_73291755.json               # Article-group data for group ID 73291755
│   ├── ai_groups.json                       # Collection of article groups
│   ├── ai_manifest.json                     # Dataset metadata and graph summary
│   ├── ai_neighbors.json                    # Neighbor information for knowledge-network exploration
│   ├── ai_nodes.csv                         # Article nodes and core metadata
│   ├── ai_nodes_enriched.csv                # Enriched article metadata and network attributes
│   ├── ai_nodes_with_pageviews.csv          # Article metadata combined with pageview information
│   ├── ai_pageviews_failures.csv            # Records of pageview retrieval failures
│   ├── ai_pageviews_monthly.csv             # Monthly Wikipedia pageview records
│   ├── ai_pageviews_summary.csv             # Summary statistics for Wikipedia pageviews
│   ├── ai_subtopic_monthly.csv              # Monthly Wikipedia pageviews aggregated by subtopic
│   ├── ai_tree.json                         # Hierarchical article-tree data
│   ├── ai_validation.json                   # Data-validation results
│   ├── archive.zip                          # Archived data files
│   │
│   ├── Job Dataset for IT Professionals/
│   │   ├── CleanData_jotpars.csv             # Cleaned version of the original job-posting dataset
│   │   ├── Dataset_jotpars.csv               # Original job-posting dataset
│   │   └── source.txt                        # Source information for the job dataset
│   │
│   ├── jobs_postings.csv                    # Processed job-posting data for career exploration
│   │
│   ├── reddit_sc/
│   │   ├── comments.csv                     # Collected Reddit comments in CSV format
│   │   ├── comments.jsonl                   # Collected Reddit comments in JSON Lines format
│   │   ├── posts.csv                        # Collected Reddit posts in CSV format
│   │   └── posts.jsonl                      # Collected Reddit posts in JSON Lines format
│   │
│   ├── reddit_subtopic_monthly.csv          # Monthly Reddit topic assignments for Visualization 5
│   ├── reddit_topic_matches.csv             # Post-level Reddit topic-classification results
│   └── reddit_topic_summary.csv             # Summary of Reddit topic-classification results
│
└── scripts/
    ├── AI_10000_pipeline_README.md           # Documentation for the 10,000-article data pipeline
    ├── audit_reddit_candidates.py            # Audits Reddit candidate records and potential topic matches
    ├── build_graph.py                        # Builds the knowledge graph from article and link data
    ├── build_reddit_monthly.py               # Aggregates classified Reddit topics by month
    ├── check_interactions.cjs                # Checks or tests website interactions
    ├── classify_reddit_topics.py             # Applies keyword-based, multi-label Reddit topic classification
    ├── collect_ai_visualization_data.py      # Collects and prepares data for the AI knowledge visualizations
    ├── compute_global_indegree.py             # Computes global in-degree values for articles
    ├── create_ai_10000_csv.py                # Creates a CSV dataset for the selected 10,000 articles
    ├── extract_redirects.py                  # Extracts Wikipedia redirect information
    ├── inspect_reddit_data.py                # Inspects collected Reddit records
    ├── json_to_parquet.py                    # Converts JSON data into Parquet format
    ├── prepare_jobs.py                       # Prepares job-posting data for career exploration
    ├── prepare_visualizations.py              # Prepares datasets for the visualizations
    ├── resolve_redirects.py                  # Resolves Wikipedia redirects
    ├── review_reddit_matches.py              # Supports review of Reddit topic-classification matches
    ├── socialcrawl_scraper.py                # Collects Reddit posts and comments through SocialCrawl
    └── sql_links_to_parquet.py               # Converts SQL link data into Parquet format
```

### How the files work together

- **Knowledge graph and article exploration (Visualizations 1–3):** The data-processing scripts collect, clean, and organize Wikipedia article and hyperlink data. The resulting node, edge, adjacency, community, and tree datasets support the seed-article tree, force-directed network, and structural-importance versus popularity scatterplot.

- **Wikipedia attention over time (Visualization 4):** `data/ai_pageviews_monthly.csv` and `data/ai_subtopic_monthly.csv` contain monthly pageview data used to examine attention to computing subtopics. `js/streamgraph.js` and `css/streamgraph.css` implement and style the streamgraph.

- **Wikipedia–Reddit comparison (Visualization 5):** The collected Reddit records in `data/reddit_sc/` are processed into topic-classification and monthly aggregation files. `js/comparative-streamgraph.js` and `css/comparative-streamgraph.css` display the comparison.

- **Career exploration (Visualization 6):** The original and cleaned job-posting files are stored in `data/Job Dataset for IT Professionals/`. `scripts/prepare_jobs.py` prepares job data, and `data/jobs_postings.csv` supplies processed information for `js/jobs.js`, styled by `css/jobs.css`.

- **Shared website structure:** `index.html` integrates the visualization components. The files `js/app.js` and `js/knowledge.js` support shared application behavior, while `css/style.css` provides global styling.

- **Reproducibility and validation:** The scripts in `scripts/` document the data-processing workflow, and `data/ai_validation.json` stores validation results. `scripts/check_interactions.cjs` supports interaction checks.

This guide describes the files present in the repository listing. Individual outputs may represent intermediate processing stages, archived data, or final datasets used by the website. Refer to `scripts/AI_10000_pipeline_README.md` for additional details about the Wikipedia article pipeline and the data-collection instructions elsewhere in this README for the Reddit collection workflow.

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

## Roles and Responsibilities

- **Christine Herbst:** collected and cleaned Wikipedia data; prepared the Wikipedia data pipeline; implemented Visualizations 1 and 2 (seed-article search/tree and force-directed network); contributed to the interim check-in and final report.
- **Temuulen Enkhtamir:** collected and cleaned Reddit and job-posting data; prepared related data-processing outputs; implemented Visualizations 3 and 6 (structural-importance versus popularity and career exploration).
- **Ly Minh Ngoc (Audrey) Tran:** led proposal and interim-check-in writing; implemented Visualizations 4 and 5 (Wikipedia pageview streamgraph and Wikipedia–Reddit comparative streamgraph); contributed to interaction design, webpage layout, and styling.
- **All team members:** contributed to project planning, visualization design decisions, integration, testing, interpretation, documentation, and presentation preparation.

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
