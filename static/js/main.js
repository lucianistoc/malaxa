(function () {
  const $ = (s, c = document) => c.querySelector(s);
  // Honour the OS "Reduce Motion" setting (Apple HIG): skip decorative animation, keep state changes.
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const $$ = (s, c = document) => Array.from(c.querySelectorAll(s));

  // Off-canvas menu
  const openOC = () => { document.body.classList.add("oc-open"); $("#offcanvas").setAttribute("aria-hidden", "false"); };
  const closeOC = () => { document.body.classList.remove("oc-open"); $("#offcanvas").setAttribute("aria-hidden", "true"); };
  $("#burger")?.addEventListener("click", openOC);
  $("#ocClose")?.addEventListener("click", closeOC);
  $("#ocSearch")?.addEventListener("click", () => {
    closeOC();
    const sp = $("#searchPanel"); sp.classList.add("open");
    $("#searchToggle")?.setAttribute("aria-expanded", "true");
    $("input", sp).focus();
  });
  $("#ocBackdrop")?.addEventListener("click", closeOC);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeOC(); });

  // Search panel
  const st = $("#searchToggle"), sp = $("#searchPanel");
  st?.addEventListener("click", () => {
    const open = sp.classList.toggle("open");
    st.setAttribute("aria-expanded", open);
    if (open) $("input", sp).focus();
  });

  // Tabs
  $$("[data-tabs]").forEach((wrap) => {
    const btns = $$("[role=tab]", wrap);
    btns.forEach((b) => b.addEventListener("click", () => {
      btns.forEach((x) => { x.setAttribute("aria-selected", x === b); $("#" + x.getAttribute("aria-controls")).hidden = x !== b; });
    }));
  });

  // Doctor filter
  const filters = $("#teamFilters");
  if (filters) {
    filters.addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      $$("button", filters).forEach((x) => x.classList.toggle("active", x === b));
      const f = b.dataset.filter;
      $$(".team-group").forEach((g) => { g.hidden = f !== "all" && g.dataset.group !== f; });
    });
  }

  // Animated counters
  const fmt = (n) => n.toLocaleString("ro-RO");
  if ("IntersectionObserver" in window && !reduceMotion.matches) {
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (!e.isIntersecting) return;
      const el = e.target, target = +el.dataset.count, pre = el.dataset.prefix || "";
      const t0 = performance.now();
      const tick = (t) => {
        const p = Math.min((t - t0) / 800, 1); // brief: under a second, decelerating
        el.textContent = pre + fmt(Math.round(target * (1 - Math.pow(1 - p, 3))));
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick); io.unobserve(el);
    }), { threshold: .3 });
    $$("[data-count]").forEach((el) => io.observe(el));
  } else {
    $$("[data-count]").forEach((el) => el.textContent = (el.dataset.prefix || "") + fmt(+el.dataset.count));
  }

  // Front-end only forms: replace with your backend / form service endpoint (set data-endpoint on the form).
  $$("form[data-form]").forEach((f) => f.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = $(".form-msg", f);
    if (!f.checkValidity()) { f.reportValidity(); return; }
    const endpoint = f.dataset.endpoint;
    try {
      if (endpoint) await fetch(endpoint, { method: "POST", body: new FormData(f) });
      if (msg) msg.textContent = f.dataset.success || "Mulțumim! Mesajul a fost trimis.";
      f.reset();
    } catch (err) { if (msg) msg.textContent = "A apărut o eroare. Vă rugăm încercați din nou."; }
  }));

  // Site search (uses search-index.json)
  const results = $("#searchResults");
  if (results) {
    const q = new URLSearchParams(location.search).get("q") || "";
    $("#searchPageInput").value = q;
    fetch(results.dataset.index).then((r) => r.json()).then((idx) => {
      const terms = q.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").split(/\s+/).filter(Boolean);
      const hits = terms.length ? idx.filter((p) => terms.every((t) => p.text.includes(t))) : [];
      results.innerHTML = hits.length
        ? hits.map((h) => `<a href="${results.dataset.root}${h.url}"><strong>${h.title}</strong><br><small>${h.section}</small></a>`).join("")
        : `<p class="muted">${q ? "Nu am găsit rezultate pentru „" + q.replace(/</g, "&lt;") + "”." : "Introduceți un termen de căutare."}</p>`;
    }).catch(() => { results.innerHTML = '<p class="muted">Căutarea necesită un server web (nu funcționează din file://).</p>'; });
  }

  // Accessibility panel
  const ab = $("#a11yBtn"), ap = $("#a11yPanel");
  let fs = 100;
  ab?.addEventListener("click", () => { const o = ap.classList.toggle("open"); ab.setAttribute("aria-expanded", o); });
  ap?.addEventListener("click", (e) => {
    const a = e.target.dataset.a11y; if (!a) return;
    if (a === "plus") fs = Math.min(fs + 10, 150);
    if (a === "minus") fs = Math.max(fs - 10, 80);
    if (a === "reset") { fs = 100; document.body.classList.remove("a11y-contrast", "a11y-links", "a11y-grayscale"); }
    if (["contrast", "links", "grayscale"].includes(a)) document.body.classList.toggle("a11y-" + a);
    document.documentElement.style.fontSize = fs + "%";
    document.body.style.fontSize = (15 * fs / 100) + "px";
  });

  // Lightbox for galleries
  const lb = $("#lightbox");
  if (lb) {
    document.addEventListener("click", (e) => {
      const a = e.target.closest("a[data-lightbox]"); if (!a) return;
      e.preventDefault(); $("img", lb).src = a.href; lb.hidden = false;
      requestAnimationFrame(() => requestAnimationFrame(() => lb.classList.add("open")));
    });
    const closeLb = () => {
      lb.classList.remove("open");
      setTimeout(() => { if (!lb.classList.contains("open")) lb.hidden = true; }, reduceMotion.matches ? 0 : 260);
    };
    lb.addEventListener("click", closeLb);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !lb.hidden) closeLb(); });
  }

  // Price list filter
  const pf = $("#priceFilter");
  pf?.addEventListener("input", () => {
    const q = pf.value.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    $$("#priceAccordion details").forEach((d) => {
      let hits = 0;
      $$("tbody tr", d).forEach((tr) => {
        const ok = !q || tr.textContent.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").includes(q);
        tr.hidden = !ok; if (ok) hits++;
      });
      d.hidden = q && !hits; d.open = !!q && hits > 0;
    });
  });

  // Public-interest tiles open their documents panel
  $$("a[data-open]").forEach((a) => a.dataset.open && a.addEventListener("click", () => {
    const d = document.getElementById(a.dataset.open); if (d) d.open = true;
  }));
  if (location.hash.startsWith("#doc-")) { const d = $(location.hash); if (d) d.open = true; }

  // Back to top
  const bt = $("#backTop");
  addEventListener("scroll", () => bt?.classList.toggle("show", scrollY > 600), { passive: true });
  bt?.addEventListener("click", () => scrollTo({ top: 0, behavior: reduceMotion.matches ? "auto" : "smooth" }));

  // Site-rendered scrollbars: the native bars are hidden (only once this script runs, so without JS the browser's
  // own bars stay) and replaced with thin overlay bars that fade in while scrolling. Wheel, touch and keyboard
  // scrolling are untouched; the bars can also be dragged, and clicking the track jumps there.
  const SCROLL_AREAS = ".side-menu ul, .doc-list.scroll, .offcanvas, .table-wrap";
  if (CSS.supports("scrollbar-width", "none") || CSS.supports("selector(::-webkit-scrollbar)")) {
    document.documentElement.classList.add("site-scrollbars");
    const bars = [];
    const page = document.scrollingElement || document.documentElement;
    const metrics = (b) => {
      const el = b.el || page, v = b.axis === "y";
      return {
        size: v ? el.clientHeight : el.clientWidth,
        total: v ? el.scrollHeight : el.scrollWidth,
        pos: v ? el.scrollTop : el.scrollLeft,
      };
    };
    const place = (b) => {
      const { size, total, pos } = metrics(b);
      if (b.el) {
        const r = b.el.getBoundingClientRect();
        const offscreen = !r.width || !r.height || r.bottom <= 0 || r.top >= innerHeight || r.right <= 0 || r.left >= innerWidth;
        b.track.hidden = offscreen || total <= size + 1;
        if (b.track.hidden) return;
        Object.assign(b.track.style, b.axis === "y"
          ? { top: r.top + 4 + "px", left: r.right - 14 + "px", height: r.height - 8 + "px", width: "" }
          : { left: r.left + 4 + "px", top: r.bottom - 14 + "px", width: r.width - 8 + "px", height: "" });
      } else {
        b.track.hidden = total <= size + 1;
        if (b.track.hidden) return;
      }
      const len = b.axis === "y" ? b.track.clientHeight : b.track.clientWidth;
      const thumb = Math.max(32, Math.round(len * size / total));
      const offset = (len - thumb) * (pos / (total - size));
      b.thumb.style[b.axis === "y" ? "height" : "width"] = thumb + "px";
      b.thumb.style.transform = b.axis === "y" ? "translateY(" + offset + "px)" : "translateX(" + offset + "px)";
      b.thumbLen = thumb; b.trackLen = len;
      if (!b.el) b.track.classList.toggle("sb-light", isDarkAt(innerWidth - 8, b.track.getBoundingClientRect().top + offset + thumb / 2));
    };
    // The page bar has no outline, so it switches to a light thumb over dark sections (hero, stats, footer), like macOS.
    const isDarkAt = (x, y) => {
      const under = document.elementsFromPoint(x, y).find((n) => !n.closest(".sb"));
      for (let n = under; n && n !== document.documentElement; n = n.parentElement) {
        const c = getComputedStyle(n);
        if (c.backgroundImage !== "none" && /hero|footer/.test(n.className)) return true; // photo/pattern backgrounds are dark
        const m = c.backgroundColor.match(/[\d.]+/g);
        if (m && (m[3] === undefined || +m[3] > .5)) {
          const [r, g, bl] = m.map(Number);
          return (0.2126 * r + 0.7152 * g + 0.0722 * bl) / 255 < 0.45;
        }
      }
      return false;
    };
    const reveal = (b) => {
      b.track.classList.add("on");
      clearTimeout(b.timer);
      b.timer = setTimeout(() => { if (!b.hover && !b.drag) b.track.classList.remove("on"); }, 1000);
    };
    const scrollAreaTo = (b, value) => {
      const opts = { [b.axis === "y" ? "top" : "left"]: value, behavior: "instant" };
      (b.el || window).scrollTo(opts);
    };
    const make = (el, axis) => {
      const track = document.createElement("div");
      track.className = "sb sb-" + axis + (el ? "" : " sb-page") + (el && el.closest(".side-menu") ? " sb-light" : "");
      track.setAttribute("aria-hidden", "true");
      const thumb = document.createElement("div");
      thumb.className = "sb-thumb";
      track.append(thumb);
      document.body.append(track);
      const b = { el, axis, track, thumb };
      track.addEventListener("pointerenter", () => { b.hover = true; reveal(b); });
      track.addEventListener("pointerleave", () => { b.hover = false; reveal(b); });
      thumb.addEventListener("pointerdown", (e) => {
        e.preventDefault(); e.stopPropagation();
        thumb.setPointerCapture(e.pointerId);
        b.drag = { start: b.axis === "y" ? e.clientY : e.clientX, pos: metrics(b).pos };
        track.classList.add("drag");
      });
      thumb.addEventListener("pointermove", (e) => {
        if (!b.drag) return;
        const { size, total } = metrics(b);
        const delta = (b.axis === "y" ? e.clientY : e.clientX) - b.drag.start;
        scrollAreaTo(b, b.drag.pos + delta * (total - size) / Math.max(1, b.trackLen - b.thumbLen));
      });
      const endDrag = () => { b.drag = null; track.classList.remove("drag"); reveal(b); };
      thumb.addEventListener("pointerup", endDrag);
      thumb.addEventListener("pointercancel", endDrag);
      track.addEventListener("pointerdown", (e) => {
        if (e.target !== track) return;
        const r = track.getBoundingClientRect();
        const at = b.axis === "y" ? e.clientY - r.top : e.clientX - r.left;
        const { size, total } = metrics(b);
        scrollAreaTo(b, (at - b.thumbLen / 2) / Math.max(1, b.trackLen - b.thumbLen) * (total - size));
      });
      (el || window).addEventListener("scroll", () => { place(b); reveal(b); }, { passive: true });
      bars.push(b);
      place(b);
      return b;
    };

    const pageBar = make(null, "y");
    $$(SCROLL_AREAS).forEach((el) => make(el, el.matches(".table-wrap") ? "x" : "y"));

    // Keep inner bars glued to their boxes when the page scrolls, resizes or content opens/closes.
    let queued = false;
    const refresh = () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; bars.forEach(place); });
    };
    addEventListener("scroll", refresh, { passive: true });
    addEventListener("resize", refresh);
    if ("ResizeObserver" in window) {
      const ro = new ResizeObserver(refresh);
      ro.observe(document.body);
      bars.forEach((b) => b.el && ro.observe(b.el));
    }
    document.addEventListener("toggle", refresh, true);           // <details> open/close
    $("#offcanvas")?.addEventListener("transitionend", refresh);   // side panel finished sliding
    // Mouse near the right edge reveals the page bar, like macOS overlay scrollbars.
    addEventListener("pointermove", (e) => { if (e.pointerType === "mouse" && e.clientX > innerWidth - 24) reveal(pageBar); }, { passive: true });
  }
})();
