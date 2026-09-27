// THE GETAWAY, action-chase revision: every tunable value of the film, 30.0 s
// at 24 fps (720 frames), 1920x1080 full frame. Plan, shot list and prompts:
// film/runway4/plan.md (the first cut is film/runway3/plan.md). Footage and
// sound are staged into public/ga/ by scripts/stage_getaway.py; the voice
// lines by scripts/build_getaway_voices.py. Every cut sits on a whole frame:
// shots are laid end to end by their length in frames.
//
// NEW shots (N1..N7) are staged from film/runway4/takes/ when a take exists,
// otherwise from the approved still as a held frame; src/getaway-media.json
// (written by the stage script) tells the picture which is which, and a held
// still gets a subtle push so the preview moves. Dropping a take in and
// re-staging is all production needs, plus setting that shot's `srcIn`.

export const FPS = 24;
export const TOTAL_FRAMES = 720;
export const TOTAL = TOTAL_FRAMES / FPS;

// Colours and type are the site's (site/style.css, site/characters.css).
export const BRAND = {
  sun: '#ffd23f',
  ink: '#15172b',
  white: '#ffffff',
};
export const FONT = {
  display: "'Bagel Fat One', sans-serif",
  body: "'Bricolage Grotesque', sans-serif",
  mono: "'JetBrains Mono', monospace",
};

export type Cast = {slug: string; name: string; bg: string};
// Site order (site/voices.json); colours from site/characters.css.
export const CAST: Cast[] = [
  {slug: 'bugs-bunny', name: 'Bugs Bunny', bg: '#ffd2a1'},
  {slug: 'cookie-monster', name: 'Cookie Monster', bg: '#bfd6ff'},
  {slug: 'daffy-duck', name: 'Daffy Duck', bg: '#a8e6d6'},
  {slug: 'elmo', name: 'Elmo', bg: '#ffd0cc'},
  {slug: 'tigger', name: 'Tigger', bg: '#ffd9b0'},
  {slug: 'pooh', name: 'Winnie the Pooh', bg: '#ffe9a8'},
  {slug: 'paddington', name: 'Paddington', bg: '#c9dcf5'},
  {slug: 'hagrid', name: 'Hagrid', bg: '#e8dcc8'},
  {slug: 'darth-vader', name: 'Darth Vader', bg: '#ffc9c9'},
  {slug: 'batman', name: 'Batman', bg: '#fff0a8'},
  {slug: 'gordon-ramsay', name: 'Gordon Ramsay', bg: '#ffe3d3'},
  {slug: 'eric-cartman', name: 'Eric Cartman', bg: '#d6f3ff'},
];
export const castOf = (slug: string) => CAST.find((c) => c.slug === slug)!;

// ------------------------------------------------------------------ picture

/** A source rectangle in 1920x1080 clip pixels. */
export type Rect = {x: number; y: number; w: number; h: number};

/** Garbled AI text to soften: keyframes of [frame into the shot, rect], interpolated. */
export type BlurTrack = {keys: [number, Rect][]; px?: number};

export type ShotSpec = {
  id: string;
  beat: string;
  /** File in public/ga/clips/ (without .mp4). N1..N7 are the NEW shots (film/runway4). */
  clip: string;
  /** Seconds into the source clip at the shot's first frame. */
  srcIn: number;
  /** Length in film frames. */
  frames: number;
  /** Picture speed (voices are never touched). */
  rate?: number;
  /** Framing: a crop at `scale` around (cx, cy); with `to`, a slow push. */
  f16?: {scale: number; cx: number; cy: number; to?: number};
  blur?: BlurTrack[];
  /** Soften the out-of-focus background above this clip y (neon signs with glyph-like shapes). */
  band?: number;
  /** Per-clip match before the campaign grade. */
  match?: {brightness?: number; contrast?: number; saturate?: number};
};

/** A held still (placeholder for a NEW shot) pushes in by this much over the shot. */
export const PLACEHOLDER_PUSH = 0.06;

