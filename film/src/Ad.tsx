import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  cancelRender,
  continueRender,
  delayRender,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import media from './ad-media.json';
import cuts from './cuts.json';
import {
  BRAND,
  END_CARD,
  FPS,
  GRADE,
  CHIP,
  MIX,
  SILENCE,
  TOTAL_SECONDS,
  VIGNETTES,
  type Shot,
} from './config';

const fontsReady = delayRender('ad fonts', {timeoutInMilliseconds: 60000, retries: 2});
Promise.all(
  [
    ['Bagel Fat One', 'fonts/BagelFatOne.ttf', '400'],
    ['Bricolage Grotesque', 'fonts/Bricolage.ttf', '200 800'],
    ['JetBrains Mono', 'fonts/JetBrainsMono.ttf', '100 800'],
  ].map(([family, file, weight]) =>
    new FontFace(family, `url('${staticFile(file)}')`, {weight}).load().then((f) => document.fonts.add(f)),
  ),
)
  .then(() => continueRender(fontsReady))
  .catch((error) => cancelRender(error));

type Media = Record<string, {file: string; seconds: number}>;
const MEDIA = media as Media;
const f = (seconds: number) => Math.round(seconds * FPS);
const gain = (db: number) => Math.pow(10, db / 20);

// ---------------------------------------------------------------- timeline

export type Placed = {
  id: string;
  extStart: number;
  /** Equal to `end` when the vignette has no interior. */
  intStart: number;
  end: number;
  voiceStart: number;
  voiceEnd: number;
  reaction: number;
};

export const buildTimeline = () => {
  let t = 0;
  const placed: Placed[] = VIGNETTES.map((v) => {
    const extStart = t;
    let intStart: number;
    let reaction: number;
    let end: number;
    if (v.interior) {
      intStart = t + v.exterior.dur;
      reaction = intStart + v.interior.reactionFrame / FPS - v.interior.in;
      end = intStart + v.interior.dur;
    } else {
      reaction = t + (v.exterior.reactionAt ?? v.exterior.dur);
      end = reaction;
      intStart = end;
    }
    const voiceEnd = reaction - SILENCE;
    const voiceStart = voiceEnd - MEDIA[v.voice].seconds;
    if (voiceStart < extStart + 0.2) {
      throw new Error(`${v.id}: voice would start before its exterior; lengthen the exterior`);
    }
    t = end;
    return {id: v.id, extStart, intStart, end, voiceStart, voiceEnd, reaction};
  });
  const endStart = t;
  if (TOTAL_SECONDS - endStart < 3.5) {
    throw new Error(`end card would only run ${(TOTAL_SECONDS - endStart).toFixed(2)}s`);
  }
  return {placed, endStart, endDur: TOTAL_SECONDS - endStart};
};

// ---------------------------------------------------------------- picture

const filterFor = (match?: Shot['match']) =>
  [
    `brightness(${(match?.brightness ?? 1) * GRADE.brightness})`,
    `contrast(${(match?.contrast ?? 1) * GRADE.contrast})`,
    `saturate(${(match?.saturate ?? 1) * GRADE.saturate})`,
  ].join(' ');

const Grade: React.FC = () => (
  <>
    <AbsoluteFill style={{background: GRADE.warmth.color, opacity: GRADE.warmth.opacity, mixBlendMode: 'soft-light'}} />
    <AbsoluteFill
      style={{background: `radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,${GRADE.vignette}) 100%)`}}
    />
  </>
);

const Clip: React.FC<{shot: Shot}> = ({shot}) => (
  <AbsoluteFill style={{background: '#000'}}>
    <OffthreadVideo
      src={staticFile(MEDIA[shot.src].file)}
      trimBefore={f(shot.in)}
      muted
      style={{width: '100%', height: '100%', objectFit: 'cover', filter: filterFor(shot.match)}}
    />
    <Grade />
  </AbsoluteFill>
);

const CAST_BG: Record<string, string> = Object.fromEntries(cuts.cast.map((c) => [c.slug, c.bg]));

/** Who's talking: the site's sticker, popping in as the voice starts. */
const NavigatorChip: React.FC<{name: string; slug: string}> = ({name, slug}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pop = spring({frame, fps, config: {damping: 12, stiffness: 190}});
  const ink = BRAND.ink;
  return (
    <div
      style={{
        position: 'absolute',
        left: CHIP.left,
        bottom: CHIP.bottom,
        display: 'flex',
        alignItems: 'center',
        gap: 18,
        padding: '10px 30px 10px 10px',
        background: BRAND.white,
        border: `5px solid ${ink}`,
        borderRadius: 999,
        boxShadow: `8px 8px 0 ${ink}`,
        opacity: pop,
        transform: `scale(${0.7 + 0.3 * pop}) rotate(${(1 - pop) * -4}deg)`,
        transformOrigin: 'left center',
      }}
    >
      <div
        style={{
          width: CHIP.faceSize,
          height: CHIP.faceSize,
          borderRadius: '50%',
          background: CAST_BG[slug] ?? BRAND.sun,
          border: `4px solid ${ink}`,
          display: 'grid',
          placeItems: 'center',
          overflow: 'hidden',
        }}
      >
        <Img src={staticFile(`faces/${slug}.svg`)} style={{width: CHIP.faceSize - 8, height: CHIP.faceSize - 8}} />
      </div>
      <div style={{display: 'flex', flexDirection: 'column', lineHeight: 1}}>
        <span
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontWeight: 700,
            fontSize: 16,
            letterSpacing: 3,
            color: ink,
            opacity: 0.6,
            marginBottom: 6,
          }}
        >
          {CHIP.label}
        </span>
        <span style={{fontFamily: "'Bagel Fat One', sans-serif", fontSize: CHIP.nameSize, color: ink}}>{name}</span>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------- end card

