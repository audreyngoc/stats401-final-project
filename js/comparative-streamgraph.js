(function () {
  "use strict";

  const container = d3.select("#comparative-streamgraph");
  if (container.empty()) return;

  const legend = d3.select("#comparison-legend");
  const status = d3.select("#comparison-month-status");
  const tooltip = d3.select("#comparison-tooltip");
  const chartCard = d3.select(".comparison-chart-card");
  const resetButton = d3.select("#comparison-reset");

  // Keep the tooltip outside the SVG so chart redraws do not remove it.
  if (
    !tooltip.empty() &&
    !chartCard.empty() &&
    tooltip.node().parentNode !== chartCard.node()
  ) {
    chartCard.node().appendChild(tooltip.node());
  }

  const parseMonth = d3.timeParse("%Y-%m");
  const formatMonth = d3.timeFormat("%B %Y");
  const formatTimelineMonth = d3.timeFormat("%b %y");
  const formatNumber = d3.format(",");
  const formatPercent = d3.format(".1%");

  const topicOrder = [
    "Artificial general intelligence",
    "Artificial intelligence in video games",
    "Cognition",
    "Decision-making",
    "Generative AI",
    "Knowledge representation and reasoning",
    "Machine learning",
    "Natural language processing",
    "Operations research",
    "Problem solving"
  ];

  const topicShortNames = {
    "Artificial general intelligence": "AGI",
    "Artificial intelligence in video games": "AI in games",
    "Cognition": "Cognition",
    "Decision-making": "Decision-making",
    "Generative AI": "Generative AI",
    "Knowledge representation and reasoning": "Knowledge reasoning",
    "Machine learning": "Machine learning",
    "Natural language processing": "NLP",
    "Operations research": "Operations research",
    "Problem solving": "Problem solving"
  };

  const colors = [
    "#557CA8",
    "#D78B4C",
    "#78A99A",
    "#BE737C",
    "#9180B8",
    "#B7A45E",
    "#4D9DB8",
    "#CF8DB5",
    "#89985C",
    "#929292"
  ];

  const color = d3.scaleOrdinal()
    .domain(topicOrder)
    .range(colors);

  const months = d3.timeMonth.range(
    parseMonth("2025-09"),
    d3.timeMonth.offset(parseMonth("2026-08"), 1)
  );

  const selectedTopics = new Set();

  let chartData = [];
  let topicLayers = [];
  let svg;
  let dimensions;
  let resizeObserver;

  const panelLabelHeight = 20;

  async function init() {
    try {
      const [wikiRows, redditRows] = await Promise.all([
        d3.csv("data/ai_subtopic_monthly.csv", d => ({
          topic: d.subtopic_title,
          month: d.month,
          views: +d.views
        })),

        d3.csv("data/reddit_subtopic_monthly.csv", d => ({
          topic: d.subtopic_title,
          month: d.month,
          posts: +d.posts,
          collected: +d.reddit_posts_in_month,
          classified: +d.classified_posts_in_month,
          assignments: +d.topic_assignments_in_month
        }))
      ]);

      const wiki = wikiRows.filter(d =>
        d.topic &&
        parseMonth(d.month) &&
        Number.isFinite(d.views) &&
        d.views >= 0
      );

      const reddit = redditRows.filter(d =>
        d.topic &&
        parseMonth(d.month) &&
        Number.isFinite(d.posts) &&
        d.posts >= 0
      );

      const availableTopics = new Set([
        ...wiki.map(d => d.topic),
        ...reddit.map(d => d.topic)
      ]);

      topicLayers = topicOrder.filter(topic =>
        availableTopics.has(topic)
      );

      if (!topicLayers.length || !wiki.length || !reddit.length) {
        throw new Error("The monthly topic data is empty.");
      }

      const wikiByKey = new Map(
        wiki.map(d => [`${d.month}|${d.topic}`, d])
      );

      const redditByKey = new Map(
        reddit.map(d => [`${d.month}|${d.topic}`, d])
      );

      const wikiByMonth = d3.group(wiki, d => d.month);
      const redditByMonth = d3.group(reddit, d => d.month);

      chartData = months.map(monthDate => {
        const month = d3.timeFormat("%Y-%m")(monthDate);
        const wikiMonth = wikiByMonth.get(month) || [];
        const redditMonth = redditByMonth.get(month) || [];

        const wikiTotal = d3.sum(wikiMonth, d => d.views);

        const redditCollected = redditMonth.length
          ? redditMonth[0].collected
          : 0;

        const redditClassified = redditMonth.length
          ? redditMonth[0].classified
          : 0;

        const redditAssignments = redditMonth.length
          ? redditMonth[0].assignments
          : 0;

        const row = {
          month: monthDate,
          monthKey: month,
          wikiTotal,
          redditCollected,
          redditClassified,
          redditAssignments,
          hasRedditEvidence: redditAssignments > 0
        };

        topicLayers.forEach(topic => {
          const wikiRow = wikiByKey.get(`${month}|${topic}`);
          const redditRow = redditByKey.get(`${month}|${topic}`);

          row[topic] = {
            wikiViews: wikiRow ? wikiRow.views : 0,
            wikiShare: wikiTotal > 0 && wikiRow
              ? wikiRow.views / wikiTotal
              : 0,
            redditPosts: redditRow ? redditRow.posts : 0,
            redditShare: redditAssignments > 0 && redditRow
              ? redditRow.posts / redditAssignments
              : 0
          };
        });

        return row;
      });

      selectedTopics.clear();
      topicLayers.forEach(topic => selectedTopics.add(topic));

      buildLegend(topicLayers);
      render();
      updateDefaultStatus();

      if ("ResizeObserver" in window) {
        resizeObserver = new ResizeObserver(() => render());
        resizeObserver.observe(container.node());
      } else {
        window.addEventListener("resize", render);
      }

      resetButton.on("click", () => {
        selectedTopics.clear();
        topicLayers.forEach(topic => selectedTopics.add(topic));

        render();
        updateDefaultStatus();
      });

    } catch (error) {
      console.error("Comparative streamgraph:", error);

      container.selectAll("svg").remove();

      container.append("p")
        .attr("class", "comparison-empty")
        .text(
          "The comparison could not be loaded. Check that both monthly " +
          "CSV files exist and that the page is served through a local web server."
        );

      status.text("Unable to load the monthly comparison data.");
    }
  }

  function buildLegend(topics) {
    legend.selectAll("*").remove();

    const buttons = legend.selectAll("button")
      .data(topics)
      .join("button")
      .attr("type", "button")
      .attr("aria-label", d => `Toggle ${d}`)
      .on("click", function (event, topic) {
        if (selectedTopics.has(topic)) {
          selectedTopics.delete(topic);
        } else {
          selectedTopics.add(topic);
        }

        render();
        updateDefaultStatus();
      });

    buttons.append("span")
      .attr("class", "comparison-swatch")
      .style("background-color", d => color(d));

    buttons.append("span")
      .text(d => d);

    updateHighlight();
  }

  function getSelectedWikiTotal(d) {
    return d3.sum(
      Array.from(selectedTopics),
      topic => d[topic].wikiViews
    );
  }

  function getSelectedRedditTotal(d) {
    return d3.sum(
      Array.from(selectedTopics),
      topic => d[topic].redditPosts
    );
  }

  function render() {
    const width = container.node().getBoundingClientRect().width;

    if (width < 100 || !chartData.length) return;

    const small = width < 560;
    const topMargin = small ? 38 : 42;
    const left = small ? 28 : 36;
    const right = small ? 8 : 18;
    const bottom = small ? 45 : 48;

    const usableWidth = width - left - right;
    const topLabelY = topMargin;
    const upperTop = topMargin + panelLabelHeight;
    const upperBottom = upperTop + (small ? 125 : 155);

    // Shared timeline between the two streams.
    const timelineTop = upperBottom + 5;
    const monthLabelY = timelineTop + 17;

    const lowerTop = timelineTop + 28;
    const lowerBottom = lowerTop + (small ? 125 : 155);
    const lowerLabelY = lowerBottom + 19;
    const plotBottom = lowerLabelY + bottom - 18;

    dimensions = {
      left,
      right,
      usableWidth,
      topLabelY,
      upperTop,
      upperBottom,
      timelineTop,
      monthLabelY,
      lowerTop,
      lowerBottom,
      lowerLabelY
    };

    const chartHeight = plotBottom + 12;

    // Remove only the SVG; keep the tooltip in the chart card.
    container.selectAll("svg").remove();

    svg = container.append("svg")
      .attr("viewBox", `0 0 ${width} ${chartHeight}`)
      .attr("role", "img")
      .attr(
        "aria-label",
        "Mirrored streamgraph comparing monthly Wikipedia pageview shares " +
        "with topic assignment shares in a sample of Reddit posts"
      );

    const x = d3.scaleTime()
      .domain(d3.extent(chartData, d => d.month))
      .range([left + 10, width - right - 10]);

    const activeTopics = topicLayers.filter(topic =>
      selectedTopics.has(topic)
    );

    // Recalculate Wikipedia shares among selected topics.
    const wikiStack = d3.stack()
      .keys(activeTopics)
      .value((d, topic) => {
        const total = getSelectedWikiTotal(d);

        return total > 0
          ? d[topic].wikiViews / total
          : 0;
      })
      .order(d3.stackOrderNone)
      .offset(d3.stackOffsetNone)(chartData);

    // Recalculate Reddit shares among selected topic assignments.
    const redditStack = d3.stack()
      .keys(activeTopics)
      .value((d, topic) => {
        const total = getSelectedRedditTotal(d);

        return d.hasRedditEvidence && total > 0
          ? d[topic].redditPosts / total
          : 0;
      })
      .order(d3.stackOrderNone)
      .offset(d3.stackOffsetNone)(chartData);

    const wikiY = d3.scaleLinear()
      .domain([0, 1])
      .range([dimensions.upperBottom, dimensions.upperTop]);

    const redditY = d3.scaleLinear()
      .domain([0, 1])
      .range([dimensions.lowerTop, dimensions.lowerBottom]);

    // Monthly guides connect both streams.
    const grid = svg.append("g")
      .attr("aria-hidden", "true");

    grid.selectAll(".comparison-grid-upper")
      .data(chartData)
      .join("line")
      .attr("class", "comparison-gridline comparison-grid-upper")
      .attr("x1", d => x(d.month))
      .attr("x2", d => x(d.month))
      .attr("y1", dimensions.upperTop)
      .attr("y2", dimensions.upperBottom);

    grid.selectAll(".comparison-grid-lower")
      .data(chartData)
      .join("line")
      .attr("class", "comparison-gridline comparison-grid-lower")
      .attr("x1", d => x(d.month))
      .attr("x2", d => x(d.month))
      .attr("y1", dimensions.lowerTop)
      .attr("y2", dimensions.lowerBottom);

    svg.append("text")
      .attr("class", "comparison-panel-label")
      .attr("x", left)
      .attr("y", dimensions.topLabelY)
      .text("WIKIPEDIA");

    svg.append("text")
      .attr("class", "comparison-panel-subtitle")
      .attr("x", left + 92)
      .attr("y", dimensions.topLabelY)
      .text("Share of pageviews across selected topics");

    svg.append("text")
      .attr("class", "comparison-panel-label")
      .attr("x", left)
      .attr("y", dimensions.lowerLabelY)
      .text("REDDIT SAMPLE");

    svg.append("text")
      .attr("class", "comparison-panel-subtitle")
      .attr("x", left + 100)
      .attr("y", dimensions.lowerLabelY)
      .text("Share of classified topic assignments");

    svg.append("line")
      .attr("class", "comparison-baseline")
      .attr("x1", left)
      .attr("x2", width - right)
      .attr("y1", dimensions.timelineTop)
      .attr("y2", dimensions.timelineTop);

    const upperArea = d3.area()
      .x(d => x(d.data.month))
      .y0(d => wikiY(d[0]))
      .y1(d => wikiY(d[1]))
      .curve(d3.curveMonotoneX);

    const lowerArea = d3.area()
      .defined(d => d.data.hasRedditEvidence)
      .x(d => x(d.data.month))
      .y0(d => redditY(d[0]))
      .y1(d => redditY(d[1]))
      .curve(d3.curveStepAfter);

    // Wikipedia stream.
    const upperGroup = svg.append("g")
      .attr("class", "comparison-upper-stream");

    upperGroup.selectAll("path")
      .data(wikiStack)
      .join("path")
      .attr("class", "comparison-area")
      .attr("data-topic", d => d.key)
      .attr("fill", d => color(d.key))
      .attr("d", upperArea);

    // Reddit stream.
    const lowerGroup = svg.append("g")
      .attr("class", "comparison-lower-stream");

    lowerGroup.selectAll("path")
      .data(redditStack)
      .join("path")
      .attr("class", "comparison-area")
      .attr("data-topic", d => d.key)
      .attr("fill", d => color(d.key))
      .attr("d", lowerArea);

    // Add readable topic labels where bands are wide enough.
    drawTopicLabels(wikiStack, x, wikiY, small);

    // Single timeline: Sep 25, Oct 25, ... Aug 26.
    const monthLabels = svg.append("g")
      .attr("class", "comparison-timeline")
      .attr("aria-label", "Shared monthly timeline")
      .attr("pointer-events", "none");

    monthLabels.selectAll(".comparison-month-label")
      .data(chartData)
      .join("text")
      .attr("class", "comparison-month-label")
      .attr("x", d => x(d.month))
      .attr("y", dimensions.monthLabelY)
      .style("font-size", small ? "8px" : "9px")
      .text(d => formatTimelineMonth(d.month));

    drawNoDataAnnotation(x);

    // Vertical guide follows the hovered month.
    const focusLine = svg.append("line")
      .attr("class", "comparison-month-focus")
      .style("display", "none")
      .attr("pointer-events", "none")
      .attr("y1", dimensions.upperTop)
      .attr("y2", dimensions.lowerBottom);

    // Transparent hover layer across both streams.
    svg.append("rect")
      .attr("class", "comparison-hover-area")
      .attr("x", left)
      .attr("y", dimensions.upperTop)
      .attr("width", usableWidth)
      .attr("height", dimensions.lowerBottom - dimensions.upperTop)
      .attr("fill", "transparent")
      .attr("pointer-events", "all")
      .style("cursor", "crosshair")
      .on("pointermove", function (event) {
        const [pointerX, pointerY] = d3.pointer(event, svg.node());

        const monthIndex = d3.leastIndex(
          chartData,
          d => Math.abs(x(d.month) - pointerX)
        );

        if (monthIndex == null) return;

        const datum = chartData[monthIndex];
        const isWiki = pointerY <= dimensions.upperBottom;
        const isReddit = pointerY >= dimensions.lowerTop;

        if (!isWiki && !isReddit) {
          focusLine.style("display", "none");
          tooltip.style("display", "none");
          return;
        }

        focusLine
          .style("display", null)
          .attr("x1", x(datum.month))
          .attr("x2", x(datum.month));

        const topic = findTopicAtPointer(
          monthIndex,
          pointerY,
          isWiki,
          wikiStack,
          redditStack,
          wikiY,
          redditY
        );

        showTooltip(event, datum, topic, isWiki);
      })
      .on("pointerleave", () => {
        focusLine.style("display", "none");
        tooltip.style("display", "none");
        updateDefaultStatus();
      });

    updateHighlight();
  }

  function drawTopicLabels(wikiStack, x, yScale, small) {
    const minBandHeight = small ? 17 : 19;
    const fontSize = small ? 9 : 10;
    const placed = [];
    const labels = [];

    wikiStack.forEach(layer => {
      const candidates = layer.map((point, index) => ({
        point,
        index,
        thickness: Math.abs(
          yScale(point[0]) - yScale(point[1])
        )
      })).filter(d => d.thickness >= minBandHeight);

      if (!candidates.length) return;

      // Prefer a thick band near the middle of the timeline.
      const middle = (chartData.length - 1) / 2;

      candidates.sort((a, b) => {
        const scoreA =
          a.thickness - Math.abs(a.index - middle) * 0.35;
        const scoreB =
          b.thickness - Math.abs(b.index - middle) * 0.35;

        return scoreB - scoreA;
      });

      for (const candidate of candidates) {
        const point = candidate.point;
        const label = topicShortNames[layer.key] || layer.key;
        const labelWidth = label.length * (small ? 5.1 : 5.7);
        const labelX = x(point.data.month);
        const labelY = (yScale(point[0]) + yScale(point[1])) / 2;

        const overlaps = placed.some(other =>
          Math.abs(labelX - other.x) <
            (labelWidth + other.width) / 2 + 8 &&
          Math.abs(labelY - other.y) < fontSize + 3
        );

        if (!overlaps) {
          labels.push({
            topic: layer.key,
            label,
            x: labelX,
            y: labelY,
            width: labelWidth
          });

          placed.push({
            x: labelX,
            y: labelY,
            width: labelWidth
          });

          break;
        }
      }
    });

    svg.append("g")
      .attr("class", "comparison-topic-labels")
      .attr("pointer-events", "none")
      .selectAll("text")
      .data(labels)
      .join("text")
      .attr("class", "comparison-topic-label")
      .attr("x", d => d.x)
      .attr("y", d => d.y)
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "middle")
      .attr("font-size", fontSize)
      .attr("font-weight", 600)
      .attr("fill", "#ffffff")
      .attr("stroke", "rgba(35, 45, 60, 0.55)")
      .attr("stroke-width", 2.5)
      .attr("paint-order", "stroke")
      .text(d => d.label);
  }

  function drawNoDataAnnotation(x) {
    const noData = chartData.filter(d => !d.hasRedditEvidence);

    noData.forEach(d => {
      const xPos = x(d.month);

      svg.append("rect")
        .attr("class", "comparison-no-data-bg")
        .attr("x", xPos - 34)
        .attr("y", dimensions.lowerTop + 8)
        .attr("width", 68)
        .attr("height", 31)
        .attr("rx", 5)
        .attr("pointer-events", "none");

      svg.append("text")
        .attr("class", "comparison-no-data")
        .attr("x", xPos)
        .attr("y", dimensions.lowerTop + 20)
        .attr("pointer-events", "none")
        .text("No classified");

      svg.append("text")
        .attr("class", "comparison-no-data")
        .attr("x", xPos)
        .attr("y", dimensions.lowerTop + 31)
        .attr("pointer-events", "none")
        .text("posts");
    });
  }

  function findTopicAtPointer(
    monthIndex,
    pointerY,
    isWiki,
    wikiStack,
    redditStack,
    wikiY,
    redditY
  ) {
    const stack = isWiki ? wikiStack : redditStack;
    const yScale = isWiki ? wikiY : redditY;

    if (!isWiki && !chartData[monthIndex].hasRedditEvidence) {
      return null;
    }

    const layer = stack.find(series => {
      const point = series[monthIndex];
      if (!point) return false;

      const y0 = yScale(point[0]);
      const y1 = yScale(point[1]);

      return pointerY >= Math.min(y0, y1) &&
        pointerY <= Math.max(y0, y1);
    });

    return layer ? layer.key : null;
  }

  function showTooltip(event, datum, topic, isWiki) {
    if (tooltip.empty() || chartCard.empty()) return;

    const source = isWiki ? "Wikipedia" : "Reddit sample";

    let body = `
      <strong>${formatMonth(datum.month)}</strong>
      <div class="tooltip-muted">${source}</div>
    `;

    if (!topic) {
      body += `
        <div>Move over a colored band to inspect a topic.</div>
      `;
    } else {
      const values = datum[topic];

      body += `
        <div class="tooltip-topic">
          <span class="tooltip-swatch"
                style="background:${color(topic)}"></span>
          ${topic}
        </div>
      `;

      if (isWiki) {
        const selectedTotal = getSelectedWikiTotal(datum);
        const share = selectedTotal > 0
          ? values.wikiViews / selectedTotal
          : 0;

        body += `
          <div><strong>${formatNumber(values.wikiViews)}</strong> pageviews</div>
          <div>${formatPercent(share)} of pageviews among selected topics</div>
          <div class="tooltip-muted">
            ${formatNumber(selectedTotal)} pageviews across selected topics
          </div>
        `;
      } else if (!datum.hasRedditEvidence) {
        body += `
          <div>No classified posts this month.</div>
          <div class="tooltip-muted">
            This indicates missing classified evidence, not an absence of discussion.
          </div>
        `;
      } else {
        const selectedTotal = getSelectedRedditTotal(datum);
        const share = selectedTotal > 0
          ? values.redditPosts / selectedTotal
          : 0;

        body += `
          <div><strong>${formatNumber(values.redditPosts)}</strong> topic assignments</div>
          <div>${formatPercent(share)} of assignments among selected topics</div>
          <div class="tooltip-muted">
            ${formatNumber(datum.redditClassified)} classified posts out of
            ${formatNumber(datum.redditCollected)} collected posts;
            ${formatNumber(datum.redditAssignments)} total topic assignments.
          </div>
        `;
      }
    }

    tooltip.html(body).style("display", "block");

    const cardRect = chartCard.node().getBoundingClientRect();
    const tooltipRect = tooltip.node().getBoundingClientRect();

    const pointerX = event.clientX - cardRect.left;
    const pointerY = event.clientY - cardRect.top;

    let left = pointerX + 14;
    let top = pointerY + 14;

    if (left + tooltipRect.width > cardRect.width - 8) {
      left = pointerX - tooltipRect.width - 14;
    }

    if (top + tooltipRect.height > chartCard.node().clientHeight - 8) {
      top = pointerY - tooltipRect.height - 14;
    }

    tooltip
      .style("left", `${Math.max(8, left)}px`)
      .style("top", `${Math.max(8, top)}px`);
  }

  function updateHighlight() {
    const hasSelection = selectedTopics.size > 0;

    legend.selectAll("button")
      .classed("is-muted", topic =>
        hasSelection && !selectedTopics.has(topic)
      )
      .attr("aria-pressed", topic =>
        String(selectedTopics.has(topic))
      );
  }

  function updateDefaultStatus() {
    const selectedLabel = selectedTopics.size === 0
      ? "No topics selected"
      : selectedTopics.size === topicLayers.length
        ? "All topics shown"
        : `${selectedTopics.size} of ${topicLayers.length} topics shown`;

    const totalWikiViews = d3.sum(
      chartData,
      d => getSelectedWikiTotal(d)
    );

    const totalClassified = d3.sum(
      chartData,
      d => d.redditClassified
    );

    const totalCollected = d3.sum(
      chartData,
      d => d.redditCollected
    );

    status.html(`
      <span>${selectedLabel}</span>
      <span>
        Study period: <strong>September 2025 – August 2026</strong>
      </span>
      <span>
        ${formatNumber(totalWikiViews)} Wikipedia pageviews across selected topics
      </span>
      <span>
        ${formatNumber(totalClassified)} classified Reddit posts out of
        ${formatNumber(totalCollected)} collected
      </span>
    `);
  }

  init();
})();