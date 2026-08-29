(function () {
  const root = document.getElementById("coupling-monitor");
  if (!root) return;

  const SNAPSHOT =
    root.getAttribute("data-snapshot") ||
    new URL("../assets/monitor/snapshot.json", document.baseURI).href;

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function tile(status, title, body, meta) {
    const art = el("article", "mon-tile mon-" + String(status || "unknown").toLowerCase());
    art.appendChild(el("div", "mon-kicker", status || "UNKNOWN"));
    art.appendChild(el("h2", "", title));
    if (typeof body === "string") art.appendChild(el("p", "", body));
    else if (body) art.appendChild(body);
    if (meta) art.appendChild(el("p", "mon-meta", meta));
    return art;
  }

  function list(items, mapFn) {
    const ul = el("ul", "mon-list");
    (items || []).slice(0, 8).forEach((item) => {
      const li = el("li");
      const node = mapFn(item);
      if (typeof node === "string") li.textContent = node;
      else li.appendChild(node);
      ul.appendChild(li);
    });
    if (!items || !items.length) ul.appendChild(el("li", "", "None in the current window."));
    return ul;
  }

  function render(data) {
    root.innerHTML = "";
    const head = el("div", "mon-head");
    head.appendChild(el("p", "mon-fetched", "Snapshot " + (data.fetched_at || "unknown") + " · health " + (data.health || "?")));
    head.appendChild(el("p", "mon-disc", data.disclaimer || ""));
    root.appendChild(head);

    const grid = el("div", "mon-grid");

    const nino = data.nino34 || {};
    if (nino.ok) {
      const body = el("div");
      body.appendChild(el("p", "mon-value", (nino.anomaly_c >= 0 ? "+" : "") + nino.anomaly_c + " °C anomaly"));
      body.appendChild(el("p", "", "SST " + nino.sst_c + " °C · week " + nino.time));
      body.appendChild(el("p", "mon-meta", nino.note));
      grid.appendChild(tile("LIVE", "Air — Niño 3.4", body, nino.source));
    } else {
      grid.appendChild(tile("STALE", "Air — Niño 3.4", nino.error || "Fetch failed", "ERDDAP"));
    }

    const lock = (data.locked || {}).register_lock || {};
    grid.appendChild(tile("LOCKED", "Water — extra-polar SST", lock.extra_polar_sst_c + " °C on " + lock.extra_polar_sst_date, lock.note));

    const amoc = (data.locked || {}).amoc_rapid || {};
    grid.appendChild(tile(amoc.status, "Water — RAPID AMOC", amoc.value + ". " + amoc.vintage, amoc.note));

    const cl002 = (data.locked || {}).cl002 || {};
    grid.appendChild(tile(cl002.status, cl002.claim, cl002.note, "Register gate"));

    const q = data.quakes_m6 || {};
    if (q.ok) {
      const wrap = el("div");
      wrap.appendChild(el("p", "mon-value", q.count + " events M≥" + q.min_magnitude + " / " + q.window_days + "d"));
      wrap.appendChild(list(q.events, (e) => {
        const a = el("a");
        a.href = e.url || "#";
        a.target = "_blank";
        a.rel = "noopener";
        a.textContent = "M" + e.mag + " — " + (e.place || "unknown");
        return a;
      }));
      grid.appendChild(tile("LIVE", "Earth — USGS M≥6", wrap, q.source));
    } else {
      grid.appendChild(tile("STALE", "Earth — USGS M≥6", q.error || "Fetch failed", "USGS FDSN"));
    }

    const volc = data.volcanoes_open || {};
    if (volc.ok) {
      const wrap = el("div");
      wrap.appendChild(el("p", "mon-value", volc.count + " open EONET volcano events"));
      wrap.appendChild(el("p", "mon-meta", "Open detections are not CL-016 and not a volcanic winter."));
      wrap.appendChild(list(volc.events, (e) => e.title || e.id));
      grid.appendChild(tile("LIVE", "Earth/Fire — open volcanoes", wrap, volc.source));
    } else {
      grid.appendChild(tile("STALE", "Earth/Fire — open volcanoes", volc.error || "Fetch failed", "EONET"));
    }

    const fire = data.wildfires_open || {};
    if (fire.ok) {
      const wrap = el("div");
      wrap.appendChild(el("p", "mon-value", fire.count + " open EONET wildfire events (page cap)"));
      wrap.appendChild(list(fire.events, (e) => e.title || e.id));
      grid.appendChild(tile("LIVE", "Fire — open wildfires", wrap, fire.source));
    } else {
      grid.appendChild(tile("STALE", "Fire — open wildfires", fire.error || "Fetch failed", "EONET"));
    }

    const cl016 = (data.locked || {}).cl016 || {};
    grid.appendChild(tile(cl016.status, cl016.claim, cl016.note, "Appendix K"));

    const bio = (data.locked || {}).biology || {};
    grid.appendChild(tile(bio.status, bio.claim, bio.note, "No v1 series"));

    const cl003 = (data.locked || {}).cl003 || {};
    grid.appendChild(tile(cl003.status, cl003.claim, cl003.note, "Register gate"));

    root.appendChild(grid);

    if (data.errors && data.errors.length) {
      const err = el("div", "mon-errors");
      err.appendChild(el("h2", "", "Fetch defects"));
      err.appendChild(list(data.errors, (e) => e));
      root.appendChild(err);
    }
  }

  fetch(SNAPSHOT, { cache: "no-store" })
    .then((r) => {
      if (!r.ok) throw new Error("snapshot HTTP " + r.status);
      return r.json();
    })
    .then(render)
    .catch((err) => {
      root.innerHTML = "";
      root.appendChild(tile("STALE", "Monitor snapshot missing", String(err), SNAPSHOT));
    });
})();
