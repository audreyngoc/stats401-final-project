/* Vis 6: job titles by posting count and mean salary, linked to the selected Wikipedia article. */
(function() {
  'use strict';
  const $ = id => document.getElementById(id);
  const W = 760, H = 540, M = { top: 24, right: 28, bottom: 58, left: 66 };
  const PAGE = 40, LABEL_TOP = 6;
  const fmtK = v => `$${d3.format(',.0f')(v)}k`;
  const fmtInt = d3.format(',');

  const QUALIFIER = /programming language|software|operating system|comput|framework|library|database|markup|protocol|file format|machine learning|deep learning|statistics|company|platform|web/i;
  const ALIASES = { 'artificial intelligence': ['ai'], 'machine learning': ['ml'], 'natural language processing': ['nlp'], 'javascript': ['js'], 'deep learning': ['dl'] };
  const escape = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  function skillTerms(title) {
    let name = title.trim();
    const m = name.match(/^(.*?)\s*\(([^)]*)\)$/);
    if (m && QUALIFIER.test(m[2])) name = m[1];
    const phrase = name.toLocaleLowerCase('en');
    return { label: name, phrases: [phrase, ...(ALIASES[phrase] || [])] };
  }

  // A posting requires a skill when it is a listed requirement, or (for terms of 2+ characters)
  // the phrase appears as a whole word within one of its listed requirements.
  function skillMatcher(title) {
    const { label, phrases } = skillTerms(title);
    const body = phrases.filter(p => p.length >= 2).map(escape).join('|') || '$^';
    const textRe = new RegExp(`(?<![a-z0-9+#])(?:${body})(?![a-z0-9+#])`);
    const isSkill = s => phrases.includes(s.toLowerCase()) || textRe.test(s.toLowerCase());
    return { label, isSkill, test: p => phrases.some(x => p.skillSet.has(x)) || textRe.test(p.text) };
  }

  const state = { jobs: [], postings: [], skill: null, matches: new Set(), selected: null, shown: PAGE, onlyMatches: false };

  d3.csv('data/jobs_postings.csv', (d, i) => {
    const skills = d.requirements.split(' , ').map(s => s.trim()).filter(Boolean);
    return {
      id: i, title: d.title, skills, skillSet: new Set(skills.map(s => s.toLowerCase())),
      experience: +d.experience, salary_range: `${fmtK(+d.salary_low_k)} – ${fmtK(+d.salary_high_k)}`, salary_mid_k: +d.salary_mid_k,
      text: d.requirements.toLowerCase()
    };
  }).then(postings => {
    state.postings = postings;
    state.jobs = d3.groups(postings, d => d.title).map(([title, rows]) => ({
      title, rows, count: rows.length,
      salary: d3.mean(rows, r => r.salary_mid_k),
      salaryMin: d3.min(rows, r => r.salary_mid_k), salaryMax: d3.max(rows, r => r.salary_mid_k),
      experience: d3.median(rows, r => r.experience), matched: 0
    })).sort((a, b) => b.count - a.count || a.title.localeCompare(b.title));
    state.selected = state.jobs[0];
    $('jobs-summary').textContent = `${fmtInt(postings.length)} job postings across ${fmtInt(state.jobs.length)} job titles.`;
    buildControls(); buildChart(); renderListing();
    window.addEventListener('knowledge:selection', syncSkill);
    window.addEventListener('knowledge:seed', syncSkill);
    syncSkill();
  }).catch(e => { $('jobs-summary').textContent = 'Could not load job postings. Serve this folder over HTTP, then refresh.'; console.error(e); });

  function syncSkill() {
    const model = window.knowledge;
    const node = model && (model.get(model.selectedId) || model.get(model.seedId));
    setSkill(node ? node.title : null, model && model.selectedId != null ? 'selected' : 'seed');
  }

  function setSkill(title, source) {
    state.skill = title ? skillMatcher(title) : null;
    state.matches = new Set(state.skill ? state.postings.filter(state.skill.test).map(p => p.id) : []);
    state.jobs.forEach(j => j.matched = j.rows.reduce((n, r) => n + state.matches.has(r.id), 0));
    const hit = state.jobs.filter(j => j.matched);
    const status = $('jobs-skill-status');
    status.replaceChildren();
    if (!state.skill) { status.textContent = 'Select a Wikipedia article above to highlight jobs that ask for it.'; }
    else {
      const b = document.createElement('strong'); b.textContent = state.skill.label;
      status.append(`Highlighting jobs whose postings require `, b,
        source === 'seed' ? ' (current starting article)' : ' (selected article)',
        hit.length ? ` — ${hit.length} of ${state.jobs.length} job titles, ${fmtInt(state.matches.size)} postings.` : ' — no postings list this skill.');
    }
    $('jobs-only-matches').disabled = !state.matches.size;
    if (!state.matches.size) { state.onlyMatches = false; $('jobs-only-matches').checked = false; }
    // Follow the skill to its most-posted job, unless the current job already matches.
    if (hit.length && !state.selected.matched) state.selected = hit[0];
    state.shown = PAGE;
    updateChart(); renderListing();
  }

  /* ---------- controls ---------- */
  function buildControls() {
    const sel = $('jobs-title-select');
    [...state.jobs].sort((a, b) => a.title.localeCompare(b.title)).forEach(j => {
      const o = document.createElement('option'); o.value = j.title; o.textContent = `${j.title} (${j.count})`; sel.append(o);
    });
    sel.value = state.selected.title;
    sel.onchange = () => selectJob(state.jobs.find(j => j.title === sel.value));
    $('jobs-only-matches').onchange = e => { state.onlyMatches = e.target.checked; state.shown = PAGE; renderListing(); };
  }

  function selectJob(job) {
    if (!job) return;
    state.selected = job; state.shown = PAGE; $('jobs-title-select').value = job.title;
    updateChart(); renderListing();
  }

  // scatterplot
  let x, y, gPoints, gLabels, delaunay, tooltip, svg;

  function buildChart() {
    const host = d3.select('#jobs-chart');
    svg = host.append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img')
      .attr('aria-label', 'Scatterplot of IT job titles: mean salary on the horizontal axis, number of postings on the vertical axis');
    x = d3.scaleLog().domain(padLog(d3.extent(state.jobs, d => d.salary))).range([M.left, W - M.right]);
    y = d3.scaleLog().domain([0.7, d3.max(state.jobs, d => d.count) * 1.4]).range([H - M.bottom, M.top]);

    const xTicks = [10, 20, 50, 100, 200, 500, 1000, 2000].filter(t => t >= x.domain()[0] && t <= x.domain()[1]);
    const yTicks = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000].filter(t => t <= y.domain()[1]);
    svg.append('g').attr('class', 'jobs-grid').selectAll('line').data(yTicks).join('line')
      .attr('x1', M.left).attr('x2', W - M.right).attr('y1', y).attr('y2', y);
    svg.append('g').attr('class', 'jobs-axis').attr('transform', `translate(0,${H - M.bottom})`)
      .call(d3.axisBottom(x).tickValues(xTicks).tickFormat(fmtK).tickSizeOuter(0));
    svg.append('g').attr('class', 'jobs-axis').attr('transform', `translate(${M.left},0)`)
      .call(d3.axisLeft(y).tickValues(yTicks).tickFormat(d3.format(',')).tickSizeOuter(0));
    svg.append('text').attr('class', 'jobs-axis-title').attr('x', (M.left + W - M.right) / 2).attr('y', H - 14).attr('text-anchor', 'middle')
      .text('Mean salary (USD, midpoint of each posting’s range, log scale)');
    svg.append('text').attr('class', 'jobs-axis-title').attr('transform', `translate(18,${(M.top + H - M.bottom) / 2}) rotate(-90)`).attr('text-anchor', 'middle')
      .text('Number of postings (log scale)');

    gPoints = svg.append('g');
    gLabels = svg.append('g').attr('class', 'jobs-labels');
    const hover = svg.append('circle').attr('class', 'jobs-hover').attr('r', 11).style('display', 'none');
    delaunay = d3.Delaunay.from(state.jobs, d => x(d.salary), d => y(d.count));
    tooltip = host.append('div').attr('class', 'jobs-tooltip').attr('role', 'tooltip').style('opacity', 0);

    const nearest = event => {
      const [px, py] = d3.pointer(event, svg.node());
      const d = state.jobs[delaunay.find(px, py)];
      return d && Math.hypot(x(d.salary) - px, y(d.count) - py) < 24 ? d : null;
    };
    svg.on('pointermove', event => {
      const d = nearest(event);
      if (!d) { hover.style('display', 'none'); tooltip.style('opacity', 0); svg.style('cursor', null); return; }
      svg.style('cursor', 'pointer');
      hover.style('display', null).attr('cx', x(d.salary)).attr('cy', y(d.count));
      showTooltip(d, event);
    }).on('pointerleave', () => { hover.style('display', 'none'); tooltip.style('opacity', 0); })
      .on('click', event => { const d = nearest(event); if (d) selectJob(d); });
  }

  function padLog([a, b]) { return [a / 1.25, b * 1.25]; }

  function showTooltip(d, event) {
    tooltip.html('');
    tooltip.append('strong').text(d.title);
    const dl = tooltip.append('dl');
    const rows = [['Postings', fmtInt(d.count)], ['Mean salary', fmtK(d.salary)],
    ['Posting midpoints', d.count > 1 ? `${fmtK(d.salaryMin)} – ${fmtK(d.salaryMax)}` : fmtK(d.salaryMin)],
    ['Median experience', `${d.experience} yr${d.experience === 1 ? '' : 's'}`]];
    if (state.skill) rows.push([`Require ${state.skill.label}`, `${fmtInt(d.matched)} of ${fmtInt(d.count)}`]);
    rows.forEach(([k, v]) => { dl.append('dt').text(k); dl.append('dd').text(v); });
    tooltip.append('p').text('Click to list these postings');
    const box = $('jobs-chart').getBoundingClientRect(), tip = tooltip.node().getBoundingClientRect();
    let left = event.clientX - box.left + 14, top = event.clientY - box.top + 14;
    if (left + tip.width > box.width) left = event.clientX - box.left - tip.width - 14;
    if (top + tip.height > box.height) top = Math.max(0, event.clientY - box.top - tip.height - 14);
    tooltip.style('left', `${left}px`).style('top', `${top}px`).style('opacity', 1);
  }

  function updateChart() {
    const active = !!state.matches.size;
    const order = d => (d === state.selected ? 2 : d.matched ? 1 : 0);
    const data = [...state.jobs].sort((a, b) => order(a) - order(b));
    gPoints.selectAll('circle.jobs-point').data(data, d => d.title).join('circle')
      .attr('class', d => `jobs-point${d.matched ? ' is-match' : ''}${active && !d.matched ? ' is-dim' : ''}${d === state.selected ? ' is-selected' : ''}`)
      .attr('cx', d => x(d.salary)).attr('cy', d => y(d.count))
      .attr('r', d => (d.matched ? 4.5 + 4 * Math.sqrt(d.matched / d.count) : 5))
      .order();

    const labelled = new Set(state.jobs.slice(0, LABEL_TOP)); labelled.add(state.selected);
    const placed = [...labelled].map(d => ({ d, x: x(d.salary), y: y(d.count) + 4 })).sort((a, b) => a.y - b.y);
    placed.forEach((p, i) => placed.slice(0, i).forEach(q => { if (Math.abs(p.x - q.x) < 160 && p.y - q.y < 13) p.y = q.y + 13; }));
    gLabels.selectAll('text').data(placed, p => p.d.title).join('text')
      .attr('class', p => (p.d === state.selected ? 'is-selected' : null))
      .attr('x', p => p.x + (p.x > W - 180 ? -9 : 9)).attr('y', p => p.y)
      .attr('text-anchor', p => (p.x > W - 180 ? 'end' : 'start'))
      .text(p => p.d.title);
  }

  // postings listing
  function renderListing() {
    const job = state.selected, list = $('jobs-list');
    $('jobs-list-title').textContent = job.title;
    const meta = [`${fmtInt(job.count)} posting${job.count === 1 ? '' : 's'}`, `mean salary ${fmtK(job.salary)}`];
    if (state.skill) meta.push(`${fmtInt(job.matched)} require ${state.skill.label}`);
    $('jobs-list-meta').textContent = meta.join(' · ');

    // Postings that require the skill come first; otherwise keep the dataset order.
    let rows = [...job.rows].sort((a, b) => state.matches.has(b.id) - state.matches.has(a.id));
    if (state.onlyMatches) rows = rows.filter(r => state.matches.has(r.id));
    list.replaceChildren(...rows.slice(0, state.shown).map(postingItem));
    if (!rows.length) { const p = document.createElement('p'); p.className = 'jobs-empty'; p.textContent = `No ${job.title} postings require ${state.skill?.label ?? 'this skill'}.`; list.append(p); }
    const more = $('jobs-more'), left = rows.length - state.shown;
    more.hidden = left <= 0;
    if (left > 0) more.textContent = `Show ${Math.min(PAGE, left)} more of ${fmtInt(left)}`;
    more.onclick = () => { state.shown += PAGE; renderListing(); };
  }

  function postingItem(p) {
    const li = document.createElement('li');
    const match = state.matches.has(p.id);
    li.className = `jobs-posting${match ? ' is-match' : ''}`;
    const head = document.createElement('div'); head.className = 'jobs-posting-head';
    const title = document.createElement('strong'); title.textContent = p.title;
    const sal = document.createElement('span'); sal.className = 'jobs-salary'; sal.textContent = p.salary_range;
    head.append(title, sal);
    // Skills as chips; the one linked to the selected article is highlighted.
    const skills = document.createElement('div'); skills.className = 'jobs-skills';
    skills.append(...p.skills.map(s => {
      const chip = document.createElement('span'); chip.textContent = s;
      chip.className = state.skill?.isSkill(s) ? 'jobs-chip is-match' : 'jobs-chip';
      return chip;
    }));
    li.append(head, skills);
    return li;
  }
})();
