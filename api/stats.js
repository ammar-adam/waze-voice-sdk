// The public numbers behind site/stats.html.
//
// GET /api/stats  all-time totals, per-character counts and a 30-day series,
// read from the counters api/tally.js keeps. Cached at the edge for a minute,
// so a busy stats page costs one Redis round trip a minute.

const {SLUGS, NAMES, PAGES, DOCS, KEY, config, redis, today} = require('./_store');

const DAYS = 30;
const DAILY = ['pageview', 'download', 'character_click'];

// HGETALL over REST is a flat [field, value, ...] array.
function toMap(flat) {
  const map = {};
  if (flat && !Array.isArray(flat)) {
    for (const [k, v] of Object.entries(flat)) map[k] = Number(v) || 0;
    return map;
  }
  for (let i = 0; i + 1 < (flat || []).length; i += 2) map[flat[i]] = Number(flat[i + 1]) || 0;
  return map;
}

function summarise(total, visitors, since, days) {
  const n = (field) => total[field] || 0;
  const characters = SLUGS.map((slug) => ({
    slug,
    name: NAMES[slug],
    downloads: n(`download:${slug}`),
    taps: n(`download:${slug}:tap`),
    qr: n(`download:${slug}:qr`),
    clicks: n(`character_click:${slug}`),
    confirmed: n(`install_worked:${slug}:yes`),
    failed: n(`install_worked:${slug}:no`),
  })).sort((a, b) => b.downloads - a.downloads || b.clicks - a.clicks || a.name.localeCompare(b.name));

  return {
    since: since || null,
    totals: {
      visitors: Number(visitors) || 0,
      pageviews: n('pageview'),
      downloads: n('download'),
      install_taps: n('download:tap'),
      qr_opens: n('download:qr'),
      confirmed_installs: n('install_worked:yes'),
      failed_installs: n('install_worked:no'),
      character_clicks: n('character_click'),
      doc_reads: n('doc_read'),
      github_clicks: n('github_click'),
      suggestions: n('suggest'),
    },
    pages: Object.fromEntries(PAGES.map((p) => [p, n(`pageview:${p}`)])),
    docs: Object.fromEntries(DOCS.map((p) => [p, {views: n(`pageview:${p}`), reads: n(`doc_read:${p}`)}])),
    characters,
    daily: days,
  };
}

module.exports = async (req, res) => {
  if (req.method !== 'GET') {
    res.setHeader('Cache-Control', 'no-store');
    res.status(405).json({error: 'GET only.'});
    return;
  }
  if (!config()) {
    res.setHeader('Cache-Control', 'public, s-maxage=60');
    res.status(503).json({error: 'Counters are not connected yet.'});
    return;
  }
  try {
    const dates = Array.from({length: DAYS}, (_, i) => today(DAYS - 1 - i));
    const results = await redis([
      ['HGETALL', KEY.total],
      ['PFCOUNT', KEY.visitors],
      ['GET', KEY.since],
      ...dates.flatMap((d) => [['HMGET', KEY.day(d), ...DAILY], ['PFCOUNT', KEY.visitorsOn(d)]]),
    ]);
    const [total, visitors, since] = results;
    const days = dates.map((date, i) => {
      const [pageviews, downloads, clicks] = (results[3 + i * 2] || []).map((v) => Number(v) || 0);
      return {date, visitors: Number(results[4 + i * 2]) || 0, pageviews, downloads, clicks};
    });
    res.setHeader('Cache-Control', 'public, s-maxage=60, stale-while-revalidate=300');
    res.status(200).json(summarise(toMap(total), visitors, since, days));
  } catch (e) {
    res.setHeader('Cache-Control', 'no-store');
    res.status(502).json({error: 'Stats are unavailable right now.'});
  }
};
