// Shared by api/track.js and api/stats.js. The leading underscore keeps
// Vercel from turning this file into a function of its own.
//
// Storage is Redis over Upstash's REST API, the same store as
// api/suggestions.js. Connect one in the Vercel dashboard (Storage -> Upstash
// Redis -> connect to this project) and Vercel injects KV_REST_API_URL and
// KV_REST_API_TOKEN. Until then both endpoints answer 503.

const VOICES = require('../site/voices.json').voices;

// The only characters a counter accepts: the ones on the site.
const SLUGS = VOICES.map((v) => v.slug);
const NAMES = Object.fromEntries(VOICES.map((v) => [v.slug, v.name]));

// Pages as the browser reports them: the path without .html, "/" as /index.
const PAGES = ['/index', '/how-it-works', '/make-your-own', '/install', '/stats'];
const DOCS = ['/how-it-works', '/make-your-own'];

const KEY = {
  total: 'stats:total',
  day: (date) => `stats:day:${date}`,
  visitors: 'stats:uv:all',
  visitorsOn: (date) => `stats:uv:${date}`,
  since: 'stats:since',
  rate: (who, date) => `stats:rate:${who}:${date}`,
};

function config() {
  const url = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
  return url && token ? {url, token} : null;
}

async function redis(commands) {
  const {url, token} = config();
  const res = await fetch(`${url}/pipeline`, {
    method: 'POST',
    headers: {Authorization: `Bearer ${token}`, 'Content-Type': 'application/json'},
    body: JSON.stringify(commands),
  });
  if (!res.ok) throw new Error(`redis ${res.status}`);
  return (await res.json()).map((r) => {
    if (r.error) throw new Error(`redis ${r.error}`);
    return r.result;
  });
}

// YYYY-MM-DD in UTC, `back` days ago.
function today(back = 0) {
  return new Date(Date.now() - back * 86400000).toISOString().slice(0, 10);
}

module.exports = {SLUGS, NAMES, PAGES, DOCS, KEY, config, redis, today};
