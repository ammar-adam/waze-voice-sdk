// Every tunable value in the 30s ad lives here. Times are in seconds unless a
// name says frames. Change a number, scrub in Remotion Studio, render.
//
// How a vignette is timed: the reaction frame in the interior clip is fixed
// (measured by stepping through the footage). The voice is placed so it ENDS
// `silence` seconds before that frame. If the voice is longer than the time
// before the reaction, it starts over the exterior and carries across the cut
// (a sound bridge); nothing is ever cut, sped up or pitch-shifted.

export const FPS = 24;
export const WIDTH = 1920;
export const HEIGHT = 1080;
export const TOTAL_SECONDS = 30;

/** The half second the joke lives in: voice ends, nothing, then the reaction. */
export const SILENCE = 0.65;

export type Shot = {
  /** Key in ad-media.json. */
  src: string;
  /** Where in the source clip this shot starts. */
  in: number;
  /** How long the shot runs in the edit. */
  dur: number;
  /** Per-clip exposure match, applied before the campaign grade. */
  match?: {brightness?: number; contrast?: number; saturate?: number};
};

export type Exterior = Shot & {
  /** For a vignette with no interior: seconds into this shot where the
   * reaction beat lands (the grandma's rev), and the cut happens there. */
  reactionAt?: number;
};

export type Interior = Shot & {
  /** First frame of the reaction, counted in the source clip's own frames. */
  reactionFrame: number;
};

export type Vignette = {
  id: string;
  exterior: Exterior;
  /** Omit to play the whole vignette on the exterior. */
  interior?: Interior;
  voice: string; // key in ad-media.json
  navigator: {name: string; slug: string}; // slug = site/faces/<slug>.svg
  ambience: {src: string; db: number};
  /** A sound that lands on the reaction beat; `offset` is where its hit sits in the file. */
  hit?: {src: string; db: number; offset: number};
};

export const VIGNETTES: Vignette[] = [
  {
    id: 'ceo',
    // The voice starts over the car and carries across the cut: her reaction
    // is at 2.62s into 1B, too soon to fit the line inside the interior.
    exterior: {src: '1A', in: 0.8, dur: 1.5, match: {saturate: 0.82, brightness: 1.06}},
    interior: {src: '1B', in: 0, dur: 4.4, reactionFrame: 63, match: {brightness: 1.18, contrast: 0.98}},
    voice: 'voice_pooh',
    navigator: {name: 'Winnie the Pooh', slug: 'pooh'},
    ambience: {src: 'sfx_rain', db: -15},
  },
  {
    id: 'learner',
    // The learner sets his jaw 0.5s into 2B, so Ramsay plays over the wide
    // shot of the L-plate car creeping down the street.
    exterior: {src: '2A', in: 0.3, dur: 4.3},
    interior: {src: '2B', in: 0, dur: 1.8, reactionFrame: 12},
    voice: 'voice_ramsay',
    navigator: {name: 'Gordon Ramsay', slug: 'gordon-ramsay'},
    ambience: {src: 'sfx_dusk', db: -16},
  },
  {
    id: 'trucker',
    // "La la la la" and he taps along.
    exterior: {src: '3A', in: 1.4, dur: 3.2, match: {brightness: 0.92, contrast: 1.04}},
    interior: {src: '3B', in: 0, dur: 4.3, reactionFrame: 68, match: {brightness: 0.95}},
    voice: 'voice_elmo',
    navigator: {name: 'Elmo', slug: 'elmo'},
    ambience: {src: 'sfx_truck', db: -16},
  },
  {
    id: 'grandma',
    // No interior was generated, and a zoomed still looked fake. The whole
    // vignette plays on the tiny car creeping along; after the silence the
    // engine revs and we smash-cut to the end card on it. The cut is the floor-it.
    exterior: {src: '4A', in: 0, dur: 5.0, reactionAt: 4.92},
    voice: 'voice_vader',
    navigator: {name: 'Darth Vader', slug: 'darth-vader'},
    ambience: {src: 'sfx_dusk', db: -18},
    hit: {src: 'sfx_surge', db: -1, offset: 0.1},
  },
];

export const MIX = {
  voiceDb: 0,
  /** Music bed, relative to the -16 LUFS the sources are normalised to. */
  musicDb: -9,
  /** Music fades out this long before each voice, and back in after the reaction. */
  duckOut: 0.25,
  duckIn: 0.5,
  /** Turn signal alone over the end card. */
  signalDb: -18,
  /** The surge runs on into the end card, then gets out of the tick's way. */
  hitTailFade: 0.35,
  /** Final master, applied after render by scripts/master_ad.py. */
  masterLufs: -14,
};

/** One campaign grade over every clip: deep blacks, warm highlights. */
export const GRADE = {
  contrast: 1.1,
  saturate: 0.92,
  brightness: 0.98,
  warmth: {color: '#ffae5c', opacity: 0.1}, // soft-light wash
  vignette: 0.28,
};

/** The navigator chip: the site's sticker style, face and name, bottom left. */
export const CHIP = {
  label: 'NAVIGATOR',
  left: 64,
  bottom: 64,
  faceSize: 92,
  nameSize: 44,
};

// Colours and type are the site's (site/style.css).
export const BRAND = {
  sun: '#ffd23f',
  ink: '#15172b',
  white: '#ffffff',
};

export const END_CARD = {
  title: "Who's in your backseat?",
  url: 'backseatnav.com',
  footer: 'Works with Waze. Independent project, not affiliated with Waze or Google.',
  titleAt: 0,
  badgesAt: 0.8,
  badgeStaggerFrames: 2,
  urlAt: 1.8,
};
