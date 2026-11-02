(function () {
  const $ = (s, c = document) => c.querySelector(s);
  const $$ = (s, c = document) => Array.from(c.querySelectorAll(s));

  // Off-canvas menu
  const openOC = () => { document.body.classList.add("oc-open"); $("#offcanvas").setAttribute("aria-hidden", "false"); };
  const closeOC = () => { document.body.classList.remove("oc-open"); $("#offcanvas").setAttribute("aria-hidden", "true"); };
  $("#burger")?.addEventListener("click", openOC);
  $("#ocClose")?.addEventListener("click", closeOC);
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
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (!e.isIntersecting) return;
      const el = e.target, target = +el.dataset.count, pre = el.dataset.prefix || "";
      const t0 = performance.now();
      const tick = (t) => {
        const p = Math.min((t - t0) / 1400, 1);
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
    });
    lb.addEventListener("click", () => { lb.hidden = true; });
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
  bt?.addEventListener("click", () => scrollTo({ top: 0 }));
})();
