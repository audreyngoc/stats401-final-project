const treeWidth = 1500;

const treeMargin = {
    top: 40,
    right: 360,
    bottom: 40,
    left: 180
};


// Vertical distance between adjacent nodes
const dx = 23;


// Horizontal distance between hierarchy levels
const dy = 340;


// One color per first-level AI branch
const branchColors = d3.schemeTableau10;


d3.json("data/ai_tree.json")
    .then(data => {

        // ---------------------------------------------
        // Convert JSON into a D3 hierarchy
        // ---------------------------------------------

        const root =
            d3.hierarchy(data);


        // ---------------------------------------------
        // Give every first-level branch its own
        // branch number.
        //
        // All descendants inherit that branch number.
        // ---------------------------------------------

        if (root.children) {

            root.children.forEach(
                (branch, index) => {

                    branch.each(d => {
                        d.branchIndex = index;
                    });

                }
            );
        }


        root.branchIndex = -1;

        // ---------------------------------------------
        // Build branch-color legend
        // ---------------------------------------------

        const branchLegend =
            d3.select("#branch-legend");


        branchLegend
            .selectAll(".branch-legend-item")
            .data(root.children || [])
            .join("span")
            .attr(
                "class",
                "branch-legend-item"
            )
            .html(
                (d, i) => `
                    <span
                        class="branch-color"
                        style="
                            background:
                            ${branchColors[i]};
                        "
                    ></span>
        
                    ${d.data.name}
                `
            );
        
        // ---------------------------------------------
        // Create tree layout
        // ---------------------------------------------

        const treeLayout =
            d3.tree()
                .nodeSize([
                    dx,
                    dy
                ]);


        treeLayout(root);


        // ---------------------------------------------
        // Determine actual vertical extent
        // ---------------------------------------------

        let x0 = Infinity;
        let x1 = -Infinity;


        root.each(d => {

            if (d.x < x0) {
                x0 = d.x;
            }

            if (d.x > x1) {
                x1 = d.x;
            }

        });


        const treeHeight =
            x1
            - x0
            + treeMargin.top
            + treeMargin.bottom;


        // ---------------------------------------------
        // SVG
        // ---------------------------------------------

        const svg =
            d3.select("#tree")
                .append("svg")
                .attr(
                    "width",
                    treeWidth
                )
                .attr(
                    "height",
                    treeHeight
                )
                .attr(
                    "viewBox",
                    [
                        0,
                        0,
                        treeWidth,
                        treeHeight
                    ]
                );


        const chart =
            svg.append("g")
                .attr(
                    "transform",
                    `translate(
                        ${treeMargin.left},
                        ${
                            treeMargin.top
                            - x0
                        }
                    )`
                );


        // ---------------------------------------------
        // Links
        // ---------------------------------------------

        const linkGenerator =
            d3.linkHorizontal()
                .x(d => d.y)
                .y(d => d.x);


        chart.append("g")
            .selectAll("path")
            .data(
                root.links()
            )
            .join("path")
            .attr(
                "class",
                "tree-link"
            )
            .attr(
                "d",
                linkGenerator
            )
            .attr(
                "stroke",
                d => {

                    if (
                        d.target.branchIndex
                        >= 0
                    ) {
                        return branchColors[
                            d.target.branchIndex
                        ];
                    }

                    return "#999";
                }
            );


        // ---------------------------------------------
        // Nodes
        // ---------------------------------------------

        const node =
            chart.append("g")
                .selectAll("g")
                .data(
                    root.descendants()
                )
                .join("g")
                .attr(
                    "class",
                    d =>
                        `tree-node depth-${d.depth}`
                )
                .attr(
                    "transform",
                    d =>
                        `translate(
                            ${d.y},
                            ${d.x}
                        )`
                );


        // ---------------------------------------------
        // Node circles
        // ---------------------------------------------

        node.append("circle")
            .attr(
                "r",
                d => {

                    if (d.depth === 0) {
                        return 8;
                    }

                    if (d.depth === 1) {
                        return 6;
                    }

                    return 4;
                }
            )
            .attr(
                "fill",
                d => {

                    if (d.depth === 0) {
                        return "#111";
                    }

                    return branchColors[
                        d.branchIndex
                    ];
                }
            );


        // ---------------------------------------------
        // Labels
        // ---------------------------------------------

        node.append("text")
            .attr(
                "x",
                d => {

                    if (d.depth === 0) {
                        return -14;
                    }

                    return 10;
                }
            )
            .attr(
                "text-anchor",
                d => {

                    if (d.depth === 0) {
                        return "end";
                    }

                    return "start";
                }
            )
            .text(
                d => d.data.name
            );


        // ---------------------------------------------
        // Browser tooltip
        // ---------------------------------------------

        node.append("title")
            .text(d => {

                let text =
                    d.data.name;


                if (
                    d.data.global_indegree
                    !== undefined
                ) {

                    text +=
                        "\nWikipedia in-degree: "
                        + d3.format(",")(
                            d.data.global_indegree
                        );
                }


                if (
                    d.data.relevance
                    !== undefined
                ) {

                    text +=
                        "\nAI relevance: "
                        + d3.format(".3f")(
                            d.data.relevance
                        );
                }


                if (
                    d.data.parent_similarity
                    !== undefined
                ) {

                    text +=
                        "\nParent similarity: "
                        + d3.format(".3f")(
                            d.data.parent_similarity
                        );
                }


                return text;
            });

    })

    .catch(error => {

        console.error(
            "Error loading tree data:",
            error
        );

        d3.select("#tree")
            .append("p")
            .text(
                "Unable to load ai_tree.json."
            );

    });