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
// identifies a person is stored; raw IPs are never written anywhere.

const crypto = require('crypto');
const {SLUGS, PAGES, DOCS, KEY, config, redis, today} = require('./_store');

const PER_DAY = 400; // events per visitor per day; a real visit is a few dozen
const DAY_TTL = String(400 * 86400); // per-day keys outlive the 30-day chart
const BOT = /bot|crawl|spider|slurp|facebookexternalhit|preview|headless|lighthouse|curl|wget|python|axios|node-fetch/i;

function one(list, value) {
  return list.includes(value) ? value : null;
}

// The hash fields one event increments, or an error.
function fields(body) {
  const event = String(body.event || '');
  const character = one(SLUGS, body.character);
  const page = one(PAGES, body.page);
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
      const doc = one(DOCS, body.page);
      if (!doc) return {error: 'unknown doc'};
      return {fields: ['doc_read', `doc_read:${doc}`]};
    }
    case 'suggest':
      return {fields: ['suggest']};
    default:
      return {error: 'unknown event'};
  }
}

function parse(raw) {
  if (raw && typeof raw === 'object' && !Buffer.isBuffer(raw)) return raw;
  const text = Buffer.isBuffer(raw) ? raw.toString('utf8') : String(raw || '');
  if (text.length > 2000) throw new Error('too long');
  const body = JSON.parse(text || '{}');
  if (!body || typeof body !== 'object') throw new Error('not an object');
  return body;
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') {
    res.status(405).json({error: 'POST only.'});
    return;
  }
  const store = config();
  if (!store) {
    res.status(503).json({error: 'Counters are not connected yet.'});
    return;
  }
  let body;
  try {
    body = parse(req.body);
  } catch (e) {
    res.status(400).json({error: 'Send JSON.'});
    return;
  }
  const counted = fields(body);
  if (counted.error) {
    res.status(400).json({error: counted.error});
    return;
  }
  const ua = String(req.headers['user-agent'] || '');
  // Preview deployments and bots share the store but must not move the numbers.
  const env = process.env.VERCEL_ENV;
  if ((env && env !== 'production') || !ua || BOT.test(ua)) {
    res.status(204).end();
    return;
  }

  const date = today();
  const ip = String(req.headers['x-forwarded-for'] || req.headers['x-real-ip'] || '').split(',')[0].trim();
  const salt = process.env.STATS_SALT || store.token;
  const hash = (...parts) => crypto.createHash('sha256').update([salt, ...parts].join('|')).digest('hex');
  const person = hash(ip, ua);

  try {
    const rate = KEY.rate(person.slice(0, 24), date);
    const [count] = await redis([['INCR', rate], ['EXPIRE', rate, '90000']]);
    if (count > PER_DAY) {
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
