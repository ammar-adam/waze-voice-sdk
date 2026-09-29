// First-party counters: permanent totals that do not depend on any analytics
// plan. site/track.js sends a beacon here alongside Plausible and Vercel.
//
// POST /api/tally {event, character?, method?, page?, worked?}
//
// Only the events below are counted, and every field is checked against a
// fixed list, so nobody can invent a character or a page. Each count goes to
// an all-time hash (stats:total) and a per-day hash (stats:day:YYYY-MM-DD)
// under the same field name.
//
// Visitors are counted in HyperLogLogs of a salted hash of IP + user agent
// (+ date for the daily one). A HyperLogLog keeps no members, so nothing that
// identifies a person is stored; raw IPs are never written anywhere, and the
// rate-limit keys hold only salted hashes that expire after a day.
//
// Abuse: a browser on another site is refused (see crossSite in _store.js),
// each visitor (IP + user agent) gets PER_DAY events a day, and each network
// (IPv4 address or IPv6 /64) gets PER_NETWORK, so rotating user agents does
// not buy unlimited counts.

const {SLUGS, PAGES, DOCS, KEY, config, redis, today, clientIp, ipBucket, hasher, crossSite, readBody} = require('./_store');

const PER_DAY = 400; // events per visitor per day; a real visit is a few dozen
const PER_NETWORK = 3000; // per IP or /64 per day; roomy for a shared carrier IP
const DAY_TTL = String(400 * 86400); // per-day keys outlive the 30-day chart
const BOT = /bot|crawl|spider|slurp|facebookexternalhit|preview|headless|lighthouse|curl|wget|python|axios|node-fetch/i;

function one(list, value) {
  return list.includes(value) ? value : null;
}

// A page as track.js reports it, folded onto the fixed list: /film/ and
// /film/index are /film, and every /docs/... page is /docs.
function pageOf(value) {
  if (typeof value !== 'string' || value.length > 100) return null;
  let path = value.replace(/\/index$/, '').replace(/\/+$/, '') || '/index';
  if (/^\/docs\/[a-z0-9-]+$/.test(path)) path = '/docs';
  return one(PAGES, path);
}

// The hash fields one event increments, or an error.
function fields(body) {
  const event = String(body.event || '');
  const character = one(SLUGS, body.character);
  const page = pageOf(body.page);
  switch (event) {
    case 'pageview':
      if (!page) return {error: 'unknown page'};
      return {fields: ['pageview', `pageview:${page}`]};
    case 'character_click':
      if (!character) return {error: 'unknown character'};
      return {fields: ['character_click', `character_click:${character}`]};
    case 'download': {
      const method = one(['tap', 'qr'], body.method);
      if (!character || !method) return {error: 'download needs a character and tap or qr'};
      return {
        fields: ['download', `download:${method}`, `download:${character}`, `download:${character}:${method}`],
      };
    }
    case 'install_worked': {
      const worked = one(['yes', 'no'], body.worked);
      if (!character || !worked) return {error: 'install_worked needs a character and yes or no'};
      return {fields: [`install_worked:${worked}`, `install_worked:${character}:${worked}`]};
    }
    case 'github_click':
      return {fields: ['github_click', ...(page ? [`github_click:${page}`] : [])]};
    case 'doc_read': {
      const doc = one(DOCS, page);
      if (!doc) return {error: 'unknown doc'};
      return {fields: ['doc_read', `doc_read:${doc}`]};
    }
    case 'suggest':
      return {fields: ['suggest']};
    default:
      return {error: 'unknown event'};
  }
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    res.status(405).json({error: 'POST only.'});
    return;
  }
  const store = config();
  if (!store) {
    res.status(503).json({error: 'Counters are not connected yet.'});
    return;
  }
  if (crossSite(req)) {
    res.status(403).json({error: 'Not counted.'});
    return;
  }
  let body;
  try {
    body = readBody(req);
  } catch (e) {
    res.status(400).json({error: 'Send JSON.'});
    return;
  }
  const counted = fields(body);
  if (counted.error) {
    res.status(400).json({error: counted.error});
    return;
  }
  const ua = String(req.headers['user-agent'] || '').slice(0, 512);
  // Preview deployments and bots share the store but must not move the numbers.
  const env = process.env.VERCEL_ENV;
  if ((env && env !== 'production') || !ua || BOT.test(ua)) {
    res.status(204).end();
    return;
  }

  const date = today();
  const ip = clientIp(req);
  const hash = hasher(store);
  const person = hash(ip, ua);

  try {
    const rate = KEY.rate(person.slice(0, 24), date);
    const rateIp = KEY.rateIp(hash('net', ipBucket(ip)).slice(0, 24), date);
    const [count, , network] = await redis([
      ['INCR', rate], ['EXPIRE', rate, '90000'],
      ['INCR', rateIp], ['EXPIRE', rateIp, '90000'],
    ]);
    if (count > PER_DAY || network > PER_NETWORK) {
      res.status(429).json({error: 'That\'s plenty for today.'});
      return;
    }
    const day = KEY.day(date);
    await redis([
      ...counted.fields.map((f) => ['HINCRBY', KEY.total, f, '1']),
      ...counted.fields.map((f) => ['HINCRBY', day, f, '1']),
      ['EXPIRE', day, DAY_TTL],
      ['PFADD', KEY.visitors, person],
      ['PFADD', KEY.visitorsOn(date), hash(ip, ua, date)],
      ['EXPIRE', KEY.visitorsOn(date), DAY_TTL],
      ['SET', KEY.since, date, 'NX'],
    ]);
    res.status(204).end();
  } catch (e) {
    res.status(502).json({error: 'Not counted. Try again.'});
  }
};

module.exports.fields = fields;
