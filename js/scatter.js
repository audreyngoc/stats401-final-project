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


d3.csv(
    "data/ai_nodes_with_pageviews.csv",
    d => ({
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
)

.then(data => {

    // =====================================================
    // Remove invalid values
    //
    // Log scales cannot display 0.
    // =====================================================

    const filtered =
        data.filter(
            d =>
                d.global_indegree > 0
                &&
                d.total_views_12m > 0
        );


    // =====================================================
    // INNER PLOT DIMENSIONS
    // =====================================================

    const innerWidth =
        scatterWidth
        - scatterMargin.left
        - scatterMargin.right;


    const innerHeight =
        scatterHeight
        - scatterMargin.top
        - scatterMargin.bottom;


    // =====================================================
    // LOG SCALES
    // =====================================================

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


    // =====================================================
    // POINT SIZE = PAGERANK
    // =====================================================

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


    // =====================================================
    // MEDIANS
    // =====================================================

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


    // =====================================================
    // SVG
    // =====================================================

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


    // =====================================================
    // GRID
    // =====================================================

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


    // =====================================================
    // MEDIAN QUADRANT LINES
    // =====================================================

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


    // =====================================================
    // QUADRANT LABELS
    // =====================================================

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


    // =====================================================
    // POINTS
    // =====================================================

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
                d => {

                    if (d.is_seed) {
                        return 16;
                    }

                    return size(
                        d.pagerank
                    );
                }
            )

            .attr(
                "fill",
                d => {

                    if (d.is_seed) {
                        return "#111";
                    }

                    return (
                        scatterCommunityColors[
                            d.community
                            %
                            scatterCommunityColors.length
                        ]
                    );
                }
            );


    // =====================================================
    // TOOLTIP
    // =====================================================

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


    // =====================================================
    // LABEL IMPORTANT / INTERESTING POINTS
    //
    // Keep labels intentionally limited.
    // =====================================================

    const labelled =
        filtered.filter(
            d =>
                d.is_seed
                ||
                d.depth === 1
                ||
                d.total_views_12m
                    >= 500000
        );


    plot.append("g")
        .selectAll("text")

        .data(labelled)

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
                + size(
                    d.pagerank
                )
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


    // =====================================================
    // AXES
    // =====================================================

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


    // =====================================================
    // AXIS LABELS
    // =====================================================

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


    // =====================================================
    // LEGEND
    // =====================================================

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


    const legend =
        d3.select(
            "#scatter-legend"
        );


    legend
        .append("span")
        .attr(
            "class",
            "legend-title"
        )
        .text(
            "Color:"
        );


    legend
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
                            scatterCommunityColors[
                                d %
                                scatterCommunityColors.length
                            ]
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

})


.catch(error => {

    console.error(
        "Error loading scatterplot data:",
        error
    );


    d3.select("#scatter")
        .append("p")
        .text(
            "Unable to load ai_nodes_with_pageviews.csv."
        );

});