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
      case 'ZSCORE': return data.has(key) && data.get(key).has(args[0]) ? String(data.get(key).get(args[0])) : null;
      case 'SMEMBERS': return data.has(key) ? [...data.get(key)] : [];
      case 'SADD': { const s = set(key); args.forEach((a) => s.add(a)); return args.length; }
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

async function call(handler, {method = 'POST', body, ip = '203.0.113.7', ua = BROWSER, headers: extra = {}} = {}) {
  const res = {
    code: 0, body: undefined, headers: {},
    setHeader(k, v) { this.headers[k.toLowerCase()] = v; },
    status(c) { this.code = c; return this; },
    json(b) { this.body = b; return this; },
    end() { return this; },
  };
  // What a same-origin fetch from the site carries.
  const headers = {'x-forwarded-for': `${ip}, 10.0.0.1`, host: 'backseatnav.com'};
  if (ua) headers['user-agent'] = ua;
  if (body && typeof body === 'object' && !Buffer.isBuffer(body)) headers['content-type'] = 'application/json';
  for (const [k, v] of Object.entries(extra)) {
    if (v === undefined) delete headers[k];
    else headers[k] = v;
  }
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
  // Over quota, Upstash answers 200 with an error per command.
  global.fetch = async () => ({ok: true, json: async () => [{error: 'ERR max daily request limit exceeded'}]});
  const res = await call(load('tally.js'), {body: {event: 'suggest'}});
  assert.equal(res.code, 502);
  assert.ok(!JSON.stringify(res.body).includes('limit exceeded'), 'no store error leaks to the client');
  global.fetch = async () => { throw new Error('network down'); };
  assert.equal((await call(load('tally.js'), {body: {event: 'suggest'}})).code, 502);
});

test('track refuses posts from other sites', async () => {
  const redis = fakeRedis();
  connect(redis);
  const track = load('tally.js');
  const body = {event: 'download', character: 'elmo', method: 'tap'};
  for (const headers of [
    {origin: 'https://evil.example'},
    {origin: 'null'},
    {origin: 'https://backseatnav.com.evil.example'},
    {'sec-fetch-site': 'cross-site'},
  ]) {
    assert.equal((await call(track, {body, headers})).code, 403, JSON.stringify(headers));
  }
  assert.equal(redis.calls.length, 0);
  // The site itself, www, and a preview deployment posting to its own host.
  assert.equal((await call(track, {body, headers: {origin: 'https://backseatnav.com', 'sec-fetch-site': 'same-origin'}})).code, 204);
  assert.equal((await call(track, {body, headers: {origin: 'https://www.backseatnav.com'}})).code, 204);
  assert.equal((await call(track, {body, headers: {origin: 'https://backseat-abc.vercel.app', host: 'backseat-abc.vercel.app'}})).code, 204);
});

test('track counts film and docs pages without inventing fields', async () => {
  const redis = fakeRedis();
  connect(redis);
  const track = load('tally.js');
  for (const page of ['/film', '/film/', '/film/index', '/docs/quickstart', '/docs/cli-reference']) {
    assert.equal((await call(track, {body: {event: 'pageview', page}})).code, 204, page);
  }
  assert.equal((await call(track, {body: {event: 'doc_read', page: '/docs/quickstart'}})).code, 204);
  for (const page of ['/docs/../admin', '/docs/A B', '/docs/x/y', `/docs/${'a'.repeat(200)}`, 42, {}]) {
    assert.equal((await call(track, {body: {event: 'pageview', page}})).code, 400, String(page));
  }
  const total = redis.data.get('stats:total');
  assert.equal(total.get('pageview:/film'), 3);
  assert.equal(total.get('pageview:/docs'), 2);
  assert.equal(total.get('doc_read:/docs'), 1);
  assert.deepEqual([...total.keys()].filter((k) => k.includes('/docs/')), []);
});

test('track caps a network that rotates its user agent', async () => {
  const redis = fakeRedis();
  connect(redis);
  const track = load('tally.js');
  const body = {event: 'character_click', character: 'elmo'};
  let last;
  for (let i = 0; i < 3001; i++) last = await call(track, {body, ua: `${BROWSER} v${i}`});
  assert.equal(last.code, 429);
  assert.equal(redis.data.get('stats:total').get('character_click'), 3000);
});