const EndCard: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const ink = BRAND.ink;
  const title = spring({frame: frame - f(END_CARD.titleAt), fps, config: {damping: 14, stiffness: 160}});
  const url = spring({frame: frame - f(END_CARD.urlAt), fps, config: {damping: 13, stiffness: 170}});
  return (
    <AbsoluteFill style={{background: BRAND.sun, alignItems: 'center'}}>
      <div
        style={{
          marginTop: 96,
          opacity: title,
          transform: `translateY(${(1 - title) * 24}px)`,
          fontFamily: "'Bagel Fat One', sans-serif",
          fontSize: 104,
          color: ink,
          letterSpacing: -1,
        }}
      >
        {END_CARD.title}
      </div>
      <div style={{marginTop: 54, display: 'grid', gridTemplateColumns: 'repeat(6, 150px)', gap: 30}}>
        {cuts.cast.map((c, i) => {
          const s = spring({
            frame: frame - f(END_CARD.badgesAt) - i * END_CARD.badgeStaggerFrames,
            fps,
            config: {damping: 11, stiffness: 210},
          });
          return (
            <div
              key={c.slug}
              style={{
                width: 150,
                height: 150,
                borderRadius: '50%',
                background: c.bg,
                border: `5px solid ${ink}`,
                boxShadow: `6px 6px 0 ${ink}`,
                display: 'grid',
                placeItems: 'center',
                transform: `scale(${s}) rotate(${(i % 2 ? 5 : -6) * s}deg)`,
              }}
            >
              <Img src={staticFile(`faces/${c.slug}.svg`)} style={{width: 134, height: 134}} />
            </div>
          );
        })}
      </div>
      <div
        style={{
          marginTop: 66,
          transform: `scale(${0.85 + 0.15 * url})`,
          opacity: url,
          background: BRAND.white,
          color: ink,
          border: `6px solid ${ink}`,
          borderRadius: 999,
          padding: '14px 60px 22px',
          fontFamily: "'Bagel Fat One', sans-serif",
          fontSize: 96,
          boxShadow: `12px 12px 0 ${ink}`,
        }}
      >
        {END_CARD.url}
      </div>
      <div
        style={{
          position: 'absolute',
          bottom: 40,
          opacity: url * 0.8,
          fontFamily: "'Bricolage Grotesque', sans-serif",
          fontWeight: 500,
          fontSize: 24,
          color: ink,
        }}
      >
        {END_CARD.footer}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- sound

const musicVolume = (placed: Placed[], endStart: number) => (frame: number) => {
  const t = frame / FPS;
  let level = 1;
  for (const p of placed) {
    const out = interpolate(t, [p.voiceStart - MIX.duckOut, p.voiceStart], [1, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
    const back = interpolate(t, [p.reaction, p.reaction + MIX.duckIn], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
    if (t >= p.voiceStart - MIX.duckOut && t < p.reaction + MIX.duckIn) {
      level = Math.min(level, t < p.reaction ? out : back);
    }
  }
  const stop = interpolate(t, [endStart - 0.3, endStart], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return gain(MIX.musicDb) * level * stop;
};

// ---------------------------------------------------------------- the ad

export const Ad: React.FC = () => {
  const {placed, endStart, endDur} = buildTimeline();
  return (
    <AbsoluteFill style={{background: '#000'}}>
      {VIGNETTES.map((v, i) => {
        const p = placed[i];
        return (
          <React.Fragment key={v.id}>
            <Sequence from={f(p.extStart)} durationInFrames={f(p.intStart) - f(p.extStart)}>
              <Clip shot={v.exterior} />
            </Sequence>
            {v.interior && (
              <Sequence from={f(p.intStart)} durationInFrames={f(p.end) - f(p.intStart)}>
                <Clip shot={v.interior} />
              </Sequence>
            )}
            <Sequence from={f(p.voiceStart)} durationInFrames={f(p.end) - f(p.voiceStart)}>
              <NavigatorChip name={v.navigator.name} slug={v.navigator.slug} />
            </Sequence>
            <Sequence from={f(p.extStart)} durationInFrames={f(p.end) - f(p.extStart)}>
              <Audio src={staticFile(MEDIA[v.ambience.src].file)} loop volume={gain(v.ambience.db)} />
            </Sequence>
            <Sequence from={f(p.voiceStart)}>
              <Audio src={staticFile(MEDIA[v.voice].file)} volume={gain(MIX.voiceDb)} />
            </Sequence>
            {v.hit && (
              <Sequence
                from={f(p.reaction - v.hit.offset)}
                durationInFrames={f(endStart + MIX.hitTailFade) - f(p.reaction - v.hit.offset)}
              >
                <HitAudio src={MEDIA[v.hit.src].file} db={v.hit.db} fadeAt={endStart - (p.reaction - v.hit.offset)} />
              </Sequence>
            )}
          </React.Fragment>
        );
      })}
      <Sequence from={0} durationInFrames={f(endStart)}>
        <Audio src={staticFile(MEDIA.score.file)} volume={musicVolume(placed, endStart)} />
      </Sequence>
      <Sequence from={f(endStart)} durationInFrames={f(endDur)}>
        <EndCard />
        <Audio src={staticFile(MEDIA.sfx_signal.file)} loop volume={gain(MIX.signalDb)} />
      </Sequence>
    </AbsoluteFill>
  );
};

const HitAudio: React.FC<{src: string; db: number; fadeAt: number}> = ({src, db, fadeAt}) => (
  <Audio
    src={staticFile(src)}
    volume={(frame) =>
      gain(db) *
      interpolate(frame / FPS, [fadeAt, fadeAt + MIX.hitTailFade], [1, 0], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      })
    }
  />
);
