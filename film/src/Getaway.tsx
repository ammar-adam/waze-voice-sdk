import React from 'react';
import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  Sequence,
  cancelRender,
  continueRender,
  delayRender,
  interpolate,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import linesData from './getaway-lines.json';
import mediaData from './getaway-media.json';
import {
  BRAND,
  CAST,
  END,
  FONT,
  FPS,
  GRADE,
  LINES,
  PLACEHOLDER_PUSH,
  SHOTS,
  TAP_LEAD,
  TOTAL_FRAMES,
  castOf,
  type Line,
  type Rect,
  type Shot,
} from './getaway.config';

// THE GETAWAY, action-chase revision (film/runway4/plan.md). 1920x1080 full
// frame, no letterbox. Picture only: the sound is built sample-accurately
// outside Remotion by scripts/mix_getaway.py from the same config.

const fontsReady = delayRender('getaway fonts', {timeoutInMilliseconds: 60000, retries: 2});
Promise.all(
  [
    ['Bagel Fat One', 'fonts/BagelFatOne.ttf', '400'],
    ['Bricolage Grotesque', 'fonts/Bricolage.ttf', '200 800'],
    ['JetBrains Mono', 'fonts/JetBrainsMono.ttf', '100 800'],
  ].map(([family, file, weight]) =>
    new FontFace(family, `url('${staticFile(file)}')`, {weight}).load().then((face) => document.fonts.add(face)),
  ),
)
  .then(() => continueRender(fontsReady))
  .catch((error) => cancelRender(error));

type Word = {w: string; start: number; end: number};
type LineData = {file: string; text: string; seconds: number; words: Word[]};
const LINE_DATA = linesData as Record<string, LineData>;

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const INK = BRAND.ink;
/** Which clips are held stills standing in for a NEW shot (written by scripts/stage_getaway.py). */
const MEDIA = mediaData as Record<string, 'take' | 'placeholder'>;
const smooth = (k: number) => k * k * (3 - 2 * k);

// ================================================================= footage

/** The clip drawn so that `rect` (clip pixels) fills boxW x boxH. */
const View: React.FC<{shot: Shot; rect: Rect; boxW: number; boxH: number}> = ({shot, rect, boxW, boxH}) => {
  const frame = useCurrentFrame();
  const s = boxW / rect.w;
  const m = shot.match ?? {};
  const filter = [
    `brightness(${(m.brightness ?? 1) * GRADE.brightness})`,
    `contrast(${(m.contrast ?? 1) * GRADE.contrast})`,
    `saturate(${(m.saturate ?? 1) * GRADE.saturate})`,
  ].join(' ');
  const src = staticFile(`ga/clips/${shot.clip}.mp4`);
  const trim = Math.round(shot.srcIn * FPS);
  const rate = shot.rate ?? 1;
  const copy = (style: React.CSSProperties, key: string) => (
    <OffthreadVideo key={key} src={src} trimBefore={trim} playbackRate={rate} muted style={{position: 'absolute', inset: 0, width: '100%', height: '100%', ...style}} />
  );
  return (
    <div style={{position: 'absolute', inset: 0, width: boxW, height: boxH, overflow: 'hidden', background: '#000'}}>
      <div style={{position: 'absolute', left: -rect.x * s, top: -rect.y * s, width: 1920 * s, height: 1080 * s}}>
        {copy({filter}, 'base')}
        {shot.band
          ? copy(
              {
                filter: `${filter} blur(${14 * s}px)`,
                WebkitMaskImage: `linear-gradient(to bottom, #000 0, #000 ${shot.band * 0.7 * s}px, transparent ${shot.band * s}px)`,
                maskImage: `linear-gradient(to bottom, #000 0, #000 ${shot.band * 0.7 * s}px, transparent ${shot.band * s}px)`,
              },
              'band',
            )
          : null}
        {(shot.blur ?? []).map((track, i) => {
          const at = track.keys.map(([k]) => k);
          const lerp = (pick: (r: Rect) => number) => interpolate(frame, at, track.keys.map(([, r]) => pick(r)), clamp);
          const b = {x: lerp((r) => r.x), y: lerp((r) => r.y), w: lerp((r) => r.w), h: lerp((r) => r.h)};
          const mask = `radial-gradient(ellipse ${b.w * 0.72 * s}px ${b.h * 0.8 * s}px at ${(b.x + b.w / 2) * s}px ${(b.y + b.h / 2) * s}px, #000 70%, transparent 100%)`;
          return copy({filter: `${filter} blur(${(track.px ?? 14) * s}px)`, WebkitMaskImage: mask, maskImage: mask}, `blur${i}`);
        })}
      </div>
    </div>
  );
};

