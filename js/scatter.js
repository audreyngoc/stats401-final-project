const scatterWidth = 1100;
const scatterHeight = 720;

const scatterMargin = {
    top: 60,
    right: 80,
    bottom: 90,
    left: 110
};


const scatterCommunityColors = [
    "#5B8FF9",
    "#61DDAA",
    "#F6BD16"
];


Promise.all([
    d3.csv(
        "data/ai_nodes_enriched.csv",
        d => ({
            pageviews_status: d.pageviews_status,
            article_id: +d.article_id,
            title: d.title,

            depth: +d.depth,

            global_indegree:
                +d.global_indegree,

            local_indegree:
                +d.local_indegree,

            local_outdegree:
                +d.local_outdegree,

            pagerank:
                +d.pagerank,

            betweenness:
                +d.betweenness,

            community:
                +d.community,

            is_seed:
                d.is_seed === "True"
                || d.is_seed === "true",

            total_views_12m:
                +d.total_views_12m,

            avg_daily_views:
                +d.avg_daily_views
        })
    ),

    // Community names for the filter menu.
    d3.json(
        "data/ai_communities.json"
    )
])

.then(([data, communityInfo]) => {

    // Remove invalid values
    // Log scales cannot display 0.

    const filtered =
        data.filter(
            d =>
                d.pageviews_status === "complete"
                && d.global_indegree > 0
                &&
                d.total_views_12m > 0
        );


    // INNER PLOT DIMENSIONS

    const innerWidth =
        scatterWidth
        - scatterMargin.left
        - scatterMargin.right;


    const innerHeight =
        scatterHeight
        - scatterMargin.top
        - scatterMargin.bottom;


    // LOG SCALES

    const xExtent =
        d3.extent(
            filtered,
            d => d.global_indegree
        );


    const yExtent =
        d3.extent(
            filtered,
            d => d.total_views_12m
        );


    const x =
        d3.scaleLog()
            .domain([
                xExtent[0] * 0.8,
                xExtent[1] * 1.25
            ])
            .range([
                0,
                innerWidth
            ]);


    const y =
        d3.scaleLog()
            .domain([
                yExtent[0] * 0.8,
                yExtent[1] * 1.25
            ])
            .range([
                innerHeight,
                0
            ]);


    // POINT SIZE = PAGERANK

    const size =
        d3.scaleSqrt()
            .domain(
                d3.extent(
                    filtered,
                    d => d.pagerank
                )
            )
            .range([
                4,
                14
            ]);


    // The seed article is drawn larger than the PageRank scale.

    const radius =
        d => d.is_seed
            ? 16
            : size(
                d.pagerank
            );


    // MEDIANS

    const medianIndegree =
        d3.median(
            filtered,
            d => d.global_indegree
        );


    const medianViews =
        d3.median(
            filtered,
            d => d.total_views_12m
        );


    // SVG

    const svg =
        d3.select("#scatter")
            .append("svg")

            .attr(
                "viewBox",
                [
                    0,
                    0,
                    scatterWidth,
                    scatterHeight
                ]
            );


    const plot =
        svg.append("g")

            .attr(
                "transform",
                `translate(
                    ${scatterMargin.left},
                    ${scatterMargin.top}
                )`
            );


    // GRID

    plot.append("g")
        .attr(
            "class",
            "grid"
        )
        .attr(
            "transform",
            `translate(
                0,
                ${innerHeight}
            )`
        )
        .call(
            d3.axisBottom(x)
                .ticks(8)
                .tickSize(
                    -innerHeight
                )
                .tickFormat("")
        );


    plot.append("g")
        .attr(
            "class",
            "grid"
        )
        .call(
            d3.axisLeft(y)
                .ticks(8)
                .tickSize(
                    -innerWidth
                )
                .tickFormat("")
        );


    // MEDIAN QUADRANT LINES

    plot.append("line")
        .attr(
            "class",
            "median-line"
        )
        .attr(
            "x1",
            x(medianIndegree)
        )
        .attr(
            "x2",
            x(medianIndegree)
        )
        .attr(
            "y1",
            0
        )
        .attr(
            "y2",
            innerHeight
        );


    plot.append("line")
        .attr(
            "class",
            "median-line"
        )
        .attr(
            "x1",
            0
        )
        .attr(
            "x2",
            innerWidth
        )
        .attr(
            "y1",
            y(medianViews)
        )
        .attr(
            "y2",
            y(medianViews)
        );


    // QUADRANT LABELS

    plot.append("text")
        .attr(
            "class",
            "quadrant-label"
        )
        .attr(
            "x",
            innerWidth - 12
        )
        .attr(
            "y",
            20
        )
        .attr(
            "text-anchor",
            "end"
        )
        .text(
            "High structure / High attention"
        );


    plot.append("text")
        .attr(
            "class",
            "quadrant-label"
        )
        .attr(
            "x",
            12
        )
        .attr(
            "y",
            20
        )
        .text(
            "Lower structure / High attention"
        );


    plot.append("text")
        .attr(
            "class",
            "quadrant-label"
        )
        .attr(
            "x",
            innerWidth - 12
        )
        .attr(
            "y",
            innerHeight - 12
        )
        .attr(
            "text-anchor",
            "end"
        )
        .text(
            "High structure / Lower attention"
        );


    plot.append("text")
        .attr(
            "class",
            "quadrant-label"
        )
        .attr(
            "x",
            12
        )
        .attr(
            "y",
            innerHeight - 12
        )
        .text(
            "Lower structure / Lower attention"
        );


    // POINTS

    const points =
        plot.append("g")
            .selectAll("circle")
            .data(filtered)
            .join("circle")
            .attr(
                "class",
                "scatter-point"
            )
            .attr(
                "cx",
                d =>
                    x(
                        d.global_indegree
                    )
            )
            .attr(
                "cy",
                d =>
                    y(
                        d.total_views_12m
                    )
            )
            .attr(
                "r",
                radius
            )
            .attr(
                "fill",
                d => {

                    if (d.is_seed) {
                        return "#111";
                    }

                    return (
                        d3.interpolateRainbow((d.community * 0.61803398875) % 1)
                    );
                }
            );


    // TOOLTIP

    points
        .append("title")
        .text(d => {
            return (
                d.title
                + "\n12-month pageviews: "
                + d3.format(",")(
                    d.total_views_12m
                )
                + "\nGlobal in-degree: "
                + d3.format(",")(
                    d.global_indegree
                )
                + "\nLocal PageRank: "
                + d3.format(".4f")(
                    d.pagerank
                )
                + "\nCommunity: "
                + (d.community + 1)
            );

        });


    // LABEL IMPORTANT / INTERESTING POINTS
    // Keep labels intentionally limited: the top PageRank
    // articles among the points currently shown.

    const labelLayer =
        plot.append("g");


    // HIGHLIGHT
    // Ring and label for the article selected in any view.

    const highlight =
        plot.append("g")
            .attr(
                "class",
                "scatter-highlight"
            )
            .attr(
                "display",
                "none"
            );

    highlight.append("circle");

    highlight.append("text")
        .attr(
            "class",
            "scatter-label scatter-highlight-label"
        );



    // AXES

    const xAxis =
        d3.axisBottom(x)
            .ticks(
                8,
                "~s"
            );


    const yAxis =
        d3.axisLeft(y)
            .ticks(
                8,
                "~s"
            );


    plot.append("g")
        .attr(
            "class",
            "scatter-axis"
        )
        .attr(
            "transform",
            `translate(
                0,
                ${innerHeight}
            )`
        )
        .call(xAxis);


    plot.append("g")
        .attr(
            "class",
            "scatter-axis"
        )
        .call(yAxis);


    // AXIS LABELS

    svg.append("text")
        .attr(
            "class",
            "axis-label"
        )
        .attr(
            "x",
            scatterMargin.left
            + innerWidth / 2
        )
        .attr(
            "y",
            scatterHeight - 25
        )
        .attr(
            "text-anchor",
            "middle"
        )
        .text(
            "Wikipedia in-degree (log scale)"
        );


    svg.append("text")
        .attr(
            "class",
            "axis-label"
        )
        .attr(
            "transform",
            "rotate(-90)"
        )
        .attr(
            "x",
            -(
                scatterMargin.top
                + innerHeight / 2
            )
        )
        .attr(
            "y",
            28
        )
        .attr(
            "text-anchor",
            "middle"
        )
        .text(
            "Pageviews, Sep. 2025–Aug. 2026 (log scale)"
        );


    // LEGEND

    const communities =
        Array.from(
            new Set(
                filtered.map(
                    d => d.community
                )
            )
        )
        .sort(
            d3.ascending
        );


    const legend = d3.select("#scatter-legend");


    legend
        .append("span")
        .attr(
            "class",
            "legend-title"
        )
        .text(
            "Color:"
        );


    const legendItems = legend
        .selectAll(
            ".scatter-community-item"
        )
        .data(
            communities
        )
        .join("span")
        .attr(
            "class",
            "community-legend-item"
        )
        .html(
            d => `
                <span
                    class="community-color"
                    style="
                        background:
                        ${
                            d3.interpolateRainbow((d * 0.61803398875) % 1)
                        };
                    "
                ></span>

                Community ${d + 1}
            `
        );

    legend
        .append("span")
        .attr(
            "class",
            "legend-title"
        )
        .text(
            "Size: PageRank"
        );


    // COMMUNITY FILTER

    const communityCounts =
        d3.rollup(
            filtered,
            v => v.length,
            d => d.community
        );


    const communitySelect =
        d3.select("#scatter-community");


    communitySelect
        .selectAll(
            "option.community-option"
        )
        .data(
            communities
        )
        .join("option")
        .attr(
            "class",
            "community-option"
        )
        .attr(
            "value",
            d => d
        )
        .text(d => {
            const label =
                communityInfo.find(
                    c => c.id === d
                )?.label;

            return (
                `Community ${d + 1}`
                + (label ? ` · ${label}` : "")
                + ` (${d3.format(",")(communityCounts.get(d))})`
            );
        });


    // FILTER + SELECTION STATE
    // The filter hides other communities; the selection is
    // shared with the other views through article IDs.

    let activeCommunity = null;

    let selectedId =
        window.knowledge?.selectedId ?? null;


    function update() {

        const visible =
            d => activeCommunity == null
                || d.community === activeCommunity;

        const selected =
            filtered.find(
                d => d.article_id === selectedId
            );

        const showSelected =
            selected != null
            && visible(selected);


        points
            .classed(
                "is-hidden",
                d => !visible(d)
            )
            .classed(
                "is-dimmed",
                d => showSelected
                    && visible(d)
                    && d !== selected
            )
            .classed(
                "is-selected",
                d => showSelected
                    && d === selected
            );

        if (showSelected) {
            points
                .filter(
                    d => d === selected
                )
                .raise();
        }


        legendItems.classed(
            "is-muted",
            d => activeCommunity != null
                && d !== activeCommunity
        );


        const labelled =
            filtered
                .filter(
                    d => visible(d)
                        && d !== selected
                )
                .sort(
                    (a, b) => b.pagerank - a.pagerank
                )
                .slice(0, 15);

        labelLayer
            .selectAll("text")
            .data(
                labelled,
                d => d.article_id
            )
            .join("text")
            .attr(
                "class",
                "scatter-label"
            )
            .attr(
                "x",
                d =>
                    x(
                        d.global_indegree
                    )
                    + radius(d)
                    + 5
            )
            .attr(
                "y",
                d =>
                    y(
                        d.total_views_12m
                    )
                    - 4
            )
            .text(
                d => d.title
            );


        highlight.attr(
            "display",
            showSelected ? null : "none"
        );

        if (showSelected) {

            const cx = x(selected.global_indegree);
            const cy = y(selected.total_views_12m);
            const r = radius(selected);

            // Flip the label to the left near the right edge.
            const flip = cx > innerWidth * 0.75;

            highlight.select("circle")
                .attr("cx", cx)
                .attr("cy", cy)
                .attr("r", r + 6);

            highlight.select("text")
                .attr("x", flip ? cx - r - 10 : cx + r + 10)
                .attr("y", cy - r - 6)
                .attr("text-anchor", flip ? "end" : "start")
                .text(selected.title);
        }


        const shownText =
            activeCommunity == null
                ? `Showing all ${d3.format(",")(filtered.length)} articles.`
                : `Showing ${d3.format(",")(communityCounts.get(activeCommunity))} of ${d3.format(",")(filtered.length)} articles (Community ${activeCommunity + 1}).`;

        const node =
            window.knowledge?.get(selectedId);

        let selectionText;

        if (selectedId == null) {
            selectionText = "Select an article in any view to highlight it here.";
        } else if (!selected) {
            selectionText = `${node?.title ?? "The selected article"} is not plotted because it lacks a complete 12-month pageview record.`;
        } else if (!showSelected) {
            selectionText = `${selected.title} is in Community ${selected.community + 1}, which the filter is hiding.`;
        } else {
            selectionText = `${selected.title} is highlighted in orange.`;
        }

        d3.select("#scatter-status")
            .text(
                `${shownText} ${selectionText}`
            );
    }


    communitySelect.on(
        "change",
        event => {
            const value = event.target.value;
            activeCommunity = value === "" ? null : +value;
            update();
        }
    );


    // Resetting the highlight clears the shared selection,
    // so the other views deselect the article too.
    d3.select("#scatter-reset")
        .on(
            "click",
            () => window.knowledge?.select(null)
        );


    // Clicking a point selects it across all views.
    points.on(
        "click",
        (event, d) =>
            window.knowledge?.get(d.article_id)
            && window.knowledge.select(d.article_id)
    );


    window.addEventListener(
        "knowledge:selection",
        event => {
            selectedId = event.detail.articleId;
            update();
        }
    );


    update();
})


.catch(error => {
    console.error(
        "Error loading scatterplot data:",
        error
    );
    d3.select("#scatter")
        .append("p")
        .text(
            "Unable to load the scatterplot data."
        );
});