test('track rejects bodies that are not a small JSON object', async () => {
  const redis = fakeRedis();
  connect(redis);
  const track = load('tally.js');
  for (const body of ['null', '[1,2]', '"x"', Buffer.from('{bad')]) {
    assert.equal((await call(track, {body})).code, 400, String(body));
  }
  // Vercel throws from the req.body getter when a JSON body is malformed.
  const res = {code: 0, setHeader() {}, status(c) { this.code = c; return this; }, json() { return this; }, end() { return this; }};
  const req = {method: 'POST', headers: {'user-agent': BROWSER}};
  Object.defineProperty(req, 'body', {get() { throw new Error('Invalid JSON'); }});
  await track(req, res);
  assert.equal(res.code, 400);
});

// ---- api/_store.js ----

test('the client IP comes from the headers Vercel sets', () => {
  const {clientIp} = load('_store.js');
  assert.equal(clientIp({headers: {'x-vercel-forwarded-for': '198.51.100.1', 'x-forwarded-for': '1.2.3.4'}}), '198.51.100.1');
  assert.equal(clientIp({headers: {'x-real-ip': '198.51.100.2', 'x-forwarded-for': '1.2.3.4'}}), '198.51.100.2');
  assert.equal(clientIp({headers: {'x-forwarded-for': '198.51.100.3, 10.0.0.1'}}), '198.51.100.3');
  assert.equal(clientIp({headers: {}}), '');
});