const progress = (shot: Shot, frame: number) =>
  smooth(interpolate(frame, [0, Math.max(1, shot.fout - shot.fin - 1)], [0, 1], clamp));

const rect16 = (shot: Shot, frame: number): Rect => {
  const p = shot.f16 ?? {scale: 1, cx: 960, cy: 540};
  // a held still (a NEW shot not generated yet) gets a subtle push so the preview moves
  const to = MEDIA[shot.clip] === 'placeholder' ? p.scale + PLACEHOLDER_PUSH : p.to;
  const scale = to ? p.scale + (to - p.scale) * progress(shot, frame) : p.scale;
  const w = 1920 / scale;
  const h = 1080 / scale;
  return {x: Math.min(Math.max(p.cx - w / 2, 0), 1920 - w), y: Math.min(Math.max(p.cy - h / 2, 0), 1080 - h), w, h};
};

const Grain: React.FC<{w: number; h: number}> = ({w, h}) => {
  const frame = useCurrentFrame();
  const gx = (frame * 197) % 512;
  const gy = (frame * 331) % 512;
  return (
    <>
      <div style={{position: 'absolute', left: 0, top: 0, width: w, height: h, backgroundImage: `url('${staticFile('ga/grain.png')}')`, backgroundPosition: `${gx}px ${gy}px`, opacity: GRADE.grain, mixBlendMode: 'overlay'}} />
      <div style={{position: 'absolute', left: 0, top: 0, width: w, height: h, background: `radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,${GRADE.vignette}) 100%)`}} />
    </>
  );
};

