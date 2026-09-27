// api/tally.js, api/stats.js and api/suggestions.js against an in-memory Upstash pipeline.
// Run with: node --test tests/api   (tests/test_api.py runs it too)

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const API = path.join(__dirname, '..', '..', 'api');
const SLUGS = require('../../site/voices.json').voices.map((v) => v.slug);

// ---- a Redis that speaks just enough of Upstash's /pipeline ----

function fakeRedis() {
  const data = new Map();
  const calls = [];
  const hash = (k) => (data.has(k) ? data.get(k) : data.set(k, new Map()).get(k));
  const set = (k) => (data.has(k) ? data.get(k) : data.set(k, new Set()).get(k));
  const run = ([cmd, key, ...args]) => {
    switch (cmd) {
      case 'INCR': data.set(key, (Number(data.get(key)) || 0) + 1); return data.get(key);
      case 'EXPIRE': return data.has(key) ? 1 : 0;
      case 'HINCRBY': { const h = hash(key); h.set(args[0], (h.get(args[0]) || 0) + Number(args[1])); return h.get(args[0]); }
      case 'HGETALL': return data.has(key) ? [...data.get(key)].flatMap(([f, v]) => [f, String(v)]) : [];
      case 'HMGET': return args.map((f) => (data.has(key) && data.get(key).has(f) ? String(data.get(key).get(f)) : null));
      case 'PFADD': { const s = set(key); const before = s.size; args.forEach((a) => s.add(a)); return s.size > before ? 1 : 0; }
      case 'PFCOUNT': return data.has(key) ? data.get(key).size : 0;
      case 'SET': if (args[1] === 'NX' && data.has(key)) return null; data.set(key, args[0]); return 'OK';
      case 'GET': return data.has(key) ? data.get(key) : null;
      case 'HSETNX': { const h = hash(key); if (h.has(args[0])) return 0; h.set(args[0], args[1]); return 1; }
      case 'HGET': return data.has(key) && data.get(key).has(args[0]) ? String(data.get(key).get(args[0])) : null;
      case 'HKEYS': return data.has(key) ? [...data.get(key).keys()] : [];
      case 'ZADD': { const z = hash(key); const [flag, score, member] = args; if (flag === 'NX' && z.has(member)) return 0; z.set(member, Number(score)); return 1; }
      case 'ZINCRBY': { const z = hash(key); z.set(args[1], (z.get(args[1]) || 0) + Number(args[0])); return String(z.get(args[1])); }
      case 'ZCARD': return data.has(key) ? data.get(key).size : 0;
      case 'ZREVRANGE': {
        const ranked = data.has(key) ? [...data.get(key)].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? 1 : -1)) : [];
        return ranked.slice(Number(args[0]), Number(args[1]) + 1).flatMap(([m, s]) => [m, String(s)]);
      }
      default: throw new Error(`fake redis: ${cmd}`);
    }
  };
  const fetch = async (url, init) => {
    assert.equal(url, 'https://redis.test/pipeline');
    assert.equal(init.headers.Authorization, 'Bearer secret');
    const commands = JSON.parse(init.body);
    commands.forEach((c) => c.forEach((part) => assert.equal(typeof part, 'string', `${c}`)));
    calls.push(commands);
    return {ok: true, json: async () => commands.map((c) => ({result: run(c)}))};
  };
  return {data, calls, fetch};
}

function load(name) {
  for (const key of Object.keys(require.cache)) if (key.startsWith(API)) delete require.cache[key];
  return require(path.join(API, name));
}

function connect(redis) {
  process.env.KV_REST_API_URL = 'https://redis.test';
  process.env.KV_REST_API_TOKEN = 'secret';
  delete process.env.VERCEL_ENV;
  global.fetch = redis.fetch;
}

function disconnect() {
  for (const k of ['KV_REST_API_URL', 'KV_REST_API_TOKEN', 'UPSTASH_REDIS_REST_URL', 'UPSTASH_REDIS_REST_TOKEN']) {
    delete process.env[k];
  }
  global.fetch = async () => { throw new Error('no network in tests'); };
}

const BROWSER = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari/604.1';

async function call(handler, {method = 'POST', body, ip = '203.0.113.7', ua = BROWSER} = {}) {
  const res = {
    code: 0, body: undefined, headers: {},
    setHeader(k, v) { this.headers[k.toLowerCase()] = v; },
    status(c) { this.code = c; return this; },
    json(b) { this.body = b; return this; },
    end() { return this; },
  };
  const headers = {'x-forwarded-for': `${ip}, 10.0.0.1`};
  if (ua) headers['user-agent'] = ua;
  await handler({method, headers, body}, res);
  return res;
}