const CUT: ShotSpec[] = [
  // 0.000 cold open: alarm, rain, neon. The three SPRINT out of the doorway and dive into the car.
  {id: 'SPRINT_A', beat: 'sprint to the car', clip: 'N1', srcIn: 0.5, frames: 48},
  // 2.000 same angle, later: the dive in, three doors slam.
  {id: 'SPRINT_B', beat: 'dive in, doors slam', clip: 'N1', srcIn: 4.5, frames: 24},
  // 3.000 "I've got navigation": phone up, thumb to the screen (thumb lands at src 0.45).
  {id: 'PHONE_UP', beat: 'phone up + tap', clip: 'V02B', srcIn: 0.0, frames: 18,
    f16: {scale: 1.12, cx: 960, cy: 520}, band: 150},
  // 3.750 Elmo: the driver's eyes go wide; a snap focus pull (3x) to the passenger's flat look.
  {id: 'RACK_A', beat: 'Elmo: driver eyes', clip: 'V03', srcIn: 0.72, frames: 55},
  {id: 'RACK_B', beat: 'Elmo: focus pull', clip: 'V03', srcIn: 3.0, frames: 18, rate: 3},
  {id: 'RACK_C', beat: 'Elmo: passenger', clip: 'V03', srcIn: 5.25, frames: 33},
  // 8.167 the head-turn chain, three cuts, each tighter. Silence.
  {id: 'CHAIN1', beat: 'driver turns to passenger', clip: 'V02A', srcIn: 1.55, frames: 15,
    f16: {scale: 1.0, cx: 960, cy: 540}, band: 150},
  {id: 'CHAIN2', beat: 'passenger turns to the back', clip: 'V02A', srcIn: 4.55, frames: 15,
    f16: {scale: 1.18, cx: 760, cy: 500}, band: 150},
  {id: 'CHAIN3', beat: 'backseat shrug', clip: 'V02A', srcIn: 6.45, frames: 17,
    f16: {scale: 1.36, cx: 960, cy: 470}, band: 150},
  // 10.125 tyres spin, smoke and spray; sirens erupt.
  {id: 'TYRE', beat: 'tyres spin', clip: 'V05', srcIn: 1.15, frames: 12, rate: 1.3},
  // 10.625 launch: the sedan fishtails out; two patrol cars slide round the corner after it.
  {id: 'LAUNCH', beat: 'launch, patrol cars pile in', clip: 'N2', srcIn: 2.6, frames: 36},
  // 12.125 hard drift through the first corner. Cookie's chip pops ON the turn.
  {id: 'DRIFT', beat: 'Cookie: corner drift', clip: 'N3', srcIn: 1.5, frames: 36},
  // 13.625 insane speed, a hand's width off the wet asphalt, patrol car closing.
  {id: 'LOWTRACK', beat: 'low tracking shot', clip: 'N4', srcIn: 1.0, frames: 30},
  // 14.875 bumper to bumper; the near miss with the truck; sparks.
  {id: 'NEARMISS', beat: 'near miss, sparks', clip: 'N5', srcIn: 0.3, frames: 36},
  // 16.375 they blow past their turn; handbrake 180 (Gordon on the yank); reverse back.
  {id: 'OVERSHOOT', beat: 'Gordon: overshoot, handbrake 180', clip: 'N6', srcIn: 0.5, frames: 54},
  // 18.625 down the alley, the cops overshoot the turn; the car swings out at the far end (Daffy's chip).
  {id: 'ALLEY', beat: 'alley escape', clip: 'N7', srcIn: 1.0, frames: 36},
  // 20.125 the red light, masked, the patrol car alongside.
  {id: 'RED1', beat: 'red light, frozen', clip: 'V08', srcIn: 0.5, frames: 42,
    f16: {scale: 1.0, cx: 960, cy: 540}},
  // 21.875 the scramble, 2.4x, running straight into the hold (no jump).
  {id: 'RED2', beat: 'masks off, sunglasses on', clip: 'V08', srcIn: 2.25, frames: 30, rate: 2.4,
    f16: {scale: 1.0, cx: 960, cy: 540}},
  // 23.125 acting natural.
  {id: 'RED3', beat: 'act natural (the shareable frame)', clip: 'V08', srcIn: 5.25, frames: 16,
    f16: {scale: 1.0, to: 1.04, cx: 960, cy: 520},
    blur: [{keys: [[0, {x: 960, y: 655, w: 150, h: 45}], [17, {x: 960, y: 655, w: 150, h: 45}]], px: 6}]},
  // 23.792 the officer squints.
  {id: 'OFFICER', beat: 'officer squints', clip: 'V09', srcIn: 2.0, frames: 18,
    f16: {scale: 1.0, cx: 960, cy: 540}},
  // 24.542 he glides on.
  {id: 'GLIDE', beat: 'patrol car glides past', clip: 'V09', srcIn: 4.9, frames: 26,
    f16: {scale: 1.0, cx: 960, cy: 540},
    // Generated lettering on the rear door: tracked blur.
    blur: [{px: 16, keys: [[7, {x: 1880, y: 640, w: 80, h: 90}], [10, {x: 1790, y: 638, w: 135, h: 92}], [14, {x: 1755, y: 628, w: 150, h: 104}],
      [19, {x: 1640, y: 628, w: 190, h: 112}], [24, {x: 1540, y: 638, w: 190, h: 118}], [26, {x: 1510, y: 642, w: 195, h: 122}]]}]},
  // 25.625 the smirk.
  {id: 'SMIRK', beat: 'phone-lit smirk', clip: 'V12', srcIn: 2.75, frames: 11,
    f16: {scale: 1.0, cx: 960, cy: 540}},
  // 26.083 the garage: engine off, everyone exhales. Smash to the card on "That's".
  // (the passenger's face drifts after src 4.0: never used)
  {id: 'GARAGE', beat: 'Bugs: garage, exhale', clip: 'V13', srcIn: 2.35, frames: 33,
    f16: {scale: 1.0, cx: 960, cy: 540}},
];

