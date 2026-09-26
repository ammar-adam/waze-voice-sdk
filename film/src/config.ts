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
  /** Key in ad-media.json: a clip, or a still for an animated push-in. */
  src: string;
  /** Where in the source clip this shot starts. */
  in: number;
  /** How long the shot runs in the edit. */
  dur: number;
  /** Per-clip exposure match, applied before the campaign grade. */
  match?: {brightness?: number; contrast?: number; saturate?: number};
};

export type Interior = Shot & {
  /** First frame of the reaction, counted in the source clip's own frames. */
  reactionFrame?: number;
  /** For a still: seconds into the shot where the reaction beat lands. */
  reactionAt?: number;
  /** For a still: push-in scale from 1 to this, and where it pushes toward. */
  pushTo?: number;
  pushOrigin?: string;
};

export type Vignette = {
  id: string;
  exterior: Shot;
  interior: Interior;
  voice: string; // key in ad-media.json
  navigator: string; // lower-third name
  ambience: {src: string; db: number};
  /** Plays at the reaction (the grandma's floor-it). */
  hit?: {src: string; db: number; offset: number};
};

export const VIGNETTES: Vignette[] = [
  {
    id: 'ceo',
    exterior: {src: '1A', in: 1.0, dur: 1.4, match: {saturate: 0.82, brightness: 1.0}},
    interior: {src: '1B', in: 0, dur: 4.6, reactionFrame: 63},
    voice: 'voice_pooh',
    navigator: 'Winnie the Pooh',
    ambience: {src: 'sfx_rain', db: -15},
  },
  {
    id: 'teen',
    // Long exterior on purpose: the teen's reaction starts 0.5s into 2B, so
    // Batman plays over the wide shot of the car creeping down the street.
    exterior: {src: '2A', in: 0.4, dur: 4.0},
    interior: {src: '2B', in: 0, dur: 2.0, reactionFrame: 12},
    voice: 'voice_batman',
    navigator: 'Batman',
    ambience: {src: 'sfx_dusk', db: -16},
  },
  {
    id: 'trucker',
    exterior: {src: '3A', in: 2.4, dur: 1.4, match: {brightness: 0.92, contrast: 1.04}},
    interior: {src: '3B', in: 0, dur: 4.4, reactionFrame: 68, match: {brightness: 0.95}},
    voice: 'voice_elmo',
    navigator: 'Elmo',
    ambience: {src: 'sfx_truck', db: -16},
  },
  {
    id: 'grandma',
    exterior: {src: '4A', in: 1.5, dur: 1.4},
    // No 4B clip was generated: the still gets a slow push-in, and the
    // floor-it is carried by sound, the surge landing as we cut to the card.
    interior: {
      src: '4B',
      in: 0,
      dur: 4.6,
      reactionAt: 4.0,
      pushTo: 1.07,
      pushOrigin: '70% 38%',
    },
    voice: 'voice_cookie',
    navigator: 'Cookie Monster',
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

export const LOWER_THIRD = {
  label: 'Navigator:',
  fontSize: 34,
  left: 96,
  bottom: 84,
  fadeFrames: 8,
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
