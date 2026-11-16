/* DevShop client — search, filters, saved list, theme, PWA. No dependencies. */
(() => {
  "use strict";
  const BASE = (document.currentScript?.src || "").replace(/\/assets\/app\.js.*$/, "").replace(location.origin, "");
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const store = {
    get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
  };
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* ---------- Toast ---------- */
  let toastEl;
  function toast(msg) {
    if (!toastEl) { toastEl = document.createElement("div"); toastEl.className = "toast"; toastEl.setAttribute("role", "status"); document.body.appendChild(toastEl); }
    toastEl.textContent = msg; toastEl.classList.add("show");
    clearTimeout(toast.t); toast.t = setTimeout(() => toastEl.classList.remove("show"), 2200);
  }
  async function copy(text, msg = "Link copied") {
    try { await navigator.clipboard.writeText(text); toast(msg); } catch { prompt("Copy this:", text); }
  }

  /* ---------- Theme ---------- */
  const root = document.documentElement;
  $("#theme-toggle")?.addEventListener("click", () => {
    const dark = root.dataset.theme === "dark" || (root.dataset.theme !== "light" && matchMedia("(prefers-color-scheme: dark)").matches);
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("ds-theme", root.dataset.theme); } catch {}
  });

  /* ---------- Saved ---------- */
  let saved = new Set(store.get("ds-saved", []));
  function syncSaved() {
    $$("[data-saved-count]").forEach((el) => (el.textContent = saved.size));
    $$("[data-save]").forEach((b) => {
      const on = saved.has(+b.dataset.save);
      b.setAttribute("aria-pressed", on); b.textContent = on ? "★ Saved" : "☆ Save";
    });
    const ex = $("#export-saved"); if (ex) ex.hidden = saved.size === 0;
  }
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-save]");
    if (b) {
      const id = +b.dataset.save;
      saved.has(id) ? saved.delete(id) : saved.add(id);
      store.set("ds-saved", [...saved]); syncSaved();
      toast(saved.has(id) ? "Saved to your shelf" : "Removed from your shelf");
      if (App.state?.savedOnly) App.render(true);
    }
    const sh = e.target.closest("[data-share]");
    if (sh) {
      if (navigator.share) navigator.share({ title: document.title, url: location.href }).catch(() => {});
      else copy(location.href);
    }
  });
  syncSaved();

  /* ---------- Home app ---------- */
  const App = {};
  const page = document.body.dataset.page;

  if (page === "home") initHome();
  if (page === "category") initStaticFilter();

  async function initHome() {
    const results = $("#results"), input = $("#q"), catSel = $("#cat"), sortSel = $("#sort");
    const params = new URLSearchParams(location.search);
    const state = App.state = {
      q: params.get("q") || "", cat: params.get("cat") || "", sort: params.get("sort") || "relevance",
      tags: new Set((params.get("tags") || "").split(",").filter(Boolean)), savedOnly: params.get("saved") === "1",
      compact: store.get("ds-compact", false),
    };
    input.value = state.q; catSel.value = state.cat; sortSel.value = state.sort;

    let data;
    try { data = await (await fetch(`${BASE}/assets/index.json`)).json(); }
    catch { results.insertAdjacentHTML("beforebegin", "<p class='muted'>Could not load the catalogue. Showing a preview.</p>"); return; }
    const cats = data.c;
    const items = data.s.map(([id, slug, name, url, domain, cat, html, tags, plain]) => ({
      id, slug, name, url, domain, cat, html, tags, catName: cats[cat],
      _name: name.toLowerCase(), _text: `${name} ${domain} ${cats[cat]} ${plain} ${tags.join(" ")}`.toLowerCase(),
    }));

    function score(it, terms) {
      let s = 0;
      for (const t of terms) {
        if (it._name === t) s += 30;
        else if (it._name.startsWith(t)) s += 15;
        else if (it._name.includes(t)) s += 8;
        else if (it._text.includes(t)) s += 2;
        else return -1;
      }
      return s;
    }

    let list = [], shown = 0;
    const PAGE = 36;
    function card(it) {
      const tags = it.tags.slice(0, 4).map((t) => `<span class="tag">${esc(t)}</span>`).join("");
      const on = saved.has(it.id);
      return `<article class="card" data-id="${it.id}">
  <div class="card-head">
    <img class="fav" loading="lazy" decoding="async" width="28" height="28" alt="" src="https://icons.duckduckgo.com/ip3/${esc(it.domain)}.ico" onerror="this.style.visibility='hidden'">
    <h3 class="card-title"><a href="${BASE}/service/${it.slug}/">${esc(it.name)}</a></h3>
    <span class="price" aria-label="Free tier">$0</span>
  </div>
  <p class="card-desc">${it.html || "Free tier available."}</p>
  <div class="card-foot"><a class="chip cat" href="${BASE}/category/${it.cat}/">${esc(it.catName)}</a>${tags}</div>
  <div class="card-actions">
    <a class="btn btn-primary" href="${esc(it.url)}" target="_blank" rel="noopener nofollow">Visit ↗</a>
    <button class="btn save-btn" type="button" data-save="${it.id}" aria-pressed="${on}">${on ? "★ Saved" : "☆ Save"}</button>
  </div></article>`;
    }

    function compute() {
      const terms = state.q.toLowerCase().split(/\s+/).filter(Boolean);
      let out = [];
      for (const it of items) {
        if (state.cat && it.cat !== state.cat) continue;
        if (state.savedOnly && !saved.has(it.id)) continue;
        if (state.tags.size && ![...state.tags].every((t) => it.tags.includes(t))) continue;
        const s = terms.length ? score(it, terms) : 0;
        if (s < 0) continue;
        out.push([s, it]);
      }
      const by = {
        relevance: (a, b) => b[0] - a[0] || a[1].id - b[1].id,
        az: (a, b) => a[1]._name.localeCompare(b[1]._name),
        za: (a, b) => b[1]._name.localeCompare(a[1]._name),
        category: (a, b) => a[1].catName.localeCompare(b[1].catName) || a[1]._name.localeCompare(b[1]._name),
      }[state.sort];
      out.sort(by);
      return out.map((x) => x[1]);
    }

    function more() {
      if (shown >= list.length) return;
      results.insertAdjacentHTML("beforeend", list.slice(shown, shown + PAGE).map(card).join(""));
      shown += PAGE;
    }

    function syncUrl() {
      const p = new URLSearchParams();
      if (state.q) p.set("q", state.q);
      if (state.cat) p.set("cat", state.cat);
      if (state.tags.size) p.set("tags", [...state.tags].join(","));
      if (state.sort !== "relevance") p.set("sort", state.sort);
      if (state.savedOnly) p.set("saved", "1");
      const qs = p.toString();
      history.replaceState(null, "", qs ? `?${qs}` : location.pathname + location.hash);
    }

    App.render = function render(keepScroll) {
      list = compute(); shown = 0; results.innerHTML = "";
      results.classList.toggle("compact", state.compact);
      if (!list.length) {
        results.innerHTML = `<div class="empty"><p class="price price-lg">∅</p><p>No free tiers match that yet.</p>
          <p class="muted">Try fewer words, or <button class="link-btn" type="button" id="empty-clear">clear filters</button>.</p></div>`;
        $("#empty-clear")?.addEventListener("click", clearAll);
      } else more();
      $("#result-count").textContent = list.length.toLocaleString();
      $("#clear-filters").hidden = !(state.q || state.cat || state.tags.size || state.savedOnly);
      $$(".filter-tag").forEach((b) => b.setAttribute("aria-pressed", state.tags.has(b.dataset.tag)));
      $("#saved-only").setAttribute("aria-pressed", state.savedOnly);
      $("#view-toggle").setAttribute("aria-pressed", state.compact);
      $$(".cat-tile").forEach((t) => t.classList.toggle("active", t.dataset.cat === state.cat));
      syncUrl(); syncSaved();
      if (!keepScroll && (state.q || state.cat) && document.activeElement !== input) $("#browse").scrollIntoView({ behavior: "smooth" });
    };

    function clearAll() {
      state.q = ""; state.cat = ""; state.tags.clear(); state.savedOnly = false;
      input.value = ""; catSel.value = ""; App.render(true);
    }

    let deb;
    input.addEventListener("input", () => { clearTimeout(deb); deb = setTimeout(() => { state.q = input.value.trim(); App.render(true); }, 90); });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); $("#browse").scrollIntoView({ behavior: "smooth" }); }
      if (e.key === "Escape") { input.value = ""; state.q = ""; App.render(true); }
    });
    catSel.addEventListener("change", () => { state.cat = catSel.value; App.render(true); });
    sortSel.addEventListener("change", () => { state.sort = sortSel.value; App.render(true); });
    $$(".filter-tag").forEach((b) => b.addEventListener("click", () => {
      const t = b.dataset.tag; state.tags.has(t) ? state.tags.delete(t) : state.tags.add(t); App.render(true);
    }));
    $("#saved-only").addEventListener("click", () => { state.savedOnly = !state.savedOnly; App.render(true); });
    $("#view-toggle").addEventListener("click", () => { state.compact = !state.compact; store.set("ds-compact", state.compact); App.render(true); });
    $("#clear-filters").addEventListener("click", clearAll);
    $("#random-btn").addEventListener("click", () => {
      const pool = list.length ? list : items; const it = pool[Math.floor(Math.random() * pool.length)];
      location.href = `${BASE}/service/${it.slug}/`;
    });
    $("#share-view").addEventListener("click", () => copy(location.href, "Link to this view copied"));
    $("#export-saved").addEventListener("click", () => {
      const rows = items.filter((i) => saved.has(i.id)).map((i) => `- [${i.name}](${i.url}) — ${i.catName}`);
      const blob = new Blob([`# My DevShop shelf\n\n${rows.join("\n")}\n`], { type: "text/markdown" });
      const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "devshop-saved.md" });
      a.click(); URL.revokeObjectURL(a.href);
    });
    $$("[data-saved-link]").forEach((a) => a.addEventListener("click", () => { state.savedOnly = true; App.render(true); }));
    // Category tiles filter in place on the home page (still real links for SEO / no-JS)
    $$(".cat-tile").forEach((t) => t.addEventListener("click", (e) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey) return;
      e.preventDefault(); state.cat = t.dataset.cat; catSel.value = state.cat; App.render(true);
      $("#browse").scrollIntoView({ behavior: "smooth" });
    }));

    new IntersectionObserver((en) => { if (en[0].isIntersecting) more(); }, { rootMargin: "800px" }).observe($("#sentinel"));
    App.render(true);
    if (state.q) input.focus();
  }

  function initStaticFilter() {
    const input = $("#q"); if (!input) return;
    const cards = $$("#results .card").map((c) => [c, c.textContent.toLowerCase()]);
    input.addEventListener("input", () => {
      const terms = input.value.toLowerCase().split(/\s+/).filter(Boolean); let n = 0;
      for (const [c, t] of cards) { const ok = terms.every((x) => t.includes(x)); c.hidden = !ok; n += ok; }
      $("#result-count").textContent = n;
    });
  }

  /* ---------- Keyboard: "/" focuses search ---------- */
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !/input|textarea|select/i.test(document.activeElement.tagName)) {
      const q = $("#q");
      if (q) { e.preventDefault(); q.focus(); q.select(); }
      else location.href = `${BASE}/?q=`;
    }
  });

  /* ---------- PWA ---------- */
  if ("serviceWorker" in navigator && location.protocol === "https:") {
    addEventListener("load", () => navigator.serviceWorker.register(`${BASE}/sw.js`, { scope: `${BASE}/` }).catch(() => {}));
  }
})();