// ---- api/tally.js ----

test('track answers 503 when no store is connected', async () => {
  disconnect();
  const res = await call(load('tally.js'), {body: {event: 'pageview', page: '/index'}});
  assert.equal(res.code, 503);
});

test('track counts each event into all-time and per-day hashes', async () => {
  const redis = fakeRedis();
  connect(redis);
  const track = load('tally.js');
  const events = [
    {event: 'pageview', page: '/index'},
    {event: 'character_click', character: 'batman'},
    {event: 'download', character: 'batman', method: 'tap'},
    {event: 'download', character: 'elmo', method: 'qr'},
    {event: 'install_worked', character: 'batman', worked: 'yes'},
    {event: 'github_click', page: '/how-it-works'},
    {event: 'doc_read', page: '/make-your-own'},
    {event: 'suggest'},
  ];
  for (const body of events) assert.equal((await call(track, {body})).code, 204, JSON.stringify(body));
  // sendBeacon posts text/plain, which arrives as a string.
  assert.equal((await call(track, {body: JSON.stringify({event: 'pageview', page: '/stats'})})).code, 204);

  const total = redis.data.get('stats:total');
  const day = redis.data.get(`stats:day:${new Date().toISOString().slice(0, 10)}`);
  for (const h of [total, day]) {
    assert.equal(h.get('pageview'), 2);
    assert.equal(h.get('pageview:/index'), 1);
    assert.equal(h.get('pageview:/stats'), 1);
    assert.equal(h.get('character_click:batman'), 1);
    assert.equal(h.get('download'), 2);
    assert.equal(h.get('download:tap'), 1);
    assert.equal(h.get('download:qr'), 1);
    assert.equal(h.get('download:batman:tap'), 1);
    assert.equal(h.get('download:elmo'), 1);
    assert.equal(h.get('install_worked:batman:yes'), 1);
    assert.equal(h.get('github_click:/how-it-works'), 1);
    assert.equal(h.get('doc_read:/make-your-own'), 1);
    assert.equal(h.get('suggest'), 1);
  }
  assert.equal(redis.data.get('stats:uv:all').size, 1);
});

test('track never stores a raw IP or user agent', async () => {
  const redis = fakeRedis();
  connect(redis);
  await call(load('tally.js'), {body: {event: 'pageview', page: '/index'}, ip: '198.51.100.23'});
  const everything = JSON.stringify(redis.calls);
  assert.ok(!everything.includes('198.51.100.23'));
  assert.ok(!everything.includes('iPhone'));
});

test('track counts two people as two visitors, one person once', async () => {
  const redis = fakeRedis();
  connect(redis);
  const track = load('tally.js');
  await call(track, {body: {event: 'pageview', page: '/index'}, ip: '203.0.113.1'});
  await call(track, {body: {event: 'pageview', page: '/install'}, ip: '203.0.113.1'});
  await call(track, {body: {event: 'pageview', page: '/index'}, ip: '203.0.113.2'});
  assert.equal(redis.data.get('stats:uv:all').size, 2);
});

test('track refuses anything off the list', async () => {
  const redis = fakeRedis();
  connect(redis);
  const track = load('tally.js');
  const bad = [
    {event: 'pageview', page: '/admin'},
    {event: 'pageview'},
    {event: 'character_click', character: 'spongebob'},
    {event: 'character_click', character: '__proto__'},
    {event: 'download', character: 'batman'},
    {event: 'download', character: 'batman', method: 'email'},
    {event: 'install_worked', character: 'batman', worked: 'maybe'},
    {event: 'doc_read', page: '/index'},
    {event: 'purchase'},
    {},
  ];
  for (const body of bad) assert.equal((await call(track, {body})).code, 400, JSON.stringify(body));
  assert.equal((await call(track, {body: '{not json'})).code, 400);
  assert.equal((await call(track, {body: 'x'.repeat(3000)})).code, 400);
  assert.equal((await call(track, {method: 'GET'})).code, 405);
  assert.equal(redis.calls.length, 0);
});

test('track accepts every character on the site', async () => {
  const redis = fakeRedis();
  connect(redis);
  const track = load('tally.js');
  assert.equal(SLUGS.length, 12);
  for (const character of SLUGS) {
    assert.equal((await call(track, {body: {event: 'character_click', character}})).code, 204);
  }
});

