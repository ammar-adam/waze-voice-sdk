// THE GETAWAY: every tunable value of the film, 30.0 s at 24 fps (720 frames).
// Plan and QA: film/runway3/plan.md. Footage and sound are staged into
// public/ga/ by scripts/stage_getaway.py; the voice lines by
// scripts/build_getaway_voices.py. Every cut sits on a whole frame: shots are
// laid end to end by their length in frames.

export {BRAND, CAST, FONT, castOf} from './toughcrowd.config';

export const FPS = 24;
export const TOTAL_FRAMES = 720;
export const TOTAL = TOTAL_FRAMES / FPS;

/** 16:9: anamorphic letterbox bars over everything but the end card. */
export const BAR = 118;
/** 9:16: the footage window, a native 1080x1080 crop (no upscale), and its top. */
export const WIN9 = {top: 300, size: 1080};

// ------------------------------------------------------------------ picture

/** A source rectangle in 1920x1080 clip pixels. */
export type Rect = {x: number; y: number; w: number; h: number};

/** Garbled AI text to soften: keyframes of [frame into the shot, rect], interpolated. */
export type BlurTrack = {keys: [number, Rect][]; px?: number};

export type ShotSpec = {
  id: string;
  beat: string;
  /** File in public/ga/clips/ (without .mp4). */
  clip: string;
  /** Seconds into the source clip at the shot's first frame. */
  srcIn: number;
  /** Length in film frames. */
  frames: number;
  /** Picture speed (voices are never touched). */
  rate?: number;
  /** 16:9 framing: a crop at `scale` around (cx, cy); with `to`, a slow push. */
  f16?: {scale: number; cx: number; cy: number; to?: number};
  /** 9:16 framing: the 1080x1080 window's centre in clip pixels, optional zoom (>= 1). */
  f9: {x: number; y?: number; zoom?: number; zoomTo?: number; panTo?: number};
  blur?: BlurTrack[];
  /** Soften the out-of-focus background above this clip y (neon signs with glyph-like shapes). */
  band?: number;
  /** Per-clip match before the campaign grade. */
  match?: {brightness?: number; contrast?: number; saturate?: number};
};

type Special = {id: 'SPEEDO' | 'PHONE'; beat: string; frames: number};
type Piece = ShotSpec | Special;

