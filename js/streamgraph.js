
(function () {
  "use strict";

  const container = d3.select("#streamgraph");
  if (container.empty()) return;

  const parseMonth = d3.timeParse("%Y-%m");
  const formatMonth = d3.timeFormat("%B %Y");
  const formatViews = d3.format(",");
  const margin = { top: 32, right: 28, bottom: 54, left: 76 };
  const color = d3.scaleOrdinal(d3.schemeTableau10);

  const tooltip = d3.select("#streamgraph-tooltip");
  let timer = null;
  let progressIndex = 0;
  let isPlaying = false;
  let chartState = null;

  async function init() {
    try {
      const rows = await d3.csv("data/ai_subtopic_monthly.csv", d => ({
        topic: d.subtopic_title,
        month: parseMonth(d.month),
        views: +d.views,
        reporting: +d.articles_reporting,
        groupSize: +d.articles_in_group
      }));

      const validRows = rows.filter(d =>
        d.topic && d.month &&
        Number.isFinite(d.views) && d.views >= 0
      );
      
      const filterToggle = document.getElementById(
        "streamgraph-filter-toggle"
      );
      
      const filterContent = document.getElementById(
        "streamgraph-filter-content"
      );
      
      const filterPanel = document.getElementById("streamgraph-filter");
      
      filterToggle.addEventListener("click", () => {
        const isExpanded =
            filterToggle.getAttribute("aria-expanded") === "true";

        filterToggle.setAttribute("aria-expanded", String(!isExpanded));
        filterContent.hidden = isExpanded;
        filterPanel.classList.toggle("is-expanded", !isExpanded);
        });

      const topics = [...new Set(validRows.map(d => d.topic))].sort();
      const months = [...new Map(
        validRows.map(d => [+d.month, d.month])
      ).values()].sort((a, b) => a - b);

      progressIndex = months.length - 1;

      if (!topics.length || !months.length) {
        throw new Error("No valid monthly pageview data was found.");
      }

      const byMonth = d3.group(validRows, d => +d.month);

      const monthly = months.map(month => {
        const row = { month };
        topics.forEach(topic => {
          row[topic] = d3.sum(
            (byMonth.get(+month) || [])
              .filter(d => d.topic === topic),
            d => d.views
          );
        });
        return row;
      });

      const controls = d3.select("#streamgraph-topics");
      controls.selectAll("*").remove();

      let selected = new Set(topics);

      controls.selectAll("label")
        .data(topics)
        .join("label")
        .attr("class", "streamgraph-topic-option")
        .each(function (topic) {
          const label = d3.select(this);

          label.append("input")
            .attr("type", "checkbox")
            .property("checked", true)
            .on("change", function () {
              selected.has(topic)
                ? selected.delete(topic)
                : selected.add(topic);
              render();
            });

          label.append("span").text(topic);
        });

      d3.select("#streamgraph-select-all").on("click", () => {
        selected = new Set(topics);
        controls.selectAll("input").property("checked", true);
        render();
      });

      d3.select("#streamgraph-clear").on("click", () => {
        selected.clear();
        controls.selectAll("input").property("checked", false);
        render();
      });

      function stopPlayback() {
        if (timer !== null) {
          clearInterval(timer);
          timer = null;
        }
        isPlaying = false;
        d3.select("#streamgraph-play").text("▶ Play");
      }

      function updateProgress(index) {
        if (!chartState) return;

        progressIndex = Math.max(
          0, Math.min(index, months.length - 1)
        );

        const { x, plot, innerHeight, innerWidth } = chartState;
        const month = months[progressIndex];
        const xPos = x(month);

        // Reveal the chart progressively from left to right.
        plot.select("#streamgraph-reveal")
          .attr("width", Math.max(0, xPos));

        plot.select("#streamgraph-progress-line")
          .attr("x1", xPos)
          .attr("x2", xPos)
          .attr("y1", 0)
          .attr("y2", innerHeight)
          .style("display", null);

        d3.select("#streamgraph-date")
          .text(formatMonth(month));

        const row = monthly[progressIndex];
        const chosen = topics.filter(t => selected.has(t));
        const values = chosen
          .map(topic => ({ topic, views: row[topic] }))
          .sort((a, b) => b.views - a.views);

        d3.select("#streamgraph-month-summary").html(
          `<strong>${formatMonth(month)}</strong>` +
          `<div>${formatViews(d3.sum(values, d => d.views))} ` +
          `pageviews across selected topics</div>` +
          `<div class="streamgraph-top-topics">` +
          values.slice(0, 3).map(d =>
            `<span><i style="background:${color(d.topic)}"></i>` +
            `${d.topic}: ${formatViews(d.views)}</span>`
          ).join("") +
          `</div>`
        );

        d3.select("#streamgraph-timeline")
          .property("value", progressIndex);

        d3.select("#streamgraph-timeline-label")
          .text(`${progressIndex + 1} / ${months.length}`);

        // The last month ends playback automatically.
        if (progressIndex === months.length - 1 && isPlaying) {
          stopPlayback();
        }
      }

      d3.select("#streamgraph-play").on("click", () => {
        if (isPlaying) {
          stopPlayback();
          return;
        }

        // Start over if playback has reached the final month.
        if (progressIndex >= months.length - 1) {
          updateProgress(0);
        }

        isPlaying = true;
        d3.select("#streamgraph-play").text("Ⅱ Pause");

        timer = setInterval(() => {
          updateProgress(progressIndex + 1);
        }, 600);
      });

      d3.select("#streamgraph-reset").on("click", () => {
        stopPlayback();
        updateProgress(0);
      });

      d3.select("#streamgraph-timeline")
        .attr("max", months.length - 1)
        .on("input", function () {
          stopPlayback();
          updateProgress(+this.value);
        });

      function render() {
        stopPlayback();
        container.selectAll("*").remove();
        d3.select("#streamgraph-legend").selectAll("*").remove();

        const chosen = topics.filter(t => selected.has(t));

        d3.select("#streamgraph-status").text(
          `${chosen.length} of ${topics.length} topics selected · ` +
          `${months.length} months`
        );

        d3.select("#streamgraph-selected-count").text(
        `${chosen.length} of ${topics.length} selected`
        );

        if (!chosen.length) {
          container.append("p")
            .attr("class", "network-note")
            .text("Select at least one topic to display the streamgraph.");
          chartState = null;
          return;
        }

        const width = Math.max(
          320,
          container.node().getBoundingClientRect().width || 800
        );
        const height = 460;
        const innerWidth = width - margin.left - margin.right;
        const innerHeight = height - margin.top - margin.bottom;

        const svg = container.append("svg")
          .attr("viewBox", `0 0 ${width} ${height}`)
          .attr("role", "img")
          .attr(
            "aria-label",
            "Interactive monthly Wikipedia pageview streamgraph"
          );

        const x = d3.scaleTime()
          .domain(d3.extent(months))
          .range([0, innerWidth]);

        const layers = d3.stack()
          .keys(chosen)
          .value((d, key) => d[key])
          .offset(d3.stackOffsetWiggle)
          .order(d3.stackOrderInsideOut)(monthly);

        const yExtent = [
          d3.min(layers, layer => d3.min(layer, d => d[0])),
          d3.max(layers, layer => d3.max(layer, d => d[1]))
        ];

        const y = d3.scaleLinear()
          .domain(yExtent)
          .nice(5)
          .range([innerHeight, 0]);

        const area = d3.area()
          .x(d => x(d.data.month))
          .y0(d => y(d[0]))
          .y1(d => y(d[1]))
          .curve(d3.curveCatmullRom.alpha(0.5));

        const plot = svg.append("g")
          .attr("transform",
            `translate(${margin.left},${margin.top})`);

        // Axes and subtle horizontal gridlines.
        plot.append("g")
          .attr("class", "streamgraph-grid")
          .call(d3.axisLeft(y).ticks(5)
            .tickSize(-innerWidth).tickFormat(""));

        plot.append("g")
            .attr("class", "streamgraph-y-axis")
            .call(d3.axisLeft(y).ticks(5).tickFormat(() => ""));

        plot.append("text")
          .attr("class", "streamgraph-axis-title")
          .attr("transform", "rotate(-90)")
          .attr("x", -innerHeight / 2)
          .attr("y", -56)
          .attr("text-anchor", "middle")
          .text("Vertical position of topic bands (layout only)");

        plot.append("g")
          .attr("transform", `translate(0,${innerHeight})`)
          .call(d3.axisBottom(x)
            .tickValues(months)
            .tickFormat(d3.timeFormat("%b %y")));

        plot.append("text")
          .attr("class", "streamgraph-axis-title")
          .attr("x", innerWidth / 2)
          .attr("y", innerHeight + 42)
          .attr("text-anchor", "middle")
          .text("Month of Wikipedia pageview activity");

        // Clip path for the playback reveal.
        const clipId = "streamgraph-reveal-clip";
        plot.append("defs")
          .append("clipPath")
          .attr("id", clipId)
          .append("rect")
          .attr("id", "streamgraph-reveal")
          .attr("x", 0)
          .attr("y", -4)
          .attr("height", innerHeight + 8)
          .attr("width", innerWidth);

        const chartContent = plot.append("g")
          .attr("clip-path", `url(#${clipId})`);

        chartContent.selectAll(".stream-layer")
          .data(layers, d => d.key)
          .join("path")
          .attr("class", "stream-layer")
          .attr("fill", d => color(d.key))
          .attr("d", area);

        // Put topic names directly on sufficiently thick bands.
        const labelDate = months[Math.floor(months.length / 2)];
        const labelX = x(labelDate);

        chartContent.selectAll(".stream-label")
          .data(layers)
          .join("text")
          .attr("class", "stream-label")
          .attr("x", labelX)
          .attr("y", layer => {
            const point = layer.find(d =>
              +d.data.month === +labelDate
            );
            return point ? y((point[0] + point[1]) / 2) : 0;
          })
          .attr("text-anchor", "middle")
          .style("display", layer => {
            const point = layer.find(d =>
              +d.data.month === +labelDate
            );
            return point && Math.abs(y(point[0]) - y(point[1])) > 23
              ? null : "none";
          })
          .text(layer => layer.key)
          .each(function () {
            const node = d3.select(this);
            const length = this.getComputedTextLength();
            if (length > 150) node.attr("font-size", "10px");
          });

        // Crosshair and hover marker.
        const crosshair = plot.append("line")
          .attr("class", "streamgraph-crosshair")
          .attr("y1", 0)
          .attr("y2", innerHeight)
          .style("display", "none");

        plot.append("line")
          .attr("id", "streamgraph-progress-line")
          .attr("class", "streamgraph-progress-line")
          .attr("y1", 0)
          .attr("y2", innerHeight)
          .style("display", "none");

        const overlay = plot.append("rect")
          .attr("class", "streamgraph-hover-overlay")
          .attr("width", innerWidth)
          .attr("height", innerHeight)
          .on("mousemove", function (event) {
            const [mx] = d3.pointer(event, this);
            const hoveredMonth = x.invert(mx);
            const i = d3.bisector(d => d).center(months, hoveredMonth);
            const month = months[i];
            const row = monthly[i];

            crosshair
              .attr("x1", x(month))
              .attr("x2", x(month))
              .style("display", null);

            
            const rankedTopics = chosen
            .map(topic => ({
                topic,
                views: row[topic]
            }))
            .sort((a, b) => b.views - a.views);

            tooltip
            .style("display", "block")
            .html(
                `<div class="streamgraph-tooltip-date">${formatMonth(month)}</div>` +
                `<div class="streamgraph-tooltip-heading">Pageviews by topic</div>` +
                rankedTopics.map((d, i) =>
                `<div class="streamgraph-tooltip-row">` +
                    `<span class="streamgraph-tooltip-topic">` +
                    `<span class="streamgraph-tooltip-rank">${i + 1}.</span>` +
                    `<strong>${d.topic}</strong>` +
                    `</span>` +
                    `<span class="streamgraph-tooltip-value">${formatViews(d.views)}</span>` +
                `</div>`
                ).join("")
            );

            d3.select("#streamgraph-chart-wrap")
              .on("mousemove.position", function (e) {
                const [px, py] = d3.pointer(e, this);
                tooltip
                  .style("left", `${Math.min(
                    Math.max(8, px + 12),
                    this.clientWidth - 270
                  )}px`)
                  .style("top", `${Math.max(8, py + 8)}px`);
              });
          })
          .on("mouseleave", () => {
            crosshair.style("display", "none");
            tooltip.style("display", "none");
          });

        // Keep the overlay above paths but allow mouse interaction.
        chartState = { x, plot, innerHeight, innerWidth };
        updateProgress(Math.min(progressIndex, months.length - 1));

        const legend = d3.select("#streamgraph-legend");
        legend.selectAll(".streamgraph-legend-item")
          .data(chosen)
          .join("span")
          .attr("class", "streamgraph-legend-item")
          .html(topic =>
            `<span class="streamgraph-swatch" ` +
            `style="background:${color(topic)}"></span>` +
            `<span>${topic}</span>`
          );

        d3.select("#streamgraph-method").text(
          "Each band represents monthly pageviews for a topic. " +
          "Band thickness indicates its value at that month. " +
          "The wiggle baseline shifts the layers to reduce visual " +
          "undulation, so y-axis positions are relative, not absolute."
        );

        
        d3.select("#streamgraph-annotation").html(
        "<strong>How to read this chart</strong>" +
        "<p>Each colored band represents a computing topic. " +
        "The horizontal axis shows the month when Wikipedia pageviews " +
        "occurred. A thicker band means that the topic received more " +
        "pageviews in that month.</p>" +
        "<p>The vertical arrangement of bands is a visual layout " +
        "designed to make changes in popularity easier to follow. " +
        "A band's vertical position does not indicate how popular " +
        "the topic is.</p>" +
        "<p><strong>Research question:</strong> How does attention " +
        "to computing concepts change over time? Wikipedia pageviews " +
        "measure readership on Wikipedia, not all forms of public " +
        "interest or expertise.</p>"
        );
      }

      render();

      window.addEventListener("resize", () => {
        stopPlayback();
        render();
      });
    } catch (error) {
      console.error("Streamgraph failed to load:", error);
      d3.select("#streamgraph-status").text(
        "Could not load the pageview data. Check the local server and CSV path."
      );
    }
  }

  init();
})();
