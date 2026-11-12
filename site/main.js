// CapitolAlpha: one driver (the event day) for the pinned plot, plus the
// intro, the filing stamp and the appendix charts. Every animation runs on
// GSAP's ticker. Under reduced motion the state jumps per unit and nothing tweens.
(() => {
  'use strict';

  const SVG = 'http://www.w3.org/2000/svg';
  const MINUS = '−';
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const gsap = window.gsap;
  const ScrollTrigger = window.ScrollTrigger;
  const animate = Boolean(gsap && ScrollTrigger) && !reduce;
  if (gsap && ScrollTrigger) gsap.registerPlugin(ScrollTrigger);
  if (gsap && window.SplitText) gsap.registerPlugin(window.SplitText);

  const el = (name, attrs = {}, parent) => {
    const node = document.createElementNS(SVG, name);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
    if (parent) parent.appendChild(node);
    return node;
  };
  const text = (parent, x, y, content, attrs = {}) => {
    const node = el('text', { x, y, ...attrs }, parent);
    node.textContent = content;
    return node;
  };
  const signed = (value, digits = 0) => {
    const fixed = Math.abs(value).toFixed(digits);
    if (Number(fixed) === 0) return (0).toFixed(digits);
    return (value < 0 ? MINUS : '+') + fixed;
  };
  const pct = (value, digits = 2) => `${signed(value * 100, digits)}%`;
  const lerp = (a, b, t) => a + (b - a) * t;

  // ---------------------------------------------------------------- plot

  const stage = document.querySelector('.stage');
  const plotSvg = document.querySelector('.plot');
  const domeWrap = document.querySelector('.dome-wrap');
  const dome = document.querySelector('.dome');
  const counter = document.querySelector('.counter__value');

  // Event days map onto a broken axis: the long estimation window is compressed.
  const SEGMENTS = [
    [-250, -30, 0, 0.16],
    [-30, 0, 0.21, 0.33],
    [0, 125, 0.33, 1],
  ];
  const MARKERS = [
    { day: -9, label: 'Trade', dash: '3 4' },
    { day: 0, label: 'Disclosure', strong: true },
    { day: 20, label: '+20' },
    { day: 62, label: '+62, primary', accent: true },
    { day: 125, label: '+125' },
  ];
  const Y_MAX = 2.5;

  const state = { day: -250, intro: 0 };
  let path = [];
  let plot = null;

  const fraction = (day) => {
    for (const [d0, d1, f0, f1] of SEGMENTS) {
      if (day <= d1) return lerp(f0, f1, (Math.max(day, d0) - d0) / (d1 - d0));
    }
    return 1;
  };

  const carAt = (day) => {
    if (day <= 0 || !path.length) return 0;
    const i = Math.min(Math.floor(day), path.length - 1);
    const a = path[i];
    const b = path[Math.min(i + 1, path.length - 1)];
    return lerp(a.mean, b.mean, day - i);
  };

  function buildPlot() {
    plotSvg.replaceChildren();
    const W = plotSvg.clientWidth;
    const H = plotSvg.clientHeight;
    if (!W || !H) return null;
    plotSvg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    const narrow = W < 520;
    const left = narrow ? 34 : 46;
    const right = narrow ? 8 : 18;
    const top = narrow ? 34 : 52;
    const bottom = narrow ? 30 : 44;
    const zeroY = domeWrap ? domeWrap.offsetTop : H * 0.52;
    const k = Math.min(zeroY - top, H - bottom - zeroY) / Y_MAX;
    const x = (day) => left + fraction(day) * (W - left - right);
    const y = (value) => zeroY - value * 100 * k;
    const yTop = y(Y_MAX / 100);
    const yBottom = y(-Y_MAX / 100);

    const axes = el('g', { class: 'axes' }, plotSvg);
    el('rect', {
      x: x(-250), y: yTop, width: x(-30) - x(-250), height: yBottom - yTop,
      fill: 'var(--band)', opacity: 0.55,
    }, axes);
    text(axes, x(-250) + 6, yTop + 16, narrow ? 'Model fit' : 'Model fit, days −250 to −30');
    for (const v of [-2, -1, 1, 2]) {
      el('line', { x1: left, x2: W - right, y1: y(v / 100), y2: y(v / 100), stroke: 'var(--line)', 'stroke-width': 1 }, axes);
      text(axes, left - 8, y(v / 100) + 4, `${signed(v)}%`, { 'text-anchor': 'end' });
    }
    text(axes, left - 8, zeroY + 4, '0%', { 'text-anchor': 'end', class: 'lbl-strong' });
    const gapX = left + 0.185 * (W - left - right);
    el('path', {
      d: `M${gapX - 5} ${zeroY + 6} l6 -12 M${gapX + 1} ${zeroY + 6} l6 -12`,
      stroke: 'var(--muted)', 'stroke-width': 1.25, fill: 'none',
    }, axes);
    for (const day of [-250, -30, 0, 20, 62, 125]) {
      text(axes, x(day), yBottom + (narrow ? 18 : 24), signed(day), { 'text-anchor': 'middle' });
    }
    if (!narrow) text(axes, W - right, yBottom + 40, 'Trading days from disclosure', { 'text-anchor': 'end' });

    const markers = el('g', { class: 'markers' }, plotSvg);
    const markerEls = MARKERS.map((m) => {
      const g = el('g', { class: 'marker', opacity: 0.25 }, markers);
      el('line', {
        x1: x(m.day), x2: x(m.day), y1: yTop, y2: yBottom,
        stroke: m.accent ? 'var(--accent)' : 'var(--ink)',
        'stroke-width': m.strong || m.accent ? 1.5 : 1,
        'stroke-dasharray': m.dash || (m.strong || m.accent ? '' : '2 4'),
      }, g);
      if (!narrow || m.strong || m.accent) {
        const before = m.day < 0;
        text(g, x(m.day) + (before ? -6 : 6), yTop + (before ? 36 : 16), narrow && m.accent ? '+62' : m.label, {
          class: m.accent ? 'lbl-accent' : m.strong ? 'lbl-strong' : '',
          'text-anchor': before ? 'end' : 'start',
        });
      }
      return { ...m, g };
    });

    const clipId = 'reveal-clip';
    const defs = el('defs', {}, plotSvg);
    const clip = el('clipPath', { id: clipId }, defs);
    const clipRect = el('rect', { x: x(0), y: 0, width: 0, height: H }, clip);
    const data = el('g', { 'clip-path': `url(#${clipId})` }, plotSvg);
    const band = el('path', { fill: 'var(--band)', stroke: 'none' }, data);
    const line = el('path', {
      fill: 'none', stroke: 'var(--accent)', 'stroke-width': 2.5,
      'stroke-linejoin': 'round', 'stroke-linecap': 'round',
    }, data);

    const ground = el('line', {
      x1: 0, x2: W, y1: zeroY, y2: zeroY,
      stroke: 'var(--ink)', 'stroke-width': 1.5, 'stroke-linecap': 'round', class: 'ground',
    }, plotSvg);

    const cursor = el('g', { class: 'cursor' }, plotSvg);
    const ring = el('circle', { r: 6, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 1.5, opacity: 0 }, cursor);
    el('circle', { r: 5, fill: 'var(--accent)', stroke: 'var(--ground)', 'stroke-width': 2 }, cursor);
    const readout = text(cursor, 10, -12, '', { class: 'lbl-accent' });

    const p = { W, H, left, x, y, zeroY, axes, markerEls, clipRect, band, line, ground, cursor, ring, readout };
    drawData(p);
    return p;
  }

  function drawData(p) {
    if (!p || !path.length) return;
    const upper = path.map((q) => `${p.x(q.day).toFixed(1)},${p.y(q.mean + 1.96 * q.se).toFixed(1)}`);
    const lower = path.map((q) => `${p.x(q.day).toFixed(1)},${p.y(q.mean - 1.96 * q.se).toFixed(1)}`).reverse();
    p.band.setAttribute('d', `M${upper.join('L')}L${lower.join('L')}Z`);
    p.line.setAttribute('d', `M${path.map((q) => `${p.x(q.day).toFixed(1)},${p.y(q.mean).toFixed(1)}`).join('L')}`);
  }

  function render() {
    if (!plot) return;
    const { day, intro } = state;
    const cx = plot.x(day);
    const cy = plot.y(carAt(day));
    plot.cursor.setAttribute('transform', `translate(${cx.toFixed(1)} ${cy.toFixed(1)})`);
    plot.clipRect.setAttribute('width', day > 0 ? (plot.x(day) - plot.x(0) + 1).toFixed(1) : '0');
    plot.ground.setAttribute('x1', lerp(0, plot.left, intro).toFixed(1));
    plot.readout.textContent = day >= 0.5 && path.length ? pct(carAt(day)) : '';
    plot.readout.setAttribute('text-anchor', cx > plot.W - 90 ? 'end' : 'start');
    plot.readout.setAttribute('x', cx > plot.W - 90 ? -10 : 10);
    plot.axes.setAttribute('opacity', intro.toFixed(3));
    plot.cursor.setAttribute('opacity', intro.toFixed(3));
    for (const m of plot.markerEls) m.g.setAttribute('opacity', ((day >= m.day - 0.5 ? 1 : 0.22) * intro).toFixed(3));
    if (domeWrap) {
      dome.style.translate = `0 ${(intro * 100).toFixed(2)}%`;
      domeWrap.style.opacity = String(1 - intro * 0.4);
    }
    if (counter) counter.textContent = signed(Math.round(day));
  }

  function mountPlot() {
    plot = buildPlot();
    render();
  }

  // ---------------------------------------------------------------- driver

  function driveTimeline() {
    const units = [...document.querySelectorAll('.unit[data-from]')];
    if (!gsap || !ScrollTrigger) {
      Object.assign(state, { day: 125, intro: 1 });
      render();
      return;
    }

    if (reduce) {
      for (const unit of units) {
        ScrollTrigger.create({
          trigger: unit,
          start: 'top 60%',
          end: 'bottom 60%',
          onToggle: (self) => {
            if (!self.isActive) return;
            state.day = Number(unit.dataset.to);
            state.intro = unit.id === 'question' ? 0 : 1;
            render();
          },
        });
      }
      return;
    }

    const toDay = gsap.quickTo(state, 'day', { duration: 0.55, ease: 'power3.out', onUpdate: render });
    ScrollTrigger.create({
      trigger: '#estimation',
      start: 'top bottom',
      end: 'top 45%',
      scrub: 0.6,
      onUpdate: (self) => {
        state.intro = self.progress;
        render();
      },
    });
    for (const unit of units.slice(1)) {
      const from = Number(unit.dataset.from);
      const to = Number(unit.dataset.to);
      ScrollTrigger.create({
        trigger: unit,
        start: 'top 55%',
        end: 'bottom 55%',
        onUpdate: (self) => toDay(lerp(from, to, self.progress)),
        onEnterBack: () => toDay(to),
      });
    }
    ScrollTrigger.create({
      trigger: '#question',
      start: 'top top',
      end: 'bottom 55%',
      onEnterBack: () => toDay(-250),
    });

    let pulse = null;
    ScrollTrigger.create({
      trigger: '.timeline',
      start: 'top bottom',
      end: 'bottom top',
      onToggle: (self) => {
        if (!plot) return;
        if (!pulse) {
          pulse = gsap.fromTo(plot.ring, { attr: { r: 6 }, opacity: 0.7 }, {
            attr: { r: 16 }, opacity: 0, duration: 2, ease: 'power2.out', repeat: -1, repeatDelay: 0.6,
          });
        }
        self.isActive ? pulse.play() : pulse.pause();
      },
    });
  }

  // ---------------------------------------------------------------- intro

  // The head script adds html.motion, which hides the intro targets before first paint.
  function intro() {
    const root = document.documentElement;
    if (!animate) {
      root.classList.remove('motion');
      return;
    }
    const strokes = dome ? [...dome.querySelectorAll('[data-draw]')] : [];
    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });
    gsap.set(strokes, { strokeDasharray: 1, strokeDashoffset: 1 });
    root.classList.remove('motion');
    tl.to(strokes, { strokeDashoffset: 0, duration: 1.1, ease: 'power2.inOut', stagger: 0.06 }, 0.15);
    if (plot) tl.from(plot.ground, { attr: { x2: 0 }, duration: 1.2, ease: 'power3.inOut' }, 0);
    tl.fromTo('.unit--question .answer, .unit--question .byline, .unit--question .scroll-cue',
      { y: 18, opacity: 0 }, { y: 0, opacity: 1, duration: 0.8, stagger: 0.08 }, 0.55);
    const h1 = document.querySelector('.question');
    if (h1 && window.SplitText) {
      window.SplitText.create(h1, {
        type: 'lines', mask: 'lines', autoSplit: true,
        onSplit: (self) => gsap.from(self.lines, { yPercent: 105, duration: 1, stagger: 0.08, ease: 'power3.out', delay: 0.1 }),
      });
    }
  }

  // ---------------------------------------------------------------- filing

  function filing(lag) {
    const art = document.querySelector('.filing__art');
    if (art && typeof art.pauseAnimations === 'function') {
      const ms = Number(art.dataset.glaxMs);
      art.pauseAnimations();
      if (!animate) {
        art.setCurrentTime(ms / 1000);
      } else {
        const t = { ms: 0 };
        art.setCurrentTime(0);
        gsap.to(t, {
          ms, ease: 'none',
          scrollTrigger: { trigger: '.filing', start: 'top 85%', end: 'top 35%', scrub: 0.4 },
          onUpdate: () => art.setCurrentTime(t.ms / 1000),
        });
      }
    }

    const svg = document.querySelector('.lags__chart');
    if (!svg || !lag) return;
    const W = svg.clientWidth;
    const H = svg.clientHeight;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    const bins = lag.bins;
    const max = Math.max(...bins.map((b) => b.trades));
    const gap = 2;
    const bw = (W - gap * (bins.length - 1)) / bins.length;
    const base = H - 22;
    const bars = bins.map((b, i) => {
      const h = Math.max(1, (b.trades / max) * (base - 20));
      return el('rect', {
        x: i * (bw + gap), y: base - h, width: bw, height: h,
        fill: b.from >= lag.deadline_days ? 'var(--accent)' : 'var(--ink)',
      }, svg);
    });
    const deadline = bins.findIndex((b) => b.from >= lag.deadline_days);
    const dx = deadline * (bw + gap) - gap / 2;
    const rule = el('line', { x1: dx, x2: dx, y1: 4, y2: base, stroke: 'var(--accent)', 'stroke-width': 1.5, 'stroke-dasharray': '3 3' }, svg);
    text(svg, dx + 6, 14, `${lag.deadline_days}-day deadline`, { class: 'lbl-accent', fill: 'var(--accent)', 'font-weight': 650 });
    text(svg, 0, H - 4, '0 days');
    text(svg, dx, H - 4, String(lag.deadline_days), { 'text-anchor': 'middle' });
    text(svg, W, H - 4, `${bins[bins.length - 1].from}+`, { 'text-anchor': 'end' });
    if (animate) {
      gsap.timeline({ scrollTrigger: { trigger: svg, start: 'top 85%', once: true } })
        .from(bars, { scaleY: 0, transformOrigin: '50% 100%', duration: 0.7, ease: 'power3.out', stagger: 0.025 })
        .from(rule, { attr: { y1: base }, duration: 0.5, ease: 'power2.out' }, 0.35);
    }
  }

  // ---------------------------------------------------------------- forest

  function forest(rows) {
    const svg = document.querySelector('.forest__chart');
    if (!svg || !rows) return;
    svg.replaceChildren();
    const W = svg.clientWidth;
    const narrow = W < 560;
    const rowH = narrow ? 44 : 46;
    const H = rows.length * rowH + 40;
    svg.style.height = `${H}px`;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    const labelW = narrow ? 0 : Math.min(260, W * 0.42);
    const left = labelW + 12;
    const right = 12;
    const span = 0.24;
    const x = (v) => left + ((v + span) / (2 * span)) * (W - left - right);
    const zero = el('line', { x1: x(0), x2: x(0), y1: 4, y2: H - 30, stroke: 'var(--ink)', 'stroke-width': 1.5 }, svg);
    for (const v of [-0.2, -0.1, 0.1, 0.2]) {
      el('line', { x1: x(v), x2: x(v), y1: 4, y2: H - 30, stroke: 'var(--line)', 'stroke-width': 1 }, svg);
    }
    for (const v of [-0.2, -0.1, 0, 0.1, 0.2]) {
      text(svg, x(v), H - 10, `${signed(v * 100)}%`, { 'text-anchor': 'middle', class: v === 0 ? 'lbl-strong' : '' });
    }
    const bars = [];
    const dots = [];
    rows.forEach((r, i) => {
      if (r.alpha_annual === null) return;
      const se = Math.abs(r.alpha_annual / r.t);
      const lo = r.alpha_annual - 1.96 * se;
      const hi = r.alpha_annual + 1.96 * se;
      const cy = i * rowH + (narrow ? 30 : rowH / 2 + 4);
      const label = r.check.replace('Primary: ', 'Primary, ');
      if (narrow) text(svg, 0, cy - 12, label, { class: i === 0 ? 'lbl-strong' : '' });
      else text(svg, 0, cy + 4, label, { class: i === 0 ? 'lbl-strong' : '' });
      bars.push(el('line', {
        x1: x(Math.max(lo, -span)), x2: x(Math.min(hi, span)), y1: cy, y2: cy,
        stroke: i === 0 ? 'var(--accent)' : 'var(--ink)', 'stroke-width': i === 0 ? 3 : 2, 'stroke-linecap': 'round',
      }, svg));
      dots.push(el('circle', {
        cx: x(r.alpha_annual), cy, r: i === 0 ? 6 : 4.5,
        fill: i === 0 ? 'var(--accent)' : 'var(--ground)', stroke: i === 0 ? 'var(--accent)' : 'var(--ink)', 'stroke-width': 2,
      }, svg));
    });
    if (animate) {
      const tl = gsap.timeline({ scrollTrigger: { trigger: svg, start: 'top 80%', once: true } });
      tl.from(zero, { attr: { y2: 4 }, duration: 0.6, ease: 'power2.inOut' })
        .from(bars, { scaleX: 0, transformOrigin: '50% 50%', duration: 0.7, ease: 'power3.out', stagger: 0.06 }, 0.3)
        .from(dots, { opacity: 0, attr: { r: 0 }, duration: 0.4, ease: 'back.out(2)', stagger: 0.06 }, 0.45);
    }
  }

  // ---------------------------------------------------------------- counts

  function counts() {
    if (!animate) return;
    for (const node of document.querySelectorAll('[data-count]')) {
      const end = Number(node.dataset.count);
      const t = { v: 0 };
      gsap.to(t, {
        v: end, duration: 1.4, ease: 'power2.out',
        scrollTrigger: { trigger: node, start: 'top 80%', once: true },
        onUpdate: () => { node.textContent = Math.round(t.v).toLocaleString('en-US'); },
      });
    }
  }

  // ---------------------------------------------------------------- start

  function start(figures) {
    window.clearTimeout(window.__introGuard);
    if (figures) path = figures.car_disclosure;
    mountPlot();
    driveTimeline();
    intro();
    counts();
    filing(figures && figures.lag);
    forest(figures && figures.robustness);

    let width = window.innerWidth;
    const resize = () => {
      if (Math.abs(window.innerWidth - width) < 2 && plot) return;
      width = window.innerWidth;
      mountPlot();
      forest(figures && figures.robustness);
      if (ScrollTrigger) ScrollTrigger.refresh();
    };
    if (window.ResizeObserver && stage) new ResizeObserver(() => resize()).observe(document.body);
  }

  fetch('/data/figures.json')
    .then((response) => (response.ok ? response.json() : null))
    .catch(() => null)
    .then(start);
})();