test('track ignores bots and preview deployments', async () => {
  const redis = fakeRedis();
  connect(redis);
  const track = load('tally.js');
  const body = {event: 'pageview', page: '/index'};
  assert.equal((await call(track, {body, ua: 'Mozilla/5.0 (compatible; Googlebot/2.1)'})).code, 204);
  assert.equal((await call(track, {body, ua: ''})).code, 204);
  process.env.VERCEL_ENV = 'preview';
  assert.equal((await call(track, {body})).code, 204);
  delete process.env.VERCEL_ENV;
  assert.equal(redis.calls.length, 0);
});

test('track rate-limits one visitor per day', async () => {
  const redis = fakeRedis();
  connect(redis);
  const track = load('tally.js');
  const body = {event: 'character_click', character: 'elmo'};
  let last;
  for (let i = 0; i < 401; i++) last = await call(track, {body});
  assert.equal(last.code, 429);
  assert.equal(redis.data.get('stats:total').get('character_click'), 400);
  // Somebody else is unaffected.
  assert.equal((await call(track, {body, ip: '203.0.113.99'})).code, 204);
});

test('track answers 502, not a crash, when Redis fails', async () => {
  connect(fakeRedis());
  global.fetch = async () => ({ok: false, status: 500, json: async () => ({})});
  assert.equal((await call(load('tally.js'), {body: {event: 'suggest'}})).code, 502);
});

// ---- api/stats.js ----

test('stats answers 503 when no store is connected', async () => {
  disconnect();
  const res = await call(load('stats.js'), {method: 'GET'});
  assert.equal(res.code, 503);
});

test('stats starts at zero with every character listed', async () => {
  connect(fakeRedis());
  const res = await call(load('stats.js'), {method: 'GET'});
  assert.equal(res.code, 200);
  assert.equal(res.body.totals.downloads, 0);
  assert.equal(res.body.totals.visitors, 0);
  assert.equal(res.body.since, null);
  assert.equal(res.body.characters.length, 12);
  assert.equal(res.body.daily.length, 30);
  assert.match(res.headers['cache-control'], /s-maxage=60/);
});

test('stats adds up what track counted', async () => {
  const redis = fakeRedis();
  connect(redis);
  const track = load('tally.js');
  const stats = load('stats.js');
  const send = (body, ip) => call(track, {body, ip});
  await send({event: 'pageview', page: '/index'}, '203.0.113.1');
  await send({event: 'pageview', page: '/how-it-works'}, '203.0.113.2');
  await send({event: 'doc_read', page: '/how-it-works'}, '203.0.113.2');
  await send({event: 'download', character: 'elmo', method: 'tap'}, '203.0.113.1');
  await send({event: 'download', character: 'elmo', method: 'qr'}, '203.0.113.2');
  await send({event: 'download', character: 'batman', method: 'tap'}, '203.0.113.2');
  await send({event: 'character_click', character: 'batman'}, '203.0.113.1');
  await send({event: 'install_worked', character: 'elmo', worked: 'yes'}, '203.0.113.1');
  await send({event: 'install_worked', character: 'elmo', worked: 'no'}, '203.0.113.2');
  await send({event: 'github_click', page: '/index'}, '203.0.113.1');

  const {body} = await call(stats, {method: 'GET'});
  assert.equal(body.totals.visitors, 2);
  assert.equal(body.totals.pageviews, 2);
  assert.equal(body.totals.downloads, 3);
  assert.equal(body.totals.install_taps, 2);
  assert.equal(body.totals.qr_opens, 1);
  assert.equal(body.totals.confirmed_installs, 1);
  assert.equal(body.totals.failed_installs, 1);
  assert.equal(body.totals.character_clicks, 1);
  assert.equal(body.totals.doc_reads, 1);
  assert.equal(body.totals.github_clicks, 1);
  assert.deepEqual(body.docs['/how-it-works'], {views: 1, reads: 1});
  assert.equal(body.pages['/index'], 1);
  assert.equal(body.since, new Date().toISOString().slice(0, 10));

  const [first, second] = body.characters;
  assert.deepEqual(first, {slug: 'elmo', name: 'Elmo', downloads: 2, taps: 1, qr: 1, clicks: 0, confirmed: 1, failed: 1});
  assert.equal(second.slug, 'batman');

  const todayRow = body.daily[body.daily.length - 1];
  assert.equal(todayRow.date, new Date().toISOString().slice(0, 10));
  assert.deepEqual(todayRow, {date: todayRow.date, visitors: 2, pageviews: 2, downloads: 3, clicks: 1});
  assert.equal(body.daily[0].downloads, 0);
});

test('stats is GET only', async () => {
  connect(fakeRedis());
  assert.equal((await call(load('stats.js'), {method: 'POST'})).code, 405);
});

// ---- api/suggestions.js ----

const suggest = (handler, name, ip) => call(handler, {body: {name}, ip});