/** Film in/out (seconds and frames) of every shot, by id. */
export const T: Record<string, {in: number; out: number; fin: number; fout: number}> = {};
{
  let fr = 0;
  for (const c of CUT) {
    T[c.id] = {in: fr / FPS, out: (fr + c.frames) / FPS, fin: fr, fout: fr + c.frames};
    fr += c.frames;
  }
  T.END = {in: fr / FPS, out: TOTAL, fin: fr, fout: TOTAL_FRAMES};
}

export type Shot = ShotSpec & {fin: number; fout: number};
export const SHOTS: Shot[] = CUT.map((c) => ({...c, fin: T[c.id].fin, fout: T[c.id].fout}));

/** One campaign grade: crisp blacks, a touch of contrast, grain and vignette. */
export const GRADE = {contrast: 1.05, saturate: 1.03, brightness: 1.0, vignette: 0.38, grain: 0.06};

// ------------------------------------------------------------------ voices

export type Line = {
  /** Key in getaway-lines.json (public/ga/voices/<key>.wav). */
  key: string;
  slug: string;
  name: string;
  /** Film frame the voice starts. The chip lands TAP_LEAD frames earlier. */
  at: number;
  /** Frame the chip and caption leave. */
  out: number;
};

export const TAP_LEAD = 2;
const fin = (id: string, plus = 0) => T[id].fin + plus;

// One navigator per hard turn: Elmo on the tap, Cookie on the corner drift,
// Gordon on the handbrake yank, Daffy as the car swings out of the alley, Bugs
// on arrival. Each chip leaves as the next one lands.
const AT = {
  elmo: fin('PHONE_UP', 13),
  cookie: fin('DRIFT', 10),
  gordon: fin('OVERSHOOT', 12),
  // "Act" (1.2 s in) lands on the same source frame of V08 as in the first cut (src 1.46)
  daffy: fin('RED1', -6),
  bugs: fin('GARAGE'),
};
export const LINES: Line[] = [
  {key: 'elmo_hello', slug: 'elmo', name: 'Elmo', at: AT.elmo, out: fin('CHAIN1')},
  {key: 'cookie_police', slug: 'cookie-monster', name: 'Cookie Monster', at: AT.cookie, out: AT.gordon - TAP_LEAD},
  {key: 'gordon_missed', slug: 'gordon-ramsay', name: 'Gordon Ramsay', at: AT.gordon, out: AT.daffy - TAP_LEAD},
  {key: 'daffy_police', slug: 'daffy-duck', name: 'Daffy Duck', at: AT.daffy, out: fin('OFFICER', 6)},
  {key: 'bugs_arrived', slug: 'bugs-bunny', name: 'Bugs Bunny', at: AT.bugs, out: fin('END')},
];

