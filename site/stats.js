/* stats.html: draws /api/stats. Characters come from voices.json, so the
   leaderboard still shows every face when the counters aren't connected. */

(function () {
  "use strict";

  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var SVG = "http://www.w3.org/2000/svg";
  var LABELS = {
    visitors: "visitors", downloads: "install taps + QR opens",
    clicks: "character clicks", pageviews: "page views"
  };
  var data = null;
  var series = "visitors";

  function fmt(n) { return Number(n || 0).toLocaleString("en-US"); }

  function countUp(node, to) {
    if (still || to < 10) { node.textContent = fmt(to); return; }
    var start = null;
    function frame(t) {
      if (start === null) start = t;
      var p = Math.min((t - start) / 900, 1);
      node.textContent = fmt(Math.round(to * (1 - Math.pow(1 - p, 3))));
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function say(text) {
    var state = document.getElementById("stats-state");
    state.textContent = text;
    state.hidden = !text;
  }

  function niceDate(iso) {
    var d = new Date(iso + "T12:00:00Z");
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  }

  /* ---------------- headline numbers ---------------- */

  function totals(t) {
    document.querySelectorAll("[data-stat]").forEach(function (node) {
      countUp(node, t[node.getAttribute("data-stat")] || 0);
    });
  }

  /* ---------------- 30-day chart ---------------- */

  function el(name, attrs, parent) {
    var node = document.createElementNS(SVG, name);
    Object.keys(attrs).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(node);
    return node;
  }

  function chart() {
    var box = document.getElementById("chart");
    var old = box.querySelector("svg, .chart-empty");
    if (old) old.remove();
    var days = (data && data.daily) || [];
    var values = days.map(function (d) { return d[series] || 0; });
    var max = Math.max.apply(null, values.concat([0]));
    document.getElementById("chart-cap").textContent =
      "Daily " + LABELS[series] + " for the last 30 days, peaking at " + fmt(max) + ".";

    if (!max) {
      var empty = document.createElement("p");
      empty.className = "chart-empty";
      empty.textContent = data
        ? "No " + LABELS[series] + " in the last 30 days yet. The next one starts the chart."
        : "The chart fills in once the counters are connected.";
      box.appendChild(empty);
      return;
    }

    var W = 600, H = 236, top = 26, bottom = 196, left = 6, right = 594;
    var svg = el("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-labelledby": "chart-cap" }, box);
    var step = (right - left) / days.length;
    var barW = Math.max(step - 5, 3);
    el("line", { x1: left, x2: right, y1: bottom, y2: bottom, class: "axis" }, svg);
    el("line", { x1: left, x2: right, y1: top, y2: top, class: "grid" }, svg);
    var peak = el("text", { x: left, y: top - 7, class: "peak" }, svg);
    peak.textContent = fmt(max) + " " + LABELS[series];

    days.forEach(function (d, i) {
      var v = values[i];
      var h = v ? Math.max((v / max) * (bottom - top), 3) : 0;
      var g = el("g", {}, svg);
      var bar = el("rect", {
        x: (left + i * step + (step - barW) / 2).toFixed(1), y: (bottom - h).toFixed(1),
        width: barW.toFixed(1), height: h.toFixed(1), rx: 3,
        class: i === days.length - 1 ? "bar today" : "bar"
      }, g);
      var tip = el("title", {}, bar);
      tip.textContent = niceDate(d.date) + ": " + fmt(v) + " " + LABELS[series];
    });
    [0, Math.floor(days.length / 2), days.length - 1].forEach(function (i, n) {
      var x = left + i * step + step / 2;
      var label = el("text", {
        x: x.toFixed(1), y: H - 10, class: "day",
        "text-anchor": n === 0 ? "start" : n === 2 ? "end" : "middle"
      }, svg);
      label.textContent = n === 2 ? "Today" : niceDate(days[i].date);
    });
  }

  document.querySelectorAll("[data-series]").forEach(function (button) {
    button.addEventListener("click", function () {
      series = button.getAttribute("data-series");
      document.querySelectorAll("[data-series]").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b === button));
      });
      chart();
    });
  });

  /* ---------------- leaderboard ---------------- */

  function node(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  function nums(row, pairs) {
    var dl = node("dl", "nums");
    pairs.forEach(function (p) {
      var cell = node("div");
      cell.appendChild(node("dt", "", p[0]));
      cell.appendChild(node("dd", "", p[1]));
      dl.appendChild(cell);
    });
    row.appendChild(dl);
  }

  function leaderboard(characters) {
    var list = document.getElementById("leader");
    list.innerHTML = "";
    // Slugs become an id, an image path and a link; only plain ones are drawn.
    characters = characters.filter(function (c) { return c && /^[a-z0-9-]+$/.test(c.slug); });
    var top = Math.max.apply(null, characters.map(function (c) { return c.downloads || 0; }).concat([0]));
    characters.forEach(function (c, i) {
      var live = typeof c.downloads === "number";
      var row = node("li", "row sticker");
      row.id = c.slug; // characters.css colours each row by slug
      row.appendChild(node("span", "rank", String(i + 1)));
      var face = node("span", "face");
      var img = document.createElement("img");
      img.src = "faces/" + c.slug + ".svg";
      img.alt = "";
      img.width = 64; img.height = 64;
      face.appendChild(img);
      row.appendChild(face);

      var who = node("div", "who");
      var name = node("a", "", c.name);
      name.href = "./#" + c.slug;
      who.appendChild(name);
      var meter = node("span", "meter");
      var fill = node("i");
      fill.style.width = (top && live ? Math.max((c.downloads / top) * 100, c.downloads ? 4 : 0) : 0) + "%";
      meter.appendChild(fill);
      who.appendChild(meter);
      row.appendChild(who);

      var dash = "–";
      nums(row, [
        ["install taps", live ? fmt(c.taps) : dash],
        ["QR opens", live ? fmt(c.qr) : dash],
        ["clicks", live ? fmt(c.clicks) : dash],
        ["confirmed*", live ? fmt(c.confirmed) : dash]
      ]);
      list.appendChild(row);
    });
  }

  /* ---------------- who should ride next ---------------- */
  // Every suggestion from /api/suggestions, most wanted first, so it's easy
  // to see which character to build next.

  function wanted(res) {
    var list = document.getElementById("wanted-list");
    var sub = document.getElementById("wanted-sub");
    list.innerHTML = "";
    var items = (res.ok && res.body && res.body.items) || [];
    if (!res.ok) {
      sub.textContent = res.status === 503
        ? "Suggestions aren't switched on yet. They show up here as soon as they are."
        : "The suggestions didn't load. Refresh in a minute.";
      return;
    }
    if (!items.length) { sub.textContent = "No suggestions yet."; return; }
    var total = res.body.total || items.length;
    var votes = items.reduce(function (sum, item) { return sum + (item.votes || 0); }, 0);
    sub.textContent = fmt(total) + (total === 1 ? " character" : " characters") + " suggested, " +
      fmt(votes) + (votes === 1 ? " vote" : " votes") + (total > items.length ? " across the top " + fmt(items.length) : "") +
      ". Different spellings of one name count together.";
    var top = items[0].votes || 1;
    items.forEach(function (item, i) {
      var row = node("li", "sticker");
      row.appendChild(node("span", "rank", String(i + 1)));
      var who = node("div", "who");
      who.appendChild(node("span", "name", item.name));
      var meter = node("span", "meter");
      var fill = node("i");
      fill.style.width = Math.max((item.votes / top) * 100, 4) + "%";
      meter.appendChild(fill);
      who.appendChild(meter);
      row.appendChild(who);
      var count = node("span", "votes", fmt(item.votes));
      count.appendChild(node("small", "", item.votes === 1 ? "vote" : "votes"));
      row.appendChild(count);
      list.appendChild(row);
    });
  }

  /* ---------------- load ---------------- */

  function json(url) {
    return fetch(url, { cache: "no-cache" }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (body) {
        return { ok: r.ok, status: r.status, body: body };
      });
    });
  }

  json("api/suggestions?limit=200")
    .catch(function () { return { ok: false, status: 0, body: {} }; })
    .then(wanted);

  var voices = json("voices.json").then(function (r) { return r.body.voices || []; }).catch(function () { return []; });

  Promise.all([voices, json("api/stats").catch(function () { return { ok: false, status: 0, body: {} }; })])
    .then(function (both) {
      var list = both[0], res = both[1];
      if (!res.ok) {
        say(res.status === 503
          ? "The counters aren't switched on yet. The numbers show up here as soon as they are."
          : "The numbers didn't load. Refresh in a minute.");
        leaderboard(list.map(function (v) { return { slug: v.slug, name: v.name }; }));
        chart();
        return;
      }
      data = res.body;
      var t = data.totals || {};
      totals(t);
      if (data.since) {
        document.getElementById("stats-since").textContent =
          "Counted by Backseat itself since " + new Date(data.since + "T12:00:00Z").toLocaleDateString("en-US",
            { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" }) + ". Updated every minute.";
      }
      if (!t.visitors && !t.pageviews) say("Fresh counters. The numbers start with the next visitor.");
      leaderboard(data.characters || []);
      chart();
    });
})();
