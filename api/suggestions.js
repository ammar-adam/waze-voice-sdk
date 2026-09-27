// "Who should ride next?" A tiny suggestion board for the site.
//
// GET  /api/suggestions          the 30 most-wanted characters, with counts
// GET  /api/suggestions?limit=N  the top N (1 to 200); stats.html asks for all
// POST /api/suggestions {name}   suggest a character, or back one already listed
//
// Storage is Redis over Upstash's REST API. Connect a store in the Vercel
// dashboard (Storage -> Upstash Redis -> connect to this project) and Vercel
// injects KV_REST_API_URL and KV_REST_API_TOKEN. Until then every request
// answers 503 and the page points people at GitHub instead.
//
// Different spellings of one character land on one entry. A name becomes a
// key by dropping case, accents, punctuation, spaces and a leading "the";
// a few common nicknames map to the full name; and a key that is one typo
// away from an existing entry (two for long names) counts for that entry
// instead of starting a new one. Characters already on the site match the
// same way, so "Mickey Mous" is told Mickey Mouse is already riding.
//
// Names are shown to every visitor, so they are length-limited, restricted to
// ordinary characters, and anything that looks like a link is refused. Remove
// a bad entry with: ZREM suggest:votes <key>  and  HDEL suggest:names <key>.

const URL_ = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
const TOKEN = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;

const VOTES = 'suggest:votes';
const NAMES = 'suggest:names';
const PER_DAY = 25;
const DEFAULT_LIMIT = 30;
const MAX_LIMIT = 200;

// A name as a key: "Mickey-Mouse!", "mickey mouse" and "Mickéy Mouse" are all
// "mickeymouse". A leading "the" goes, so "The Grinch" meets "Grinch".
function keyOf(name) {
  return String(name || '')
    .normalize('NFKD').replace(/\p{M}+/gu, '')
    .toLowerCase()
    .replace(/&/g, ' and ')
    .trim()
    .replace(/^the\s+/, '')
    .replace(/[^\p{L}\p{N}]+/gu, '');
}

// Nicknames and long forms that should count for the usual name. Both sides
// are keys already. Kept short on purpose: only the obvious ones.
const ALIASES = {
  // On the site already.
  bugs: 'bugsbunny', daffy: 'daffyduck',
  pooh: 'winniethepooh', poohbear: 'winniethepooh', winnie: 'winniethepooh',
  paddingtonbear: 'paddington', mickey: 'mickeymouse', vader: 'darthvader',
  brucewayne: 'batman', ramsay: 'gordonramsay', chefgordonramsay: 'gordonramsay',
  cartman: 'ericcartman',
  // Popular requests.
  spongebobsquarepants: 'spongebob', squarepants: 'spongebob',
  homer: 'homersimpson', scooby: 'scoobydoo', optimus: 'optimusprime',
  stewie: 'stewiegriffin', supermario: 'mario', masteryoda: 'yoda',
};

function canonical(name) {
  const key = keyOf(name);
  return ALIASES[key] || key;
}

// Already in the app: suggesting one of these points you at it instead.
const VOICES = require('../site/voices.json').voices;
const LIVE = Object.fromEntries(VOICES.map((v) => [keyOf(v.name), v.name]));

// A few to start the board so it is never empty.
const SEEDS = ['SpongeBob', 'Yoda', 'Shrek', 'Homer Simpson', 'Mario', 'Scooby-Doo', 'Optimus Prime', 'Stewie Griffin'];

// Optimal string alignment distance (Damerau-Levenshtein with adjacent
// swaps). Gives up early, returning max + 1, once it is past `max`.
function distance(a, b, max) {
  const s = [...a];
  const t = [...b];
  if (Math.abs(s.length - t.length) > max) return max + 1;
  let before = null;
  let prev = Array.from({length: t.length + 1}, (_, j) => j);
  for (let i = 1; i <= s.length; i++) {
    const row = [i];
    let best = i;
    for (let j = 1; j <= t.length; j++) {
      const cost = s[i - 1] === t[j - 1] ? 0 : 1;
      let d = Math.min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + cost);
      if (before && j > 1 && s[i - 1] === t[j - 2] && s[i - 2] === t[j - 1]) {
        d = Math.min(d, before[j - 2] + 1);
      }
      row.push(d);
      if (d < best) best = d;
    }
    if (best > max) return max + 1;
    before = prev;
    prev = row;
  }
  return prev[t.length];
}

// How many typos two keys may differ by and still be one character: none
// for short names (Bart is not Bert), one from five letters, two from nine.
function allowance(a, b) {
  const n = Math.min([...a].length, [...b].length);
  if (n >= 9) return 2;
  if (n >= 5) return 1;
  return 0;
}