test('rate limits treat an IPv6 /64 as one network', () => {
  const {ipBucket} = load('_store.js');
  assert.equal(ipBucket('2001:db8:1:2:aaaa::1'), ipBucket('2001:db8:1:2:bbbb:cccc:dddd:eeee'));
  assert.notEqual(ipBucket('2001:db8:1:2::1'), ipBucket('2001:db8:1:3::1'));
  assert.equal(ipBucket('2001:db8::1'), '2001:db8:0:0::/64');
  assert.equal(ipBucket('::ffff:203.0.113.5'), '203.0.113.5');
  assert.equal(ipBucket('203.0.113.5'), '203.0.113.5');
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

test('suggestions refuses offensive, invisible and lookalike names', async () => {
  const redis = fakeRedis();
  connect(redis);
  const handler = load('suggestions.js');
  const bad = [
    'F U C K', 'fuuuuck', 'sh1t head', 'big cock', 'Hitler',
    'Yоda', // a Cyrillic o in Yoda
    'Yo​da', // zero-width space
    'ab‮cd', // right-to-left override
    'ㅤㅤㅤ', // Hangul fillers render blank
    'Za̷lgo', // combining marks
    '\u{1F44D} Thumbs', 'x.com/promo', 'mail me@x',
  ];
  for (const name of bad) assert.equal((await suggest(handler, name, '203.0.113.50')).code, 400, JSON.stringify(name));
  for (const name of [null, 42, {a: 1}, ['Yoda'], 'y'.repeat(41), 'y'.repeat(5000)]) {
    assert.equal((await call(handler, {body: {name}})).code, 400, JSON.stringify(name).slice(0, 20));
  }
  assert.equal(redis.data.has('suggest:names'), false);
});

test('suggestions keeps real names that contain rude-looking letters', async () => {
  connect(fakeRedis());
  const handler = load('suggestions.js');
  const fine = ['Moby Dick', 'Dick Dastardly', 'Cockatoo Carl', 'Raccoon', 'Grape Ape', 'Benedict Cumberbatch',
    'Bob the Builder', 'Nigel Thornberry', 'Puss in Boots', 'Essex Girl', 'Wall-E', 'R2-D2', 'Чебурашка', 'ドラえもん'];
  for (const [i, name] of fine.entries()) {
    const res = await suggest(handler, name, `203.0.113.${100 + i}`);
    assert.equal(res.code, 200, `${name}: ${JSON.stringify(res.body)}`);
  }
  // Fullwidth and "mathematical" letters are folded to plain ones before they are shown.
  const wide = await suggest(handler, 'Ｓｈｒｅｋ', '203.0.113.130');
  assert.equal(wide.body.added.name, 'Shrek');
});

test('suggestions counts one vote per network per character per day', async () => {
  const redis = fakeRedis();
  connect(redis);
  const handler = load('suggestions.js');
  const first = await suggest(handler, 'Kermit the Frog', '198.51.100.7');
  assert.equal(first.body.added.votes, 1);
  assert.equal(first.body.counted, true);
  const again = await suggest(handler, 'kermit the frog!', '198.51.100.7');
  assert.equal(again.code, 200);
  assert.equal(again.body.counted, false);
  assert.equal(again.body.added.votes, 1);
  // A new address in the same IPv6 /64 is the same network.
  await suggest(handler, 'Kermit the Frog', '2001:db8:5:6::1');
  const same64 = await suggest(handler, 'Kermit the Frog', '2001:db8:5:6::ffff');
  assert.equal(same64.body.counted, false);
  assert.equal(same64.body.added.votes, 2);
  assert.equal(redis.data.get('suggest:votes').get('kermitthefrog'), 2);
});

test('suggestions never stores an IP address', async () => {
  const redis = fakeRedis();
  connect(redis);
  await suggest(load('suggestions.js'), 'Kermit the Frog', '198.51.100.23');
  const everything = JSON.stringify(redis.calls);
  assert.ok(!everything.includes('198.51.100.23'));
});

test('suggestions refuses cross-site and non-JSON posts', async () => {
  const redis = fakeRedis();
  connect(redis);
  const handler = load('suggestions.js');
  const body = {name: 'Kermit'};
  assert.equal((await call(handler, {body, headers: {origin: 'https://evil.example'}})).code, 403);
  assert.equal((await call(handler, {body, headers: {'sec-fetch-site': 'cross-site'}})).code, 403);
  assert.equal((await call(handler, {body: JSON.stringify(body), headers: {'content-type': 'text/plain'}})).code, 415);
  assert.equal((await call(handler, {body, headers: {'content-type': undefined}})).code, 415);
  assert.equal(redis.calls.length, 0);
  assert.equal((await call(handler, {body, headers: {origin: 'https://backseatnav.com'}})).code, 200);
});

test('suggestions honours the block list and the caps on new names', async () => {
  const redis = fakeRedis();
  connect(redis);
  const handler = load('suggestions.js');
  redis.data.set('suggest:blocked', new Set(['kermitthefrog']));
  assert.equal((await suggest(handler, 'Kermit the Frog', '198.51.100.1')).code, 400);
  assert.equal((await suggest(handler, 'Kermit teh Frog', '198.51.100.2')).code, 400, 'near-misses too');
  await call(handler, {method: 'GET'}); // seeds the board
  redis.data.set(`suggest:new:${new Date().toISOString().slice(0, 10)}`, 500);
  assert.equal((await suggest(handler, 'Totally New', '198.51.100.3')).code, 429);
  // Backing a name already on the list still works.
  assert.equal((await suggest(handler, 'Shrek', '198.51.100.4')).code, 200);
});

test('suggestions answers a character already riding without touching Redis', async () => {
  const redis = fakeRedis();
  connect(redis);
  const res = await suggest(load('suggestions.js'), 'Elmo');
  assert.equal(res.body.live, 'Elmo');
  assert.equal(redis.calls.length, 0);
});

test('suggestions caches the board briefly and degrades when Redis is down', async () => {
  connect(fakeRedis());
  const handler = load('suggestions.js');
  const ok = await call(handler, {method: 'GET'});
  assert.match(ok.headers['cache-control'], /s-maxage=\d+/);
  global.fetch = async () => ({ok: true, json: async () => [{error: 'ERR max requests limit exceeded'}, {error: 'x'}]});
  const down = await call(handler, {method: 'GET'});
  assert.equal(down.code, 502);
  assert.equal(down.headers['cache-control'], 'no-store');
  assert.equal((await suggest(handler, 'Kermit')).code, 502);
});