// ------------------------------------------------------------------ sound

export type Bed = {src: string; from: number; to: number; db: number; offset?: number; fadeIn?: number; fadeOut?: number};
/** A one-shot; `offset` is seconds into its file. */
export type Hit = {src: string; at: number; db: number; offset?: number};

export const MIX = {voiceDb: 0, tapDb: -12};

// Beds are staged at -20 LUFS (scripts/stage_getaway.py). Frames, not seconds.
// Preview sound: the first cut's SFX stand in for the chase SFX listed in
// film/runway4/plan.md (screech, handbrake, truck horn, scrape, splashes).
export const BEDS: Bed[] = [
  {src: 'sfx/drone.wav', from: 0, to: AT.elmo, db: -6, fadeIn: 6},
  {src: 'sfx/alarm_rain.wav', from: 0, to: T.PHONE_UP.fin, db: -6, fadeOut: 2},
  {src: 'sfx/rain_roof.wav', from: T.PHONE_UP.fin, to: T.TYRE.fin, db: -9},
  {src: 'sfx/road.wav', from: T.TYRE.fin, to: T.RED1.fin, db: -11, fadeOut: 12},
  {src: 'sfx/sirens.wav', from: T.TYRE.fin + 4, to: T.RED1.fin, db: -13, fadeIn: 8, fadeOut: 24},
  {src: 'sfx/rain_roof.wav', from: T.RED1.fin, to: T.GLIDE.fin, db: -10, offset: 2},
  {src: 'sfx/road.wav', from: T.GLIDE.fin, to: T.GARAGE.fin, db: -15, fadeIn: 8, offset: 1},
  {src: 'sfx/rain_roof.wav', from: T.GARAGE.fin, to: T.END.fin, db: -18, offset: 1},
];

export const HITS: Hit[] = [
  // three doors slam as they dive in
  {src: 'sfx/door_thunk.wav', at: T.SPRINT_B.fin + 7, db: -4},
  {src: 'sfx/door_thunk.wav', at: T.SPRINT_B.fin + 12, db: -6},
  {src: 'sfx/door_thunk.wav', at: T.SPRINT_B.fin + 17, db: -5},
  // the rev builds under the shrug's last frames; the screech lands on the spin
  {src: 'sfx/peel_out.wav', at: T.TYRE.fin - 4, db: 0, offset: 1.2},
  {src: 'sfx/whoosh.wav', at: T.DRIFT.fin - 3, db: -8},
  {src: 'sfx/whoosh.wav', at: T.LOWTRACK.fin - 2, db: -10},
  {src: 'sfx/whoosh.wav', at: T.NEARMISS.fin + 8, db: -6},
  // the handbrake 180
  {src: 'sfx/peel_out.wav', at: T.OVERSHOOT.fin + 10, db: -4, offset: 1.2},
  {src: 'sfx/whoosh.wav', at: T.ALLEY.fin - 2, db: -8},
  {src: 'sfx/pull_up.wav', at: T.GLIDE.fin - 6, db: -10},
  {src: 'sfx/garage_stop.wav', at: T.GARAGE.fin - 4, db: -8},
  // in the gap between "We've arrived." and "That's", on the visible exhale
  {src: 'sfx/exhale.wav', at: T.GARAGE.fin + 21, db: -14},
];

/** Film frames of the soft screen tap (only Elmo is tapped in; the rest arrive with the turns). */
export const TAPS: number[] = [AT.elmo - TAP_LEAD];

/** The one music hit, on the cut to the card. */
export const MUSIC_HIT = {src: 'sfx/hit.wav', at: T.END.fin, db: -12};

// ------------------------------------------------------------------ end card

export const END = {
  fin: T.END.fin,
  title: "Who's in your backseat?",
  url: 'backseatnav.com',
  tagline: 'Free. No account. One tap.',
  footer: 'Independent project. Not affiliated with Waze or Google.',
  faceStaggerFrames: 1,
};