const ShotView: React.FC<{shot: Shot}> = ({shot}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <View shot={shot} rect={rect16(shot, frame)} boxW={1920} boxH={1080} />
      <Grain w={1920} h={1080} />
      {MEDIA[shot.clip] === 'placeholder' ? (
        <div style={{position: 'absolute', left: 28, top: 22, fontFamily: FONT.mono, fontWeight: 500, fontSize: 18, letterSpacing: 2, color: 'rgba(255,255,255,0.55)'}}>
          {shot.clip} STILL
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

// ================================================================= stickers and captions

const FaceBadge: React.FC<{slug: string; size: number; ring?: number}> = ({slug, size, ring = 5}) => (
  <div style={{width: size, height: size, flex: 'none', borderRadius: '50%', background: castOf(slug).bg, border: `${ring}px solid ${INK}`, display: 'grid', placeItems: 'center', overflow: 'hidden'}}>
    <Img src={staticFile(`ga/faces/${slug}.svg`)} style={{width: size * 0.92, height: size * 0.92, marginTop: size * 0.06}} />
  </div>
);

/** Slap in over 5 frames (0 -> 1.12 -> 1), pop off over 4. `frame` is frames since the chip landed. */
const slap = (frame: number, dur: number) => {
  const inS = interpolate(frame, [0, 3, 5], [0, 1.12, 1], clamp);
  const outS = interpolate(frame, [dur - 4, dur - 2, dur], [1, 1.08, 0], clamp);
  return {scale: frame < dur - 4 ? inS : outS, rot: interpolate(frame, [0, 5], [-9, -2], clamp)};
};

const Chip: React.FC<{line: Line; frame: number; dur: number}> = ({line, frame, dur}) => {
  const visible = frame >= 0 && frame < dur;
  const {scale, rot} = slap(frame, dur);
  const face = 92;
  return (
    <div style={{display: 'inline-flex', alignItems: 'center', gap: 14, padding: '7px 26px 7px 7px', background: BRAND.sun, border: `5px solid ${INK}`, borderRadius: 999, boxShadow: `6px 6px 0 ${INK}`, transform: `scale(${visible ? scale : 0}) rotate(${rot}deg)`, transformOrigin: 'left center', visibility: visible ? 'visible' : 'hidden', whiteSpace: 'nowrap', flex: 'none'}}>
      <FaceBadge slug={line.slug} size={face} ring={4} />
      <span style={{fontFamily: FONT.display, fontSize: 44, color: INK, lineHeight: 1, paddingBottom: 4}}>{line.name}</span>
    </div>
  );
};

/** The preset text exactly, in clean bold white with a soft dark outline and
 * shadow (no box): the whole line readable at once, each word inking in as it is spoken. */
const Caption: React.FC<{line: Line; t: number; outT: number; maxWidth: number}> = ({line, t, outT, maxWidth}) => {
  const words = LINE_DATA[line.key].words;
  const visible = t >= 0 && t < outT;
  const pop = interpolate(t, [0, 3 / FPS], [0.94, 1], clamp);
  const off = interpolate(t, [outT - 3 / FPS, outT], [1, 0], clamp);
  return (
    <div
      style={{
        maxWidth,
        opacity: visible ? off : 0,
        transform: `scale(${pop})`,
        fontFamily: FONT.body,
        fontWeight: 800,
        fontSize: 58,
        lineHeight: 1.1,
        color: BRAND.white,
        textAlign: 'left',
        letterSpacing: -0.5,
        WebkitTextStroke: '7px rgba(8,9,20,0.5)',
        paintOrder: 'stroke fill',
        textShadow: '0 3px 6px rgba(0,0,0,0.65), 0 0 26px rgba(0,0,0,0.55)',
      }}
    >
      {words.map((w, i) => {
        const shown = interpolate(t, [w.start, w.start + 2 / FPS], [0, 1], clamp);
        return (
          <span key={i} style={{opacity: 0.45 + 0.55 * shown, display: 'inline-block', transform: `translateY(${-3 * shown}px)`}}>
            {w.w}
            {i < words.length - 1 ? ' ' : ''}
          </span>
        );
      })}
    </div>
  );
};

const VoiceUI: React.FC<{line: Line; start: number}> = ({line, start}) => {
  const frame = useCurrentFrame();
  const abs = start + frame;
  const chipFrame = abs - (line.at - TAP_LEAD);
  const chipDur = line.out - (line.at - TAP_LEAD);
  const t = (abs - line.at) / FPS;
  const outT = (line.out - line.at) / FPS;
  // full frame: chip and caption sit low, inside the title-safe area
  return (
    <div style={{position: 'absolute', left: 96, right: 96, bottom: 64, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 22}}>
      <Chip line={line} frame={chipFrame} dur={chipDur} />
      <Caption line={line} t={t} outT={outT} maxWidth={1240} />
    </div>
  );
};

const Voice: React.FC<{line: Line}> = ({line}) => {
  const start = line.at - TAP_LEAD;
  return (
    <Sequence from={start} durationInFrames={line.out - start} name={`voice ui ${line.key}`}>
      <VoiceUI line={line} start={start} />
    </Sequence>
  );
};

// ================================================================= end card

const EndCard: React.FC = () => {
  const frame = useCurrentFrame();
  const title = interpolate(frame, [0, 2, 4], [0.9, 1.04, 1], clamp);
  const urlS = interpolate(frame, [0, 2, 4], [0.94, 1.05, 1], clamp);
  const cols = 6;
  const face = 140;
  const bugsIdx = CAST.findIndex((c) => c.slug === 'bugs-bunny');
  // The site's look: a faint street map drifting under the sun yellow, and a
  // dashed route marching to a pin behind the cast.
  const drift = frame * 1.2;
  const march = -frame * 2;
  return (
    <AbsoluteFill style={{background: BRAND.sun, alignItems: 'center'}}>
      <AbsoluteFill
        style={{
          backgroundImage: `url(${staticFile('ga/map-tile.svg')})`,
          backgroundSize: '320px 320px',
          backgroundPosition: `${-drift}px ${drift}px`,
        }}
      />
      <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0}}>
        <path
          d="M-40 980 C 260 980 300 780 560 790 S 900 900 1040 700 S 1260 400 1520 430 S 1820 260 1860 150"
          fill="none" stroke={INK} strokeWidth={7} strokeLinecap="round" strokeDasharray="3 20"
          strokeDashoffset={march} opacity={0.2}
        />
        <path
          d="M1860 70 c -30 0 -50 22 -50 46 c 0 36 50 74 50 74 s 50 -38 50 -74 c 0 -24 -20 -46 -50 -46 z m 0 30 a 16 16 0 1 1 0 32 a 16 16 0 1 1 0 -32 z"
          fill="#ff5a1f" stroke={INK} strokeWidth={4} opacity={0.9}
          transform={`translate(0 ${-Math.abs(Math.sin(frame / 8)) * 6})`}
        />
      </svg>
      <div style={{position: 'absolute', top: 52, left: 0, width: 1920, textAlign: 'center', transform: `scale(${title}) rotate(-1.5deg)`, fontFamily: FONT.display, fontSize: 100, lineHeight: 1.02, color: INK, textShadow: '6px 6px 0 rgba(21,23,43,0.18)'}}>
        {END.title}
      </div>
      <div style={{position: 'absolute', top: 210, left: 0, width: 1920, display: 'flex', justifyContent: 'center'}}>
        <div style={{display: 'grid', gridTemplateColumns: `repeat(${cols}, ${face + 64}px)`, rowGap: 30, justifyItems: 'center'}}>
          {CAST.map((c, i) => {
            // Bugs (who just spoke) pops first; the rest follow, one frame apart.
            const order = i === bugsIdx ? 0 : i + 1;
            const st = order * END.faceStaggerFrames;
            const s = interpolate(frame, [st, st + 2, st + 4], [0.5, 1.12, 1], clamp);
            const o = interpolate(frame, [st, st + 1], [0, 1], clamp);
            const wig = i === bugsIdx ? interpolate(frame, [4, 6, 8, 10], [0, -9, 7, 0], clamp) : 0;
            return (
              <div key={c.slug} style={{display: 'flex', flexDirection: 'column', alignItems: 'center', opacity: o, transform: `scale(${s}) rotate(${(i % 2 ? 2 : -2) + wig}deg)`}}>
                <div style={{boxShadow: `6px 6px 0 ${INK}`, borderRadius: '50%'}}>
                  <FaceBadge slug={c.slug} size={face} ring={5} />
                </div>
                <span style={{marginTop: -16, padding: '3px 12px 5px', background: BRAND.white, border: `3px solid ${INK}`, borderRadius: 999, boxShadow: `3px 3px 0 ${INK}`, fontFamily: FONT.display, fontSize: 21, color: INK, whiteSpace: 'nowrap', position: 'relative'}}>
                  {c.name}
                </span>
              </div>
            );
          })}
        </div>
      </div>
      <div style={{position: 'absolute', top: 700, left: 0, width: 1920, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20}}>
        <div style={{transform: `scale(${urlS}) rotate(-1deg)`, background: INK, color: BRAND.sun, borderRadius: 999, padding: '12px 64px 20px', fontFamily: FONT.display, fontSize: 100, lineHeight: 1, boxShadow: '10px 10px 0 rgba(21,23,43,0.3)'}}>
          {END.url}
        </div>
        <div style={{fontFamily: FONT.body, fontWeight: 700, fontSize: 42, color: INK}}>{END.tagline}</div>
      </div>
      <div style={{position: 'absolute', bottom: 30, left: 0, width: 1920, textAlign: 'center', fontFamily: FONT.body, fontWeight: 500, fontSize: 24, color: INK, opacity: 0.85}}>
        {END.footer}
      </div>
    </AbsoluteFill>
  );
};

// ================================================================= the film

export const Getaway: React.FC = () => (
  <AbsoluteFill style={{background: '#000'}}>
    {SHOTS.map((shot) => (
      <Sequence key={shot.id} from={shot.fin} durationInFrames={shot.fout - shot.fin} name={shot.id}>
        <ShotView shot={shot} />
      </Sequence>
    ))}
    {LINES.map((l) => (
      <Voice key={l.key} line={l} />
    ))}
    <Sequence from={END.fin} durationInFrames={TOTAL_FRAMES - END.fin} name="end card">
      <EndCard />
    </Sequence>
  </AbsoluteFill>
);

export const GETAWAY_FRAMES = TOTAL_FRAMES;