// Punch-ins for the head-turn chain: each cut goes tighter (comic escalation).
const CUT: Piece[] = [
  // 0.00 cold open: the slow walk to the car under the red beacon.
  // 1x: Veo's walk is already unhurried; a slowed 24 fps clip would repeat every fifth frame.
  {id: 'WALK', beat: 'cold open', clip: 'V01', srcIn: 2.9, frames: 48,
    f16: {scale: 1.0, to: 1.06, cx: 1000, cy: 470}, f9: {x: 1180, zoom: 1.0, zoomTo: 1.05},
    blur: [{keys: [[0, {x: 60, y: 210, w: 230, h: 120}], [47, {x: 60, y: 210, w: 230, h: 120}]], px: 18}]},
  // 2.00 "I've got navigation": phone up, thumb to the screen.
  {id: 'PHONE_UP', beat: 'phone up + tap', clip: 'V02B', srcIn: 0.0, frames: 18,
    f16: {scale: 1.12, cx: 960, cy: 520}, f9: {x: 960}, band: 150},
  // 2.75 Elmo: the driver's eyes go wide; a snap focus pull (3x) to the passenger's flat look.
  {id: 'RACK_A', beat: 'Elmo: driver eyes', clip: 'V03', srcIn: 0.8, frames: 53, f9: {x: 1250}},
  {id: 'RACK_B', beat: 'Elmo: focus pull', clip: 'V03', srcIn: 3.0, frames: 18, rate: 3, f9: {x: 1250, panTo: 820}},
  {id: 'RACK_C', beat: 'Elmo: passenger', clip: 'V03', srcIn: 5.25, frames: 33, f9: {x: 820}},
  // 7.08 the head-turn chain, three cuts, each tighter.
  {id: 'CHAIN1', beat: 'driver turns to passenger', clip: 'V02A', srcIn: 1.55, frames: 15,
    f16: {scale: 1.0, cx: 960, cy: 540}, f9: {x: 980}, band: 150},
  {id: 'CHAIN2', beat: 'passenger turns to the back', clip: 'V02A', srcIn: 4.55, frames: 15,
    f16: {scale: 1.18, cx: 760, cy: 500}, f9: {x: 800, zoom: 1.08}, band: 150},
  {id: 'CHAIN3', beat: 'backseat shrug', clip: 'V02A', srcIn: 6.45, frames: 17,
    f16: {scale: 1.36, cx: 960, cy: 470}, f9: {x: 960, y: 480, zoom: 1.2}, band: 150},
  // 9.04 tyres spin, the car tears off.
  {id: 'TYRE', beat: 'tyres spin', clip: 'V05', srcIn: 1.15, frames: 15, rate: 1.3, f9: {x: 760}},
  // 9.67 Paddington: red and blue, glare, swipe, the hard stare.
  {id: 'BLUERED', beat: 'Paddington: glare, swipe, hard stare', clip: 'V06', srcIn: 1.0, frames: 98,
    f16: {scale: 1.0, to: 1.08, cx: 960, cy: 520}, f9: {x: 960}, band: 150},
  // 13.75 the red light, masked, the patrol car alongside.
  {id: 'RED1', beat: 'red light, frozen', clip: 'V08', srcIn: 0.0, frames: 54,
    f16: {scale: 1.0, cx: 960, cy: 540}, f9: {x: 960}},
  // 16.00 the scramble, 2.4x, running straight into the hold (no jump).
  {id: 'RED2', beat: 'masks off, sunglasses on', clip: 'V08', srcIn: 2.25, frames: 30, rate: 2.4,
    f16: {scale: 1.0, cx: 960, cy: 540}, f9: {x: 960}},
  // 17.17 acting natural.
  {id: 'RED3', beat: 'act natural (the shareable frame)', clip: 'V08', srcIn: 5.25, frames: 16,
    f16: {scale: 1.0, to: 1.04, cx: 960, cy: 520}, f9: {x: 960},
    blur: [{keys: [[0, {x: 960, y: 655, w: 150, h: 45}], [17, {x: 960, y: 655, w: 150, h: 45}]], px: 6}]},
  // 17.92 the officer squints.
  {id: 'OFFICER', beat: 'officer squints', clip: 'V09', srcIn: 2.0, frames: 18,
    f16: {scale: 1.0, cx: 960, cy: 540}, f9: {x: 1150}},
  // 18.67 Vader: the patrol car glides past.
  {id: 'GLIDE', beat: 'patrol car glides past', clip: 'V09', srcIn: 4.9, frames: 26,
    f16: {scale: 1.0, cx: 960, cy: 540}, f9: {x: 1100, panTo: 1000},
    // Generated lettering on the rear door: tracked blur.
    blur: [{px: 16, keys: [[7, {x: 1880, y: 640, w: 80, h: 90}], [10, {x: 1790, y: 638, w: 135, h: 92}], [14, {x: 1755, y: 628, w: 150, h: 104}],
      [19, {x: 1640, y: 628, w: 190, h: 112}], [24, {x: 1540, y: 638, w: 190, h: 118}], [26, {x: 1510, y: 642, w: 195, h: 122}]]}]},
  // 19.75 the speedometer eases down (built here, a digital cluster).
  {id: 'SPEEDO', beat: 'speedometer eases down', frames: 74},
  // 22.83 the synchronized nod on "Slow down."
  // down on "Slow" (frame 558), bottom on "down." (575), all three back up by the cut
  {id: 'NOD', beat: 'synchronized solemn nod', clip: 'V11', srcIn: 2.1, frames: 48, rate: 1.5,
    f16: {scale: 1.0, cx: 960, cy: 520}, f9: {x: 960}},
  // 24.83 the site on his phone: scroll past Vader, tap Install under Bugs Bunny.
  {id: 'PHONE', beat: 'phone: install Bugs Bunny', frames: 19},
  // 25.63 the smirk.
  {id: 'SMIRK', beat: 'phone-lit smirk', clip: 'V12', srcIn: 2.75, frames: 11,
    f16: {scale: 1.0, cx: 960, cy: 540}, f9: {x: 820}},
  // 26.08 the garage: engine off, everyone exhales. Cut to the card on "That's".
  // (the passenger's face drifts after src 4.0: never used)
  {id: 'GARAGE', beat: 'garage, exhale', clip: 'V13', srcIn: 2.35, frames: 33,
    f16: {scale: 1.0, cx: 960, cy: 540}, f9: {x: 960}},
];

/** Film in/out (seconds) of every piece, by id. */
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
export const SHOTS: Shot[] = CUT.filter((c): c is ShotSpec => 'clip' in c).map((c) => ({
  ...c,
  fin: T[c.id].fin,
  fout: T[c.id].fout,
}));

