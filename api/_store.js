// Shared by api/tally.js, api/stats.js and api/suggestions.js. The leading
// underscore keeps Vercel from turning this file into a function of its own.
//
// Storage is Redis over Upstash's REST API. Connect one in the Vercel
// dashboard (Storage -> Upstash Redis -> connect to this project) and Vercel
// injects KV_REST_API_URL and KV_REST_API_TOKEN. Until then every endpoint
// answers 503 and the pages fall back to what they can show without it.

const crypto = require('crypto');

const VOICES = require('../site/voices.json').voices;

// The only characters a counter accepts: the ones on the site.
const SLUGS = VOICES.map((v) => v.slug);
const NAMES = Object.fromEntries(VOICES.map((v) => [v.slug, v.name]));

// Pages as the browser reports them: the path without .html, "/" as /index.
// Every page under /docs/ counts as /docs, so a new doc page is counted
// without letting anyone invent new fields.
const PAGES = ['/index', '/how-it-works', '/make-your-own', '/install', '/stats', '/film', '/docs'];
const DOCS = ['/how-it-works', '/make-your-own', '/docs'];

const KEY = {
  total: 'stats:total',
  day: (date) => `stats:day:${date}`,
  visitors: 'stats:uv:all',
  visitorsOn: (date) => `stats:uv:${date}`,
  since: 'stats:since',
  rate: (who, date) => `stats:rate:${who}:${date}`,
  rateIp: (who, date) => `stats:rateip:${who}:${date}`,
};

// A Redis call that takes longer than this is abandoned, so a slow or
// unreachable store costs a visitor a fast error, not a hung request.
const REDIS_TIMEOUT_MS = 4000;

// The hosts the site is served from. Anything else posting to the API from a
// browser is another site trying to use its visitors to stuff the counters.
const SITE_HOSTS = ['backseatnav.com', 'www.backseatnav.com'];

function config() {
  const url = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
  return url && token ? {url, token} : null;
}

// Commands go over as a JSON array of string arrays, so a value from a request
// is only ever an argument: there is no command string to inject into.
async function redis(commands) {
  const {url, token} = config();
  const init = {
    method: 'POST',
    headers: {Authorization: `Bearer ${token}`, 'Content-Type': 'application/json'},
    body: JSON.stringify(commands),
  };
  if (typeof AbortSignal !== 'undefined' && AbortSignal.timeout) init.signal = AbortSignal.timeout(REDIS_TIMEOUT_MS);
  const res = await fetch(`${url}/pipeline`, init);
  if (!res.ok) throw new Error(`redis ${res.status}`);
  const out = await res.json();
  if (!Array.isArray(out)) throw new Error('redis: unexpected reply');
  return out.map((r) => {
    if (r && r.error) throw new Error('redis command failed');
    return r ? r.result : null;
  });
}

// YYYY-MM-DD in UTC, `back` days ago.
function today(back = 0) {
  return new Date(Date.now() - back * 86400000).toISOString().slice(0, 10);
}

// The caller's IP. On Vercel the edge sets x-vercel-forwarded-for and
// x-real-ip itself and overwrites any x-forwarded-for the client sent, so
// none of them can be forged from outside; the Vercel-specific ones are
// preferred in case a proxy ever sits in front.
function clientIp(req) {
  const h = (req && req.headers) || {};
  const raw = h['x-vercel-forwarded-for'] || h['x-real-ip'] || h['x-forwarded-for'] || '';
  return String(raw).split(',')[0].trim().slice(0, 64);
}

// What a rate limit keys on. An IPv6 user usually controls a whole /64, so
// limiting single addresses would be no limit at all.
function ipBucket(ip) {
  const addr = String(ip || '').trim().toLowerCase().replace(/%.*$/, '');
  const mapped = addr.match(/^::ffff:(\d+\.\d+\.\d+\.\d+)$/);
  if (mapped) return mapped[1];
  if (!addr.includes(':')) return addr;
  const [head, tail] = addr.split('::');
  const h = head ? head.split(':') : [];
  const t = tail === undefined ? [] : tail ? tail.split(':') : [];
  const groups = tail === undefined ? h : [...h, ...Array(Math.max(8 - h.length - t.length, 0)).fill('0'), ...t];
  return `${groups.slice(0, 4).map((g) => (parseInt(g, 16) || 0).toString(16)).join(':')}::/64`;
}

// A one-way, salted hash, so rate-limit keys and visitor counts never hold an
// IP address.
function hasher(store) {
  const salt = process.env.STATS_SALT || (store && store.token) || '';
  return (...parts) => crypto.createHash('sha256').update([salt, ...parts].join('|')).digest('hex');
}

// True when a browser sent this request from another site. Browsers attach
// Origin (and Sec-Fetch-Site) to every POST, so a page elsewhere cannot use
// its own visitors' connections to post here. Tools like curl send neither
// and are left to the rate limits.
function crossSite(req) {
  const h = (req && req.headers) || {};
  if (String(h['sec-fetch-site'] || '') === 'cross-site') return true;
  const origin = h.origin;
  if (origin === undefined || origin === '') return false;
  let host;
  try {
    host = new URL(String(origin)).host.toLowerCase();
  } catch (e) {
    return true; // "null" (sandboxed frames, data: pages) and anything malformed
  }
  const own = String(h['x-forwarded-host'] || h.host || '').split(',')[0].trim().toLowerCase();
  return host !== own && !SITE_HOSTS.includes(host);
}

// The request body as an object. Vercel parses JSON bodies itself (and
// throws on a malformed one when req.body is read); sendBeacon's text/plain
// arrives as a string or a Buffer. Anything over `max` characters, or
// anything that is not a JSON object, is refused.
function readBody(req, max = 2000) {
  let raw;
  try {
    raw = req.body;
  } catch (e) {
    throw new Error('bad json');
  }
  if (raw && typeof raw === 'object' && !Buffer.isBuffer(raw)) {
    if (Array.isArray(raw)) throw new Error('not an object');
    return raw;
  }
  const text = Buffer.isBuffer(raw) ? raw.toString('utf8') : String(raw || '');
  if (text.length > max) throw new Error('too long');
  const body = JSON.parse(text || '{}');
  if (!body || typeof body !== 'object' || Array.isArray(body)) throw new Error('not an object');
  return body;
}

module.exports = {
  SLUGS, NAMES, PAGES, DOCS, KEY, config, redis, today, clientIp, ipBucket, hasher, crossSite, readBody,
};