test('suggestions answers 503 when no store is connected', async () => {
  disconnect();
  assert.equal((await call(load('suggestions.js'), {method: 'GET'})).code, 503);
});

test('suggestions seeds the board and honours a limit', async () => {
  connect(fakeRedis());
  const handler = load('suggestions.js');
  const all = await call(handler, {method: 'GET'});
  assert.equal(all.code, 200);
  assert.equal(all.body.items.length, 8);
  assert.equal(all.body.total, 8);
  const handlerReq = {method: 'GET', headers: {}, query: {limit: '4'}};
  const res = {code: 0, setHeader() {}, status(c) { this.code = c; return this; }, json(b) { this.body = b; return this; }};
  await handler(handlerReq, res);
  assert.equal(res.body.items.length, 4);
  assert.equal(res.body.total, 8);
});

test('suggestions keys ignore case, accents, punctuation and a leading "the"', () => {
  const {keyOf, canonical} = load('suggestions.js');
  assert.equal(keyOf('Mickéy-Mouse!'), 'mickeymouse');
  assert.equal(keyOf('  the Grinch '), 'grinch');
  assert.equal(keyOf('Tom & Jerry'), keyOf('tom and jerry'));
  assert.equal(canonical('SpongeBob SquarePants'), 'spongebob');
  assert.equal(canonical('Homer'), 'homersimpson');
});

test('suggestions measures typos, swaps included', () => {
  const {distance, closest} = load('suggestions.js');
  assert.equal(distance('shrek', 'shrke', 2), 1);
  assert.equal(distance('shrek', 'shrk', 2), 1);
  assert.equal(distance('yoda', 'darthvader', 2), 3);
  assert.equal(closest('bert', ['bart']), null);
  assert.equal(closest('shrke', ['shrek', 'yoda']), 'shrek');
  assert.equal(closest('homersimsn', ['homersimpson']), 'homersimpson');
  assert.equal(closest('rocky2', ['rocky3']), null);
});

test('suggestions merges spellings into one entry', async () => {
  const redis = fakeRedis();
  connect(redis);
  const handler = load('suggestions.js');
  await call(handler, {method: 'GET'}); // seeds the board
  const first = await suggest(handler, 'Kermit the Frog', '203.0.113.1');
  assert.equal(first.code, 200);
  assert.equal(first.body.added.key, 'kermitthefrog');
  assert.equal(first.body.merged, false);
  const typo = await suggest(handler, 'kermit teh frog', '203.0.113.2');
  assert.equal(typo.body.added.key, 'kermitthefrog');
  assert.equal(typo.body.added.name, 'Kermit the Frog');
  assert.equal(typo.body.added.votes, 2);
  assert.equal(typo.body.merged, true);
  const shouty = await suggest(handler, 'KERMIT-THE-FROG!', '203.0.113.3');
  assert.equal(shouty.body.added.votes, 3);
  const seeded = await suggest(handler, 'Sponge Bob Square Pants', '203.0.113.4');
  assert.equal(seeded.body.added.key, 'spongebob');
  assert.equal(seeded.body.added.name, 'SpongeBob');
  assert.equal(seeded.body.added.votes, 2);
  const names = redis.data.get('suggest:names');
  assert.equal([...names.keys()].filter((k) => k.startsWith('kermit')).length, 1);
});

test('suggestions points at a character already riding, typos and all', async () => {
  const redis = fakeRedis();
  connect(redis);
  const handler = load('suggestions.js');
  for (const [typed, name] of [['Mickey Mous', 'Mickey Mouse'], ['darth vadr', 'Darth Vader'], ['pooh', 'Winnie the Pooh'], ['ELMO', 'Elmo']]) {
    const res = await suggest(handler, typed);
    assert.equal(res.code, 200, typed);
    assert.equal(res.body.live, name, typed);
    assert.equal(res.body.added, undefined, typed);
  }
  assert.equal(redis.data.has('suggest:names') && redis.data.get('suggest:names').has('mickeymous'), false);
});

test('suggestions still validates and rate-limits', async () => {
  connect(fakeRedis());
  const handler = load('suggestions.js');
  assert.equal((await suggest(handler, 'x')).code, 400);
  assert.equal((await suggest(handler, 'see www.example.com')).code, 400);
  assert.equal((await suggest(handler, '<b>hi</b>')).code, 400);
  for (let i = 0; i < 25; i++) assert.equal((await suggest(handler, `Robot ${i}`, '203.0.113.9')).code, 200);
  assert.equal((await suggest(handler, 'One Too Many', '203.0.113.9')).code, 429);
  assert.equal((await call(handler, {method: 'DELETE'})).code, 405);
});
