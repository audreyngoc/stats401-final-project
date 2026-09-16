const networkWidth = 1200;
const networkHeight = 800;


// Community colors
const communityColors = [
    "#5B8FF9",
    "#61DDAA",
    "#F6BD16"
];


d3.json("data/ai_graph.json")
    .then(data => {

        // =================================================
        // COPY DATA
        // =================================================

        const nodes =
            data.nodes.map(d => ({
                ...d
            }));


        const links =
            data.links.map(d => ({
                ...d
            }));


        // =================================================
        // NODE SIZE
        // =================================================

        const pageRankExtent =
            d3.extent(
                nodes,
                d => d.pagerank
            );


        const radiusScale =
            d3.scaleSqrt()
                .domain(pageRankExtent)
                .range([4, 14]);


        function nodeRadius(d) {

            if (d.is_seed) {
                return 17;
            }

            return radiusScale(
                d.pagerank
            );
        }


        // =================================================
        // BUILD FORCE SIMULATION
        //
        // IMPORTANT:
        // We calculate the layout up front instead of
        // animating it in the browser.
        // =================================================

        const simulation =
            d3.forceSimulation(nodes)

                .force(
                    "link",
                    d3.forceLink(links)
                        .id(
                            d => d.article_id
                        )
                        .distance(90)
                        .strength(0.035)
                )

                .force(
                    "charge",
                    d3.forceManyBody()
                        .strength(-260)
                )

                .force(
                    "center",
                    d3.forceCenter(
                        networkWidth / 2,
                        networkHeight / 2
                    )
                )

                .force(
                    "collision",
                    d3.forceCollide()
                        .radius(
                            d =>
                                nodeRadius(d)
                                + 5
                        )
                        .strength(0.8)
                )

                .stop();


        // -------------------------------------------------
        // Calculate final positions immediately.
        //
        // No animated simulation = much less lag.
        // -------------------------------------------------

        for (
            let i = 0;
            i < 350;
            i++
        ) {
            simulation.tick();
        }


        // =================================================
        // SVG
        // =================================================

        const svg =
            d3.select("#network")
                .append("svg")

                .attr(
                    "viewBox",
                    [
                        0,
                        0,
                        networkWidth,
                        networkHeight
                    ]
                );


        const graphLayer =
            svg.append("g");


        // =================================================
        // LINKS
        // =================================================

        graphLayer
            .append("g")
            .selectAll("line")

            .data(links)

            .join("line")

            .attr(
                "class",
                "network-link"
            )

            .attr(
                "x1",
                d => d.source.x
            )

            .attr(
                "y1",
                d => d.source.y
            )

            .attr(
                "x2",
                d => d.target.x
            )

            .attr(
                "y2",
                d => d.target.y
            );


        // =================================================
        // NODES
        // =================================================

        const node =
            graphLayer
                .append("g")
                .selectAll("circle")

                .data(nodes)

                .join("circle")

                .attr(
                    "class",
                    "network-node"
                )

                .attr(
                    "cx",
                    d => d.x
                )

                .attr(
                    "cy",
                    d => d.y
                )

                .attr(
                    "r",
                    d => nodeRadius(d)
                )

                .attr(
                    "fill",
                    d => {

                        if (d.is_seed) {
                            return "#111";
                        }

                        return communityColors[
                            d.community %
                            communityColors.length
                        ];
                    }
                );


        // =================================================
        // LABELS
        //
        // Only show:
        //   - seed
        //   - first-level concepts
        //
        // This makes the static overview readable.
        // =================================================

        const labelledNodes =
            nodes.filter(
                d =>
                    d.is_seed
                    || d.depth === 1
            );


        graphLayer
            .append("g")
            .selectAll("text")

            .data(labelledNodes)

            .join("text")

            .attr(
                "class",
                d => {

                    if (d.is_seed) {
                        return (
                            "network-label " +
                            "seed-label"
                        );
                    }

                    return (
                        "network-label " +
                        "first-level-label"
                    );
                }
            )

            .attr(
                "x",
                d =>
                    d.x
                    + nodeRadius(d)
                    + 6
            )

            .attr(
                "y",
                d => d.y
            )

            .attr(
                "dy",
                "0.35em"
            )

            .text(
                d => d.title
            );


        // =================================================
        // TOOLTIP
        // =================================================

        node
            .append("title")
            .text(d => {

                return (
                    d.title
                    + "\nCommunity: "
                    + (d.community + 1)

                    + "\nPageRank: "
                    + d3.format(".4f")(
                        d.pagerank
                    )

                    + "\nLocal in-degree: "
                    + d.local_indegree

                    + "\nLocal out-degree: "
                    + d.local_outdegree

                    + "\nGlobal Wikipedia in-degree: "
                    + (
                        d.global_indegree == null
                            ? "N/A"
                            : d3.format(",")(
                                d.global_indegree
                            )
                    )
                );

            });


        // =================================================
        // COMMUNITY LEGEND
        // =================================================

        const communities =
            Array.from(
                new Set(
                    nodes.map(
                        d => d.community
                    )
                )
            )
            .sort(
                d3.ascending
            );


        d3.select(
            "#community-legend"
        )

            .selectAll(
                ".community-legend-item"
            )

            .data(communities)

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
                                communityColors[
                                    d %
                                    communityColors.length
                                ]
                            };
                        "
                    ></span>

                    Community ${d + 1}
                `
            );

    })


    .catch(error => {

        console.error(
            "Error loading network data:",
            error
        );


        d3.select("#network")
            .append("p")
            .text(
                "Unable to load ai_graph.json."
            );

    });