const digits = (key) => key.replace(/\D+/g, '');

// The candidate key that `key` means, or null: an exact match, else the
// nearest within the allowance. Numbers must agree, so "Rocky 2" never
// becomes "Rocky 3".
function closest(key, candidates) {
  if (candidates.includes(key)) return key;
  let best = null;
  let bestDistance = Infinity;
  for (const candidate of candidates) {
    const max = allowance(key, candidate);
    if (!max || digits(candidate) !== digits(key)) continue;
    const d = distance(key, candidate, max);
    if (d <= max && d < bestDistance) {
      best = candidate;
      bestDistance = d;
    }
  }
  return best;
}

async function redis(commands) {
  const res = await fetch(`${URL_}/pipeline`, {
    method: 'POST',
    headers: {Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json'},
    body: JSON.stringify(commands),
  });
  if (!res.ok) throw new Error(`redis ${res.status}`);
  return (await res.json()).map((r) => r.result);
}

async function board(limit = DEFAULT_LIMIT) {
  const read = [['ZREVRANGE', VOTES, '0', String(limit - 1), 'WITHSCORES'], ['ZCARD', VOTES]];
  let [ranked, total] = await redis(read);
  if (!ranked.length) {
    await redis([
      ...SEEDS.map((s) => ['HSETNX', NAMES, keyOf(s), s]),
      ...SEEDS.map((s) => ['ZADD', VOTES, 'NX', '1', keyOf(s)]),
    ]);
    [ranked, total] = await redis(read);
  }
  const keys = ranked.filter((_, i) => i % 2 === 0);
  const [names] = keys.length ? await redis([['HMGET', NAMES, ...keys]]) : [[]];
  return {
    items: keys.map((key, i) => ({key, name: names[i] || key, votes: Number(ranked[i * 2 + 1])})),
    total: Number(total) || keys.length,
  };
}

function limitOf(req) {
  let raw = req.query && req.query.limit;
  if (raw === undefined && req.url) {
    try {
      raw = new URL(req.url, 'http://localhost').searchParams.get('limit');
    } catch (e) {
      raw = null;
    }
  }
  const n = parseInt(raw, 10);
  return Number.isFinite(n) ? Math.min(Math.max(n, 1), MAX_LIMIT) : DEFAULT_LIMIT;
}

function clean(raw) {
  const name = String(raw || '').replace(/\s+/g, ' ').trim();
  if (name.length < 2 || name.length > 40) return {error: 'Names are 2 to 40 characters.'};
  if (/https?:|www\.|\.(com|net|org|io)\b|[<>{}]/i.test(name)) return {error: 'Just the character\'s name, please.'};
  if (!/^[\p{L}\p{N} '’.&!-]+$/u.test(name)) return {error: 'Letters, numbers and spaces only.'};
  if (!keyOf(name)) return {error: 'Letters, numbers and spaces only.'};
  return {name};
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (!URL_ || !TOKEN) {
    res.status(503).json({error: 'Suggestions are not connected yet.'});
    return;
  }
  try {
    if (req.method === 'GET') {
      res.status(200).json(await board(limitOf(req)));
      return;
    }
    if (req.method !== 'POST') {
      res.status(405).json({error: 'GET or POST only.'});
      return;
    }
    const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : req.body || {};
    const {name, error} = clean(body.name);
    if (error) {
      res.status(400).json({error});
      return;
    }
    const key = canonical(name);
    const live = closest(key, Object.keys(LIVE));
    if (live) {
      res.status(200).json({live: LIVE[live], key: live, ...(await board())});
      return;
    }
    const ip = String(req.headers['x-forwarded-for'] || 'unknown').split(',')[0].trim();
    const limitKey = `suggest:rate:${ip}:${new Date().toISOString().slice(0, 10)}`;
    const [count, , known] = await redis([['INCR', limitKey], ['EXPIRE', limitKey, '90000'], ['HKEYS', NAMES]]);
    if (count > PER_DAY) {
      res.status(429).json({error: 'That\'s plenty for today. Thanks!'});
      return;
    }
    // A near-miss spelling backs the entry it meant instead of starting one.
    const target = closest(key, known || []) || key;
    const [, votes, stored] = await redis([
      ['HSETNX', NAMES, target, name],
      ['ZINCRBY', VOTES, '1', target],
      ['HGET', NAMES, target],
    ]);
    res.status(200).json({
      added: {key: target, name: stored || name, votes: Number(votes) || 1},
      merged: target !== key,
      ...(await board()),
    });
  } catch (e) {
    res.status(502).json({error: 'That didn\'t go through. Try again.'});
  }
};

module.exports.keyOf = keyOf;
module.exports.canonical = canonical;
module.exports.distance = distance;
module.exports.closest = closest;
