// "Who should ride next?" A tiny suggestion board for the site.
//
// GET  /api/suggestions          the 30 most-wanted characters
// POST /api/suggestions {name}   suggest a character, or back one already listed
//
// Storage is Redis over Upstash's REST API. Connect a store in the Vercel
// dashboard (Storage -> Upstash Redis -> connect to this project) and Vercel
// injects KV_REST_API_URL and KV_REST_API_TOKEN. Until then every request
// answers 503 and the page points people at GitHub instead.
//
// Names are shown to every visitor, so they are length-limited, restricted to
// ordinary characters, and anything that looks like a link is refused. Remove
// a bad entry with: ZREM suggest:votes <key>  and  HDEL suggest:names <key>.

const URL_ = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
const TOKEN = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;

const VOTES = 'suggest:votes';
const NAMES = 'suggest:names';
const PER_DAY = 25;

// Already in the app: suggesting one of these points you at it instead.
const LIVE = {
  bugsbunny: 'Bugs Bunny', cookiemonster: 'Cookie Monster', daffyduck: 'Daffy Duck',
  elmo: 'Elmo', tigger: 'Tigger', winniethepooh: 'Winnie the Pooh', pooh: 'Winnie the Pooh',
  paddington: 'Paddington', mickeymouse: 'Mickey Mouse', mickey: 'Mickey Mouse', darthvader: 'Darth Vader', vader: 'Darth Vader',
  batman: 'Batman', gordonramsay: 'Gordon Ramsay', ericcartman: 'Eric Cartman', cartman: 'Eric Cartman',
};

// A few to start the board so it is never empty.
const SEEDS = ['SpongeBob', 'Yoda', 'Shrek', 'Homer Simpson', 'Mario', 'Scooby-Doo', 'Optimus Prime', 'Stewie Griffin'];

const keyOf = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, '');

async function redis(commands) {
  const res = await fetch(`${URL_}/pipeline`, {
    method: 'POST',
    headers: {Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json'},
    body: JSON.stringify(commands),
  });
  if (!res.ok) throw new Error(`redis ${res.status}`);
  return (await res.json()).map((r) => r.result);
}

async function board() {
  let [ranked] = await redis([['ZREVRANGE', VOTES, '0', '29', 'WITHSCORES']]);
  if (!ranked.length) {
    await redis([
      ...SEEDS.map((s) => ['HSETNX', NAMES, keyOf(s), s]),
      ...SEEDS.map((s) => ['ZADD', VOTES, 'NX', '1', keyOf(s)]),
    ]);
    [ranked] = await redis([['ZREVRANGE', VOTES, '0', '29', 'WITHSCORES']]);
  }
  const keys = ranked.filter((_, i) => i % 2 === 0);
  const [names] = keys.length ? await redis([['HMGET', NAMES, ...keys]]) : [[]];
  return keys.map((key, i) => ({key, name: names[i] || key, votes: Number(ranked[i * 2 + 1])}));
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
      res.status(200).json({items: await board()});
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
    const key = keyOf(name);
    if (LIVE[key]) {
      res.status(200).json({live: LIVE[key], items: await board()});
      return;
    }
    const ip = String(req.headers['x-forwarded-for'] || 'unknown').split(',')[0].trim();
    const limitKey = `suggest:rate:${ip}:${new Date().toISOString().slice(0, 10)}`;
    const [count] = await redis([['INCR', limitKey], ['EXPIRE', limitKey, '90000']]);
    if (count > PER_DAY) {
      res.status(429).json({error: 'That\'s plenty for today. Thanks!'});
      return;
    }
    await redis([['HSETNX', NAMES, key, name], ['ZINCRBY', VOTES, '1', key]]);
    res.status(200).json({items: await board()});
  } catch (e) {
    res.status(502).json({error: 'That didn\'t go through. Try again.'});
  }
};