/** One campaign grade: crisp blacks, a touch of contrast, grain and vignette. */
export const GRADE = {contrast: 1.05, saturate: 1.03, brightness: 1.0, vignette: 0.38, grain: 0.06};

// ------------------------------------------------------------------ inserts

/** The digital cluster: the needle eases from `from` to `to` (mph). */
export const SPEEDO = {from: 68, to: 45, easeStart: 0, easeEnd: 2.7};

/** The site on his phone. Times are seconds into the insert. */
export const PHONE = {
  headline: 'Pick your navigator',
  startSlug: 'darth-vader',
  targetSlug: 'bugs-bunny',
  hoverUntil: 0.16,
  scrollEnd: 0.5,
  tapAt: 0.56,
};

// ------------------------------------------------------------------ voices

export type Line = {
  /** Key in getaway-lines.json (public/ga/voices/<key>.wav). */
  key: string;
  slug: string;
  name: string;
  /** Film frame the voice starts. The tap and the chip land TAP_LEAD frames earlier. */
  at: number;
  /** Frame the chip and caption leave. */
  out: number;
};

export const TAP_LEAD = 2;
const fin = (id: string, plus = 0) => T[id].fin + plus;

export const LINES: Line[] = [
  // The thumb meets the screen at src 0.45 of V02B (film frame 59).
  {key: 'elmo_hello', slug: 'elmo', name: 'Elmo', at: fin('PHONE_UP', 13), out: fin('CHAIN1')},
  {key: 'paddington_police', slug: 'paddington', name: 'Paddington', at: fin('BLUERED', 6), out: fin('RED1')},
  {key: 'daffy_police', slug: 'daffy-duck', name: 'Daffy Duck', at: fin('RED1', 6), out: fin('OFFICER', 6)},
  {key: 'vader_police', slug: 'darth-vader', name: 'Darth Vader', at: fin('GLIDE'), out: fin('PHONE')},
  {key: 'bugs_arrived', slug: 'bugs-bunny', name: 'Bugs Bunny', at: fin('GARAGE'), out: fin('END')},
];

// ------------------------------------------------------------------ sound

export type Bed = {src: string; from: number; to: number; db: number; offset?: number; fadeIn?: number; fadeOut?: number};
/** A one-shot; `offset` is seconds into its file. */
export type Hit = {src: string; at: number; db: number; offset?: number};

export const MIX = {voiceDb: 0, tapDb: -12};

// Beds are staged at -20 LUFS (scripts/stage_getaway.py). Frames, not seconds.
export const BEDS: Bed[] = [
  {src: 'sfx/drone.wav', from: 0, to: LINES[0].at, db: -6, fadeIn: 6},
  {src: 'sfx/alarm_rain.wav', from: 0, to: T.PHONE_UP.fin, db: -6, fadeOut: 2},
  {src: 'sfx/rain_roof.wav', from: T.PHONE_UP.fin, to: T.TYRE.fin, db: -9},
  {src: 'sfx/road.wav', from: T.TYRE.fin, to: T.RED1.fin, db: -9},
  {src: 'sfx/sirens.wav', from: T.TYRE.fin + 4, to: T.RED1.fin, db: -10, fadeIn: 12, fadeOut: 2},
  {src: 'sfx/rain_roof.wav', from: T.RED1.fin, to: T.GLIDE.fin, db: -10, offset: 2},
  {src: 'sfx/road.wav', from: T.GLIDE.fin, to: T.GARAGE.fin, db: -15, fadeIn: 8, offset: 1},
  {src: 'sfx/rain_roof.wav', from: T.GARAGE.fin, to: T.END.fin, db: -18, offset: 1},
];

export const HITS: Hit[] = [
  // the rev builds under the shrug's last frames; the screech lands on the spin
  {src: 'sfx/peel_out.wav', at: T.TYRE.fin - 4, db: 0, offset: 1.2},
  {src: 'sfx/pull_up.wav', at: T.GLIDE.fin - 6, db: -10},
  {src: 'sfx/garage_stop.wav', at: T.GARAGE.fin - 4, db: -8},
  // in the gap between "We've arrived." and "That's", on the visible exhale
  {src: 'sfx/exhale.wav', at: T.GARAGE.fin + 21, db: -14},
];

/** Film frames of the soft screen taps (every voice switch, plus the install tap). */
export const TAPS: number[] = [
  ...LINES.filter((l) => l.key !== 'bugs_arrived').map((l) => l.at - TAP_LEAD),
  T.PHONE.fin + Math.round(PHONE.tapAt * FPS),
];

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
