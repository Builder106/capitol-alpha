// CapitolAlpha: one driver (event day, plus zoom) for the canvas stage, where
// every disclosed purchase is a dot. Everything runs on GSAP's ticker. Under
// reduced motion each unit sets its state at once and nothing tweens.
(() => {
  'use strict';

  const SVG = 'http://www.w3.org/2000/svg';
  const MINUS = '−';
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const gsap = window.gsap;
  const ScrollTrigger = window.ScrollTrigger;
  const SplitText = window.SplitText;
  const animate = Boolean(gsap && ScrollTrigger) && !reduce;
  if (gsap && ScrollTrigger) gsap.registerPlugin(ScrollTrigger);
  if (gsap && SplitText) gsap.registerPlugin(SplitText);

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
  const lerp = (a, b, t) => a + (b - a) * t;
  const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
  const smooth = (t) => t * t * (3 - 2 * t);

  // ---------------------------------------------------------------- stage

  const stage = document.querySelector('.stage');
  const canvas = document.querySelector('.plot');
  const domeWrap = document.querySelector('.dome-wrap');
  const dome = document.querySelector('.dome');
  const counter = document.querySelector('.counter__value');
  const ctx = canvas ? canvas.getContext('2d') : null;

  // Event days on a broken axis: the long estimation window is compressed.
  const SEGMENTS = [
    [-250, -30, 0, 0.14],
    [-30, 0, 0.19, 0.3],
    [0, 125, 0.3, 1],
  ];
  const MARKERS = [
    { day: -9, label: 'Trade' },
    { day: 0, label: 'Disclosure', strong: true },
    { day: 20, label: '+20' },
    { day: 62, label: '+62, primary', accent: true },
    { day: 125, label: '+125' },
  ];
  const RANGE_WIDE = 0.45;
  const RANGE_ZOOM = 0.025;
  const N = 3942;

  const state = { day: -250, intro: 0, zoom: 0, fall: 1 };
  let path = [];
  let geo = null;
  let dots = [];
  let dotValue = [];
  let dotSpan = [];
  let colors = {};

  const fraction = (day) => {
    for (const [d0, d1, f0, f1] of SEGMENTS) {
      if (day <= d1) return lerp(f0, f1, (Math.max(day, d0) - d0) / (d1 - d0));
    }
    return 1;
  };

  // Value at percentile p (0 to 100) on a given day, from the 1st to 99th percentiles.
  const quantile = (p, ps) => {
    // Beyond the 1st and 99th percentiles, stretch the tail by twice the 1-to-5 gap.
    if (p <= 1) return ps[0] - (ps[4] - ps[0]) * 2 * (1 - p);
    if (p >= 99) return ps[98] + (ps[98] - ps[94]) * 2 * (p - 99);
    const i = Math.floor(p) - 1;
    return lerp(ps[i], ps[i + 1], p - Math.floor(p));
  };
  const at = (day, key) => {
    if (!path.length) return 0;
    const d = clamp(day, 0, path.length - 1);
    const i = Math.min(Math.floor(d), path.length - 2);
    return lerp(path[i][key], path[i + 1][key], d - i);
  };
  const spreadAt = (day, p) => {
    const d = clamp(day, 0, path.length - 1);
    const i = Math.min(Math.floor(d), path.length - 2);
    return lerp(quantile(p, path[i].p), quantile(p, path[i + 1].p), d - i);
  };

  // Deterministic pseudo-random numbers so the dots land the same way every visit.
  function random(seed) {
    let s = seed >>> 0;
    return () => {
      s = (s + 0x6d2b79f5) >>> 0;
      let t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function makeDots(lag) {
    const rand = random(1965);
    // Filing order: each dot draws a lag from the real histogram of House filing delays.
    const lags = [];
    if (lag) {
      const total = lag.bins.reduce((s, b) => s + b.trades, 0);
      for (const b of lag.bins) {
        const n = Math.round((b.trades / total) * N);
        for (let k = 0; k < n; k += 1) lags.push(Math.min(b.from + rand() * 5, 90) / 90);
      }
    }
    while (lags.length < N) lags.push(rand());
    lags.sort(() => rand() - 0.5);
    dots = Array.from({ length: N }, (_, i) => ({
      p: ((i + 0.5) / N) * 100,
      u: rand(),
      g: rand(),
      fall: rand(),
      lag: lags[i],
    }));
    // Each dot's value and local spacing on every whole day, computed once.
    dotValue = [];
    dotSpan = [];
    for (let day = 0; day < path.length; day += 1) {
      const ps = path[day].p;
      const values = new Float32Array(N);
      const spans = new Float32Array(N);
      for (let i = 0; i < N; i += 1) {
        const p = dots[i].p;
        values[i] = quantile(p, ps);
        spans[i] = Math.abs(quantile(Math.min(99.5, p + 0.6), ps) - quantile(Math.max(0.5, p - 0.6), ps));
      }
      dotValue.push(values);
      dotSpan.push(spans);
    }
  }

  function layout() {
    if (!canvas || !ctx) return null;
    const rect = canvas.getBoundingClientRect();
    const W = rect.width;
    const H = rect.height;
    if (!W || !H) return null;
    const dpr = Math.min(window.devicePixelRatio || 1, W < 520 ? 1.5 : 2);
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const narrow = W < 520;
    const left = narrow ? 38 : 56;
    const right = narrow ? 10 : 20;
    const top = narrow ? 30 : 56;
    const bottom = narrow ? 26 : 46;
    const zeroY = domeWrap ? domeWrap.offsetTop : H * 0.52;
    const half = Math.min(zeroY - top, H - bottom - zeroY);
    const css = getComputedStyle(document.documentElement);
    colors = {
      ink: css.getPropertyValue('--ink').trim(),
      muted: css.getPropertyValue('--muted').trim(),
      line: css.getPropertyValue('--line').trim(),
      accent: css.getPropertyValue('--accent').trim(),
      ground: css.getPropertyValue('--ground').trim(),
    };
    return {
      W, H, narrow, left, right, top, bottom, zeroY, half,
      x: (day) => left + fraction(day) * (W - left - right),
      dot: narrow ? 1.5 : 1.8,
    };
  }

  const range = () => Math.exp(lerp(Math.log(RANGE_WIDE), Math.log(RANGE_ZOOM), smooth(state.zoom)));

  function ticks(r) {
    const raw = r / 2.2;
    const mag = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw);
    const out = [];
    for (let v = step; v < r * 0.98; v += step) out.push(v, -v);
    return { step, values: out };
  }

  function font(size, weight = 500) {
    return `${weight} ${size}px 'Public Sans', system-ui, sans-serif`;
  }

  // Text on a ground-colored box, so grid and marker lines never run through a label.
  // haloAlpha lets a dimmed label keep a solid halo.
  function label(content, x, y, haloAlpha) {
    ctx.save();
    if (haloAlpha !== undefined) ctx.globalAlpha = haloAlpha;
    const m = ctx.measureText(content);
    const left = ctx.textAlign === 'right' ? x - m.width : ctx.textAlign === 'center' ? x - m.width / 2 : x;
    ctx.fillStyle = colors.ground;
    ctx.fillRect(left - 3, y - m.actualBoundingBoxAscent - 3, m.width + 6, m.actualBoundingBoxAscent + m.actualBoundingBoxDescent + 6);
    ctx.restore();
    ctx.fillText(content, x, y);
  }

  function draw() {
    if (!geo) return;
    const g = geo;
    const { day, intro, zoom } = state;
    const r = range();
    const y = (v) => g.zeroY - (v / r) * g.half;
    const yTop = g.zeroY - g.half;
    const yBottom = g.zeroY + g.half;
    ctx.clearRect(0, 0, g.W, g.H);

    // Axes, estimation window, grid and labels fade in as the dome sinks.
    ctx.globalAlpha = intro;
    ctx.fillStyle = colors.line;
    ctx.globalAlpha = intro * 0.45;
    ctx.fillRect(g.x(-250), yTop, g.x(-30) - g.x(-250), yBottom - yTop);
    ctx.globalAlpha = intro;
    ctx.font = font(g.narrow ? 11 : 13);
    ctx.fillStyle = colors.muted;
    ctx.textAlign = 'left';
    if (!g.narrow) {
      // Keep the caption inside the shaded window: one line if it fits, else two.
      const caption = 'Model fit, days −250 to −30';
      const room = g.x(-30) - g.x(-250) - 16;
      if (ctx.measureText(caption).width <= room) ctx.fillText(caption, g.x(-250) + 8, yTop + 18);
      else {
        ctx.fillText('Model fit,', g.x(-250) + 8, yTop + 18);
        ctx.fillText('days −250 to −30', g.x(-250) + 8, yTop + 36);
      }
    }
    const t = ticks(r);
    ctx.textAlign = 'right';
    for (const v of t.values) {
      const yy = y(v);
      ctx.strokeStyle = colors.line;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(g.left, yy);
      ctx.lineTo(g.W - g.right, yy);
      ctx.stroke();
      const digits = t.step < 0.01 ? 1 : 0;
      ctx.fillText(`${signed(v * 100, digits)}%`, g.left - 8, yy + 4);
    }
    ctx.fillStyle = colors.ink;
    ctx.font = font(g.narrow ? 11 : 13, 650);
    ctx.fillText('0%', g.left - 8, g.zeroY + 4);
    ctx.font = font(g.narrow ? 11 : 13);
    ctx.fillStyle = colors.muted;
    ctx.textAlign = 'center';
    for (const d of [-250, -30, 0, 20, 62, 125]) {
      // The last tick sits on the plot's right edge, so it ends there instead of centering.
      ctx.textAlign = d === 125 ? 'right' : 'center';
      ctx.fillText(signed(d), d === 125 ? g.W - 2 : g.x(d), yBottom + (g.narrow ? 18 : 26));
    }
    if (!g.narrow) {
      ctx.textAlign = 'right';
      ctx.fillText('Trading days from disclosure', g.W - g.right, yBottom + 42);
    }
    const gapX = g.left + 0.165 * (g.W - g.left - g.right);
    ctx.strokeStyle = colors.muted;
    ctx.beginPath();
    ctx.moveTo(gapX - 5, g.zeroY + 6);
    ctx.lineTo(gapX + 1, g.zeroY - 6);
    ctx.moveTo(gapX + 1, g.zeroY + 6);
    ctx.lineTo(gapX + 7, g.zeroY - 6);
    ctx.stroke();

    for (const m of MARKERS) {
      const on = day >= m.day - 0.5;
      ctx.globalAlpha = intro * (on ? 1 : 0.3);
      ctx.strokeStyle = m.accent ? colors.accent : colors.ink;
      ctx.lineWidth = m.strong || m.accent ? 1.5 : 1;
      ctx.setLineDash(m.strong || m.accent ? [] : [2, 4]);
      ctx.beginPath();
      ctx.moveTo(g.x(m.day), yTop);
      ctx.lineTo(g.x(m.day), yBottom);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    // Labels go in a second pass so no later marker line crosses an earlier label.
    for (const m of MARKERS) {
      ctx.globalAlpha = intro * (day >= m.day - 0.5 ? 1 : 0.3);
      if (!g.narrow || m.strong || m.accent) {
        // Labels sit right of their line, except before day 0 and at the plot's right edge.
        const flip = m.day < 0 || m.day === 125;
        ctx.textAlign = flip ? 'right' : 'left';
        ctx.font = font(g.narrow ? 11 : 13, m.strong || m.accent ? 650 : 500);
        ctx.fillStyle = m.accent ? colors.accent : m.strong ? colors.ink : colors.muted;
        label(g.narrow && m.accent ? '+62' : m.label, g.x(m.day) + (flip ? -7 : 7), yTop + (m.day < 0 ? 38 : 18), intro);
      }
    }

    // The spread across purchases up to today: 10th to 90th and 25th to 75th percentiles.
    const upTo = Math.max(0, day);
    ctx.save();
    ctx.beginPath();
    ctx.rect(g.left, yTop, g.W - g.left, yBottom - yTop);
    ctx.clip();
    if (path.length && upTo > 0) {
      const days = [];
      for (let d = 0; d < upTo; d += 1) days.push(d);
      days.push(upTo);
      const fade = 1 - smooth(clamp(zoom * 1.4));
      const fan = (lo, hi, alpha) => {
        if (alpha <= 0.002) return;
        ctx.globalAlpha = alpha * intro;
        ctx.fillStyle = colors.ink;
        ctx.beginPath();
        days.forEach((d, i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, g.x(d), y(spreadAt(d, hi))));
        for (let i = days.length - 1; i >= 0; i -= 1) ctx.lineTo(g.x(days[i]), y(spreadAt(days[i], lo)));
        ctx.closePath();
        ctx.fill();
      };
      fan(10, 90, 0.06 * fade);
      fan(25, 75, 0.09 * fade);

      // The 95% band around the mean; it only becomes readable once zoomed in.
      ctx.globalAlpha = intro * (0.12 + 0.14 * smooth(zoom));
      ctx.fillStyle = colors.accent;
      ctx.beginPath();
      days.forEach((d, i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, g.x(d), y(at(d, 'mean') + 1.96 * at(d, 'se'))));
      for (let i = days.length - 1; i >= 0; i -= 1) ctx.lineTo(g.x(days[i]), y(at(days[i], 'mean') - 1.96 * at(days[i], 'se')));
      ctx.closePath();
      ctx.fill();

      ctx.globalAlpha = intro;
      ctx.strokeStyle = colors.accent;
      ctx.lineWidth = 2.5;
      ctx.lineJoin = 'round';
      ctx.beginPath();
      days.forEach((d, i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, g.x(d), y(at(d, 'mean'))));
      ctx.stroke();
    }
    ctx.restore();

    // The zero line: the ground the dome stands on.
    ctx.globalAlpha = 1;
    ctx.strokeStyle = colors.ink;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(lerp(0, g.left, intro), g.zeroY);
    ctx.lineTo(g.W, g.zeroY);
    ctx.stroke();

    drawDots(g, y);

    // Readouts at today's position.
    if (path.length && day > 0.5) {
      const cx = g.x(day);
      const mean = at(day, 'mean');
      ctx.globalAlpha = intro;
      ctx.fillStyle = colors.accent;
      ctx.beginPath();
      ctx.arc(cx, y(mean), 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = colors.ground;
      ctx.lineWidth = 2;
      ctx.stroke();
      const cloud = (1 - smooth(zoom)) * (g.narrow ? 36 : 76);
      const right = cx + cloud > g.W - (g.narrow ? 100 : 190);
      ctx.textAlign = right ? 'right' : 'left';
      const dx = right ? -12 - cloud : 12 + cloud;
      ctx.font = font(g.narrow ? 12 : 14, 700);
      ctx.fillStyle = colors.accent;
      // Put the mean on the side of its dot away from the zero line, haloed against the band.
      label(`Mean ${signed(mean * 100, 2)}%`, cx + dx, y(mean) + (mean < 0 ? 20 : -12));
      if (!g.narrow && zoom < 0.5) {
        ctx.font = font(13, 500);
        ctx.fillStyle = colors.muted;
        ctx.globalAlpha = intro * (1 - zoom * 2);
        label(`Middle half: ${signed(spreadAt(day, 25) * 100, 1)}% to ${signed(spreadAt(day, 75) * 100, 1)}%`, cx + dx, y(spreadAt(day, 75)) - 10);
      }
    }
    ctx.globalAlpha = 1;
  }

  function drawDots(g, y) {
    if (!dots.length) return;
    const { day, fall, zoom } = state;
    const width = g.x(125) - g.x(-250);
    const gather = clamp((day + 30) / 30);
    const after = day > 0 && dotValue.length;
    const today = after ? Math.min(day, dotValue.length - 1) : 0;
    const d0 = Math.min(Math.floor(today), Math.max(dotValue.length - 2, 0));
    const f1 = today - d0;
    const v0 = dotValue[d0];
    const v1 = dotValue[Math.min(d0 + 1, dotValue.length - 1)];
    const s0 = dotSpan[d0];
    const r = range();
    const pxPerValue = g.half / r;
    const maxW = g.narrow ? 70 : 150;
    const cx0 = g.x(today);
    const groundY = g.zeroY - g.dot - 0.5;
    const s = g.dot;
    const alpha = 0.72 * (1 - smooth(clamp(zoom * 1.25)));
    if (alpha <= 0.01) return;
    const yTop = g.zeroY - g.half;
    const yBottom = g.zeroY + g.half;
    ctx.globalAlpha = alpha;
    ctx.fillStyle = colors.ink;
    ctx.beginPath();
    for (let i = 0; i < dots.length; i += 1) {
      const d = dots[i];
      let x = g.x(-250) + d.g * width;
      let yy = groundY - (i % 3) * (s + 0.4);
      const f = clamp(fall * 1.7 - d.fall * 0.7);
      if (f < 1) yy = lerp(-20 - d.u * g.H * 0.5, yy, f * f);
      const h = after ? 1 : smooth(clamp((gather - d.lag * 0.8) / 0.2));
      if (h > 0 && v0) {
        const value = lerp(v0[i], v1[i], f1);
        const perPx = ((1.2 / 100) * N) / Math.max(s0[i] * pxPerValue, 0.4);
        const w = Math.min(maxW, Math.max(3, perPx * s * s * 1.6));
        x = lerp(x, cx0 + (d.u - 0.5) * w, h);
        yy = lerp(yy, g.zeroY - value * pxPerValue, h);
      }
      if (h > 0 && (yy < yTop || yy > yBottom)) continue;
      if (yy < -10 || yy > g.H + 10) continue;
      ctx.rect(x - s / 2, yy - s / 2, s, s);
    }
    ctx.fill();
    ctx.globalAlpha = 1;
  }

  function render() {
    draw();
    if (domeWrap) {
      dome.style.translate = `0 ${(state.intro * 100).toFixed(2)}%`;
      domeWrap.style.opacity = String(1 - state.intro * 0.4);
    }
    if (counter) counter.textContent = signed(Math.round(state.day));
  }

  function mount() {
    geo = layout();
    render();
  }

  // ---------------------------------------------------------------- driver

  function driveTimeline() {
    const units = [...document.querySelectorAll('.unit[data-from]')];
    if (!gsap || !ScrollTrigger) {
      Object.assign(state, { day: 125, intro: 1, zoom: 1 });
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
            state.zoom = Number(unit.dataset.zoom || 0);
            render();
          },
        });
      }
      return;
    }

    const toDay = gsap.quickTo(state, 'day', { duration: 0.6, ease: 'power3.out', onUpdate: render });
    const toZoom = gsap.quickTo(state, 'zoom', { duration: 0.8, ease: 'power3.out', onUpdate: render });
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
      const zoomFrom = Number(unit.dataset.zoomFrom || unit.dataset.zoom || 0);
      const zoomTo = Number(unit.dataset.zoom || 0);
      ScrollTrigger.create({
        trigger: unit,
        start: 'top 55%',
        end: 'bottom 55%',
        onUpdate: (self) => {
          toDay(lerp(from, to, self.progress));
          toZoom(lerp(zoomFrom, zoomTo, clamp(self.progress * 1.6)));
        },
        onEnterBack: () => {
          toDay(to);
          toZoom(zoomTo);
        },
      });
    }
    ScrollTrigger.create({
      trigger: '#question',
      start: 'top top',
      end: 'bottom 55%',
      onEnterBack: () => {
        toDay(-250);
        toZoom(0);
      },
    });

  }

  // ---------------------------------------------------------------- intro

  // The head script adds html.motion, which hides the intro targets before first paint.
  function intro() {
    const root = document.documentElement;
    if (!animate) {
      root.classList.remove('motion');
      state.fall = 1;
      render();
      return;
    }
    const strokes = dome ? [...dome.querySelectorAll('[data-draw]')] : [];
    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });
    gsap.set(strokes, { strokeDasharray: 1, strokeDashoffset: 1 });
    state.fall = 0;
    root.classList.remove('motion');
    tl.to(strokes, { strokeDashoffset: 0, duration: 1.2, ease: 'power2.inOut', stagger: 0.06 }, 0.1);
    tl.to(state, { fall: 1, duration: 2.2, ease: 'none', onUpdate: render }, 0.2);
    tl.fromTo('.no', { yPercent: 40, opacity: 0 }, { yPercent: 0, opacity: 1, duration: 1.1 }, 0.7);
    tl.fromTo('.unit--question .byline, .unit--question .scroll-cue',
      { y: 18, opacity: 0 }, { y: 0, opacity: 1, duration: 0.8, stagger: 0.08 }, 0.95);
    const h1 = document.querySelector('.question');
    if (h1 && SplitText) {
      SplitText.create(h1, {
        type: 'lines', mask: 'lines', autoSplit: true,
        onSplit: (self) => gsap.from(self.lines, { yPercent: 105, duration: 1, stagger: 0.08, ease: 'power3.out', delay: 0.1 }),
      });
    }
  }

  // Unit copy: headings and stats slide up out of a mask as each unit arrives.
  function reveals() {
    if (!animate || !SplitText) return;
    for (const unit of document.querySelectorAll('.unit:not(.unit--question), .block')) {
      const heads = unit.querySelectorAll('h2');
      for (const h of heads) {
        SplitText.create(h, {
          type: 'lines', mask: 'lines', autoSplit: true,
          onSplit: (self) => gsap.from(self.lines, {
            yPercent: 105, duration: 0.9, stagger: 0.07, ease: 'power3.out',
            scrollTrigger: { trigger: h, start: 'top 82%', once: true },
          }),
        });
      }
      const stat = unit.querySelector('.stat');
      if (stat) {
        gsap.from(stat, {
          yPercent: 30, opacity: 0, duration: 0.9, ease: 'power3.out',
          scrollTrigger: { trigger: stat, start: 'top 85%', once: true },
        });
      }
    }
  }

  // ---------------------------------------------------------------- filing

  function filing(lag) {
    const art = document.querySelector('.filing__art');
    if (art && typeof art.pauseAnimations === 'function' && !art.dataset.bound) {
      art.dataset.bound = 'true';
      const ms = Number(art.dataset.glaxMs);
      art.pauseAnimations();
      if (!animate) {
        art.setCurrentTime(ms / 1000);
      } else {
        const t = { ms: 0 };
        art.setCurrentTime(0);
        gsap.to(t, {
          ms, ease: 'none',
          scrollTrigger: { trigger: '.filing', start: 'top 85%', end: 'top 30%', scrub: 0.4 },
          onUpdate: () => art.setCurrentTime(t.ms / 1000),
        });
      }
    }

    const svg = document.querySelector('.lags__chart');
    if (!svg || !lag) return;
    svg.replaceChildren();
    const W = svg.clientWidth;
    const H = svg.clientHeight;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    const bins = lag.bins;
    const max = Math.max(...bins.map((b) => b.trades));
    const gap = 2;
    const bw = (W - gap * (bins.length - 1)) / bins.length;
    const base = H - 22;
    const bars = bins.map((b, i) => {
      const h = Math.max(1, (b.trades / max) * (base - 22));
      return el('rect', {
        x: i * (bw + gap), y: base - h, width: bw, height: h,
        fill: b.from >= lag.deadline_days ? 'var(--accent)' : 'var(--ink)',
      }, svg);
    });
    const deadline = bins.findIndex((b) => b.from >= lag.deadline_days);
    const dx = deadline * (bw + gap) - gap / 2;
    const rule = el('line', { x1: dx, x2: dx, y1: 4, y2: base, stroke: 'var(--accent)', 'stroke-width': 1.5, 'stroke-dasharray': '3 3' }, svg);
    text(svg, dx + 6, 14, `${lag.deadline_days}-day deadline`, { class: 'lbl-accent' });
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
    const rowH = narrow ? 46 : 50;
    const H = rows.length * rowH + 40;
    svg.style.height = `${H}px`;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    const labelW = narrow ? 0 : Math.min(280, W * 0.42);
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
    const marks = [];
    rows.forEach((r, i) => {
      if (r.alpha_annual === null) return;
      const se = Math.abs(r.alpha_annual / r.t);
      const lo = r.alpha_annual - 1.96 * se;
      const hi = r.alpha_annual + 1.96 * se;
      const cy = i * rowH + (narrow ? 32 : rowH / 2 + 4);
      const label = r.check.replace('Primary: ', 'Primary, ');
      if (narrow) text(svg, 0, cy - 12, label, { class: i === 0 ? 'lbl-strong' : '' });
      else text(svg, 0, cy + 4, label, { class: i === 0 ? 'lbl-strong' : '' });
      bars.push(el('line', {
        x1: x(Math.max(lo, -span)), x2: x(Math.min(hi, span)), y1: cy, y2: cy,
        stroke: i === 0 ? 'var(--accent)' : 'var(--ink)', 'stroke-width': i === 0 ? 3.5 : 2, 'stroke-linecap': 'round',
      }, svg));
      marks.push(el('circle', {
        cx: x(r.alpha_annual), cy, r: i === 0 ? 6.5 : 4.5,
        fill: i === 0 ? 'var(--accent)' : 'var(--ground)', stroke: i === 0 ? 'var(--accent)' : 'var(--ink)', 'stroke-width': 2,
      }, svg));
    });
    if (animate) {
      const tl = gsap.timeline({ scrollTrigger: { trigger: svg, start: 'top 80%', once: true } });
      tl.from(zero, { attr: { y2: 4 }, duration: 0.6, ease: 'power2.inOut' })
        .from(bars, { scaleX: 0, transformOrigin: '50% 50%', duration: 0.7, ease: 'power3.out', stagger: 0.06 }, 0.3)
        .from(marks, { opacity: 0, attr: { r: 0 }, duration: 0.4, ease: 'back.out(2)', stagger: 0.06 }, 0.45);
    }
  }

  // ---------------------------------------------------------------- counts

  function counts() {
    if (!animate) return;
    for (const node of document.querySelectorAll('[data-count]')) {
      const end = Number(node.dataset.count);
      const digits = Number(node.dataset.digits || 0);
      const sign = node.dataset.sign === 'true';
      const format = (v) => {
        const body = Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
        if (!sign || Number(Math.abs(v).toFixed(digits)) === 0) return body;
        return (v < 0 ? MINUS : '+') + body;
      };
      const t = { v: 0 };
      gsap.to(t, {
        v: end, duration: 1.4, ease: 'power2.out',
        scrollTrigger: { trigger: node, start: 'top 85%', once: true },
        onUpdate: () => { node.textContent = format(t.v); },
      });
    }
  }

  // ---------------------------------------------------------------- start

  function start(figures) {
    window.clearTimeout(window.__introGuard);
    if (figures) path = figures.car_disclosure;
    makeDots(figures && figures.lag);
    mount();
    driveTimeline();
    intro();
    reveals();
    counts();
    filing(figures && figures.lag);
    forest(figures && figures.robustness);
    if (document.fonts) document.fonts.ready.then(render);

    // Remeasure when the window width or the canvas size changes; a height-only window
    // resize changes the canvas on desktop, while a phone's toolbar (svh units) does not.
    let size = '';
    const resize = () => {
      const rect = canvas ? canvas.getBoundingClientRect() : { width: 0, height: 0 };
      const next = `${window.innerWidth}x${Math.round(rect.width)}x${Math.round(rect.height)}`;
      if (next === size && geo) return;
      size = next;
      mount();
      forest(figures && figures.robustness);
      filing(figures && figures.lag);
      if (ScrollTrigger) ScrollTrigger.refresh();
    };
    if (window.ResizeObserver && stage) new ResizeObserver(() => resize()).observe(document.body);
  }

  fetch('/data/figures.json')
    .then((response) => (response.ok ? response.json() : null))
    .catch(() => null)
    .then(start);
})();
