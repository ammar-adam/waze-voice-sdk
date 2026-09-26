/* The only place the site talks to an analytics provider.

   Every event goes through track(name, props) and is sent to Plausible,
   Vercel Web Analytics, and the site's own counters (api/track.js, shown on
   stats.html). Swapping or adding a provider is a change to this one file. It never throws: a blocked script or a privacy extension must not
   break the page it is measuring. */

window.plausible = window.plausible || function () {
  (window.plausible.q = window.plausible.q || []).push(arguments);
};
// Each page also defines this inline before /_vercel/insights/script.js; kept
// here so track() works on a page that forgot it.
window.va = window.va || function () {
  (window.vaq = window.vaq || []).push(arguments);
};

/* Vercel keeps at most 2 properties per custom event on Pro (8 with Web
   Analytics Plus), so each event names the two that matter most, character
   first. Plausible still gets every property. */
var VERCEL_PROPS = {
  site_view: ["utm_source", "inapp"],
  preview_play: ["character", "clip"],
  cast_click: ["character"],
  character_click: ["character", "action"],
  install_click: ["character", "inapp"],
  install_qr_shown: ["character"],
  download: ["character", "method"],
  install_worked: ["character", "worked"],
  github_click: ["page", "link"],
  doc_read: ["page"],
  suggest: ["character"]
};

function vercelData(name, props) {
  var keys = VERCEL_PROPS[name] || Object.keys(props).slice(0, 2);
  var data = {};
  keys.forEach(function (key) {
    if (!(key in props)) return;
    var value = props[key];
    if (value !== null && typeof value === "object") value = String(value);
    if (typeof value === "string") value = value.slice(0, 255);
    data[key] = value === undefined ? null : value;
  });
  return data;
}

/* The site's own counters: permanent, and free of any analytics plan's
   limits. Only these events are counted; api/track.js checks every field. */
var COUNTED = {
  character_click: 1, download: 1, install_worked: 1,
  github_click: 1, doc_read: 1, suggest: 1
};

// "/" and "/index.html" are both /index; "/how-it-works.html" is /how-it-works.
function pagePath() {
  var path = location.pathname.replace(/\.html$/, "");
  return path === "/" || path === "" ? "/index" : path;
}

// Fire and forget. sendBeacon survives the page unloading (a tap to Waze or
// GitHub); text/plain keeps it a simple request. Never throws, never waits.
function count(name, props) {
  try {
    var body = JSON.stringify({
      event: name, character: props.character, method: props.method,
      page: props.page, worked: props.worked
    });
    if (navigator.sendBeacon &&
        navigator.sendBeacon("/api/track", new Blob([body], { type: "text/plain" }))) return;
    fetch("/api/track", { method: "POST", body: body, keepalive: true }).catch(function () {});
  } catch (e) { /* the page still works */ }
}

window.track = function track(name, props, done) {
  var finished = false;
  props = props || {};
  function finish() {
    if (finished) return;
    finished = true;
    if (done) done();
  }
  try {
    window.va("event", { name: name, data: vercelData(name, props) });
  } catch (e) { /* the page still works */ }
  try {
    window.plausible(name, { props: props, callback: finish });
  } catch (e) { /* the page still works */ }
  if (COUNTED[name]) count(name, props);
  // A blocked script never calls back. Do not make the user wait on it.
  if (done) setTimeout(finish, 900);
};

/* TikTok, Instagram and Facebook open links in their own webview, which often
   will not hand a link off to another app. That is the difference between a
   tap installing a voice and a tap loading a web page, so it is detected here
   and reported with every event. */
window.inAppBrowser = (function () {
  var ua = navigator.userAgent || "";
  if (/musical_ly|BytedanceWebview|TikTok|Bytedance/i.test(ua)) return "tiktok";
  if (/Instagram/i.test(ua)) return "instagram";
  if (/FBAN|FBAV|FB_IAB/i.test(ua)) return "facebook";
  if (/Twitter/i.test(ua)) return "x";
  if (/LinkedInApp/i.test(ua)) return "linkedin";
  if (/Snapchat/i.test(ua)) return "snapchat";
  return "";
})();

window.isPhone = (function () {
  var ua = navigator.userAgent || "";
  if (/android|iphone|ipod/i.test(ua)) return true;
  // iPadOS reports itself as a Mac; the touch points give it away.
  return /Macintosh/.test(ua) && navigator.maxTouchPoints > 1;
})();

(function () {
  var page = pagePath;

  // Plausible and Vercel count page views themselves; the counters need telling.
  count("pageview", { page: page() });

  /* Every link to GitHub, on every page, counts as a GitHub visit. Delegated,
     so links added later (the "suggest it on GitHub" note) count too. */
  function githubLink(e) {
    return (e.target && e.target.closest && e.target.closest('a[href^="https://github.com/"]')) || null;
  }

  function linkProps(link) {
    return { page: page(), link: link.href.replace("https://github.com/", "") };
  }

  document.addEventListener("click", function (e) {
    var link = githubLink(e);
    if (!link) return;
    var elsewhere = e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey ||
      e.shiftKey || e.altKey || link.target === "_blank";
    if (elsewhere) { track("github_click", linkProps(link)); return; }
    // Same tab: give the event a moment to leave before the page does.
    e.preventDefault();
    var href = link.href;
    track("github_click", linkProps(link), function () { location.href = href; });
  });

  // A middle click opens a tab without firing click.
  document.addEventListener("auxclick", function (e) {
    var link = e.button === 1 && githubLink(e);
    if (link) track("github_click", linkProps(link));
  });

  /* Documentation and blog readership. The page view says someone opened it;
     doc_read says they scrolled most of the way through. Pages opt in with
     <body data-doc-read>. */
  function watchReading() {
    if (!document.body || !document.body.hasAttribute("data-doc-read")) return;
    function check() {
      var doc = document.documentElement;
      if ((window.scrollY + window.innerHeight) / Math.max(doc.scrollHeight, 1) < 0.6) return;
      window.removeEventListener("scroll", check);
      track("doc_read", { page: page() });
    }
    window.addEventListener("scroll", check, { passive: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", watchReading);
  else watchReading();
})();
