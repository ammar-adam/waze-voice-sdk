/* The only place the site talks to an analytics provider.

   Every event goes through track(name, props). Swapping Plausible for
   something else is a change to this one function. It never throws: a blocked
   script or a privacy extension must not break the page it is measuring. */

window.plausible = window.plausible || function () {
  (window.plausible.q = window.plausible.q || []).push(arguments);
};

window.track = function track(name, props, done) {
  var finished = false;
  function finish() {
    if (finished) return;
    finished = true;
    if (done) done();
  }
  try {
    window.plausible(name, { props: props || {}, callback: finish });
  } catch (e) { /* the page still works */ }
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
