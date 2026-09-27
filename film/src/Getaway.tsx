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
import {
  BAR,
  BRAND,
  CAST,
  END,
  FONT,
  FPS,
  GRADE,
  LINES,
  PHONE,
  SHOTS,
  SPEEDO,
  T,
  TAP_LEAD,
  TOTAL_FRAMES,
  WIN9,
  castOf,
  type Line,
  type Rect,
  type Shot,
} from './getaway.config';

// THE GETAWAY (film/runway3/plan.md). Picture only: the sound is built
// sample-accurately outside Remotion by scripts/mix_getaway.py from the same
// config (Remotion's own audio drifted 1 to 4 frames on the last film).

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
const smooth = (k: number) => k * k * (3 - 2 * k);

type Layout = {vertical: boolean};

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
  const scale = p.to ? p.scale + (p.to - p.scale) * progress(shot, frame) : p.scale;
  const w = 1920 / scale;
  const h = 1080 / scale;
  return {x: Math.min(Math.max(p.cx - w / 2, 0), 1920 - w), y: Math.min(Math.max(p.cy - h / 2, 0), 1080 - h), w, h};
};

const rect9 = (shot: Shot, frame: number): Rect => {
  const z0 = shot.f9.zoom ?? 1;
  const zoom = shot.f9.zoomTo ? z0 + (shot.f9.zoomTo - z0) * progress(shot, frame) : z0;
  const side = 1080 / zoom;
  const cy = shot.f9.y ?? 540;
  const cx = shot.f9.panTo === undefined ? shot.f9.x : shot.f9.x + (shot.f9.panTo - shot.f9.x) * progress(shot, frame);
  return {
    x: Math.min(Math.max(cx - side / 2, 0), 1920 - side),
    y: Math.min(Math.max(cy - side / 2, 0), 1080 - side),
    w: side,
    h: side,
  };
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

/** Whatever fills the picture area: 1920x1080 in 16:9; in 9:16 the sharp native
 * 1080 square window, over the same picture scaled to cover the whole 1080x1920
 * frame, heavily blurred and darkened (the fill), frame-synced because both are
 * drawn from the same source on the same frame. `fill(w, h)` draws the fill's
 * content; it defaults to `children`. */
const FILL = {blur: 50, brightness: 0.55, overscan: 1.12};
const Frame: React.FC<{
  layout: Layout;
  children: (w: number, h: number) => React.ReactNode;
  fill?: (w: number, h: number) => React.ReactNode;
}> = ({layout, children, fill}) => {
  const w = layout.vertical ? WIN9.size : 1920;
  const h = layout.vertical ? WIN9.size : 1080;
  return (
    <>
      {layout.vertical ? (
        <div style={{position: 'absolute', left: 0, top: 0, width: 1080, height: 1920, overflow: 'hidden', background: '#000'}}>
          {/* overscanned so the blur never pulls black in from the edges */}
          <div style={{position: 'absolute', left: 0, top: 0, width: 1080, height: 1920, transform: `scale(${FILL.overscan})`, filter: `blur(${FILL.blur}px) brightness(${FILL.brightness})`}}>
            {(fill ?? children)(1080, 1920)}
          </div>
          <Grain w={1080} h={1920} />
        </div>
      ) : null}
      <div style={{position: 'absolute', left: 0, top: layout.vertical ? WIN9.top : 0, width: w, height: h, overflow: 'hidden', boxShadow: layout.vertical ? '0 0 60px 10px rgba(0,0,0,0.45)' : undefined}}>
        {children(w, h)}
        <Grain w={w} h={h} />
      </div>
    </>
  );
};

/** 9:16 fill: a 9:16 column of the clip around the window's centre, covering 1080x1920. */
const rectFill = (shot: Shot, frame: number): Rect => {
  const r = rect9(shot, frame);
  const cx = r.x + r.w / 2;
  const w = (1080 * 1080) / 1920;
  return {x: Math.min(Math.max(cx - w / 2, 0), 1920 - w), y: 0, w, h: 1080};
};

const ShotView: React.FC<{shot: Shot; layout: Layout}> = ({shot, layout}) => {
  const frame = useCurrentFrame();
  return (
    <Frame layout={layout} fill={(w, h) => <View shot={shot} rect={rectFill(shot, frame)} boxW={w} boxH={h} />}>
      {(w, h) => <View shot={shot} rect={layout.vertical ? rect9(shot, frame) : rect16(shot, frame)} boxW={w} boxH={h} />}
    </Frame>
  );
};

// ================================================================= the speedometer (a digital cluster)

const Speedo: React.FC<{layout: Layout}> = ({layout}) => {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  // ease-out: the needle moves from the first frame and settles, like a car slowing down
  const k = 1 - (1 - interpolate(t, [SPEEDO.easeStart, SPEEDO.easeEnd], [0, 1], clamp)) ** 2.4;
  const mph = SPEEDO.from + (SPEEDO.to - SPEEDO.from) * k;
  const MAX = 160;
  const A0 = -120;
  const A1 = 120;
  const ang = (v: number) => A0 + ((A1 - A0) * v) / MAX;
  const R = 330;
  const ticks: React.ReactNode[] = [];
  for (let v = 0; v <= MAX; v += 5) {
    const a = (ang(v) * Math.PI) / 180;
    const major = v % 20 === 0;
    const r0 = R - (major ? 34 : v % 10 === 0 ? 22 : 12);
    const lit = v <= mph;
    ticks.push(
      <line
        key={v}
        x1={Math.sin(a) * r0}
        y1={-Math.cos(a) * r0}
        x2={Math.sin(a) * R}
        y2={-Math.cos(a) * R}
        stroke={lit ? '#e9f6ff' : 'rgba(170,200,230,0.28)'}
        strokeWidth={major ? 5 : 2.5}
        strokeLinecap="round"
      />,
    );
    if (major) {
      ticks.push(
        <text key={`t${v}`} x={Math.sin(a) * (R - 70)} y={-Math.cos(a) * (R - 70) + 11} textAnchor="middle" fontFamily={FONT.mono} fontWeight={500} fontSize={30} fill={lit ? '#dff1ff' : 'rgba(170,200,230,0.45)'}>
          {v}
        </text>,
      );
    }
  }
  const na = ang(mph);
  const arc = (from: number, to: number, r: number) => {
    const p = (v: number) => {
      const a = (ang(v) * Math.PI) / 180;
      return `${Math.sin(a) * r} ${-Math.cos(a) * r}`;
    };
    return `M ${p(from)} A ${r} ${r} 0 ${ang(to) - ang(from) > 180 ? 1 : 0} 1 ${p(to)}`;
  };
  // camera drift and passing streetlight glare
  const drift = smooth(interpolate(t, [0, 3.1], [0, 1], clamp)) * 0.6 + interpolate(t, [0, 3.1], [0, 0.4], clamp);
  const glare = (t * 0.55) % 1;
  return (
    <Frame layout={layout}>
      {(w, h) => (
        <div style={{position: 'absolute', inset: 0, width: w, height: h, background: 'radial-gradient(ellipse at 50% 55%, #0b1220 0%, #04060b 60%, #000 100%)', overflow: 'hidden'}}>
          <div
            style={{
              position: 'absolute',
              left: w / 2,
              top: h / 2 + (layout.vertical ? 170 : 250),
              transform: `translate(-50%, -50%) perspective(1100px) rotateX(${26 - 4 * drift}deg) rotateY(${-30 + 6 * drift}deg) rotateZ(-4deg) scale(${(layout.vertical ? 1.75 : 2.05) + 0.1 * drift})`,
              filter: 'drop-shadow(0 0 30px rgba(80,170,255,0.25))',
            }}
          >
            <svg width={900} height={900} viewBox="-450 -450 900 900" style={{overflow: 'visible'}}>
              <defs>
                <radialGradient id="face" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="scale(420)">
                  <stop offset="0" stopColor="#0c1726" />
                  <stop offset="0.8" stopColor="#060a12" />
                  <stop offset="1" stopColor="#020308" />
                </radialGradient>
                <linearGradient id="needle" x1="0" y1="0" x2="0" y2="-1" gradientUnits="objectBoundingBox">
                  <stop offset="0" stopColor="#ff3b2f" stopOpacity="0.2" />
                  <stop offset="1" stopColor="#ff5a3c" />
                </linearGradient>
              </defs>
              <circle r={400} fill="url(#face)" stroke="rgba(120,170,220,0.18)" strokeWidth={3} />
              <path d={arc(0, MAX, R + 18)} stroke="rgba(90,160,230,0.16)" strokeWidth={10} fill="none" strokeLinecap="round" />
              <path d={arc(0, mph, R + 18)} stroke="#58b8ff" strokeWidth={10} fill="none" strokeLinecap="round" style={{filter: 'drop-shadow(0 0 10px #3aa0ff)'}} />
              {ticks}
              <g transform={`rotate(${na})`} style={{filter: 'drop-shadow(0 0 12px rgba(255,70,40,0.9))'}}>
                <path d={`M -7 40 L -3 ${-R + 8} L 3 ${-R + 8} L 7 40 Z`} fill="#ff4a2e" />
              </g>
              <circle r={74} fill="#05080f" stroke="rgba(150,200,255,0.3)" strokeWidth={3} />
              <text y={92 + 60} textAnchor="middle" fontFamily={FONT.mono} fontWeight={300} fontSize={112} fill="#f2f8ff" style={{filter: 'drop-shadow(0 0 14px rgba(120,190,255,0.6))'}}>
                {Math.round(mph)}
              </text>
              <text y={92 + 104} textAnchor="middle" fontFamily={FONT.mono} fontWeight={500} fontSize={26} letterSpacing={6} fill="rgba(170,210,245,0.7)">
                MPH
              </text>
            </svg>
          </div>
          {/* depth of field: the far edges soften */}
          <div style={{position: 'absolute', inset: 0, backdropFilter: 'blur(12px)', WebkitMaskImage: 'radial-gradient(ellipse 34% 40% at 52% 48%, transparent 45%, #000 100%)', maskImage: 'radial-gradient(ellipse 34% 40% at 52% 48%, transparent 45%, #000 100%)'}} />
          {/* a passing streetlight sweeps across the glass */}
          <div style={{position: 'absolute', inset: 0, background: `linear-gradient(115deg, transparent ${glare * 140 - 40}%, rgba(255,190,120,0.10) ${glare * 140 - 25}%, rgba(255,220,170,0.16) ${glare * 140 - 20}%, transparent ${glare * 140 - 5}%)`, mixBlendMode: 'screen'}} />
          <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(40,90,160,0.10), transparent 40%)', mixBlendMode: 'screen'}} />
        </div>
      )}
    </Frame>
  );
};

// ================================================================= the site, on his phone

const ARROW = (
  <svg viewBox="0 0 24 24" style={{width: '1.05em', height: '1.05em'}} fill="none" stroke="currentColor" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 12h13" />
    <path d="m12 6 6 6-6 6" />
  </svg>
);

// The three preview buttons, captions and icons exactly as site/app.js draws them.
const CLIP_CAPS = [
  {cap: 'Starting a drive', icon: <path d="M7 4v16l13-8z" />},
  {cap: 'Recalculating', icon: <><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 4v7h-7" /></>},
  {cap: 'Arrived', icon: <><path d="M12 21s-6-5.4-6-10a6 6 0 0 1 12 0c0 4.6-6 10-6 10z" /><circle cx="12" cy="11" r="2" /></>},
];

const CARD_H = 2.5 + 192 + 27 + 42 + 13 + 62 + 13 + 50 + 17 + 2.5;
const CARD_GAP = 26;
const BUTTON_Y = 2.5 + 192 + 27 + 42 + 13 + 62 + 13 + 25;
const LIST_TOP = 96;
const THUMB_Y = 560;

/** One voice card as site/app.js builds it on a phone (site/style.css, 1rem = 16px). */
const VoiceCard: React.FC<{slug: string; pressed: number}> = ({slug, pressed}) => {
  const c = castOf(slug);
  return (
    <div style={{border: `2.5px solid ${INK}`, borderRadius: 22, overflow: 'hidden', background: BRAND.white, boxShadow: `7px 7px 0 ${INK}`, marginBottom: CARD_GAP, height: CARD_H, boxSizing: 'border-box'}}>
      <div style={{height: 192, boxSizing: 'border-box', borderBottom: `2.5px solid ${INK}`, background: c.bg, position: 'relative', display: 'grid', placeItems: 'center', paddingTop: 10}}>
        <Img src={staticFile(`ga/faces/${slug}.svg`)} style={{width: 160, height: 160}} />
        <span style={{position: 'absolute', left: 14, bottom: -17, padding: '5px 14px', background: BRAND.white, border: `2.5px solid ${INK}`, borderRadius: 999, boxShadow: `3px 3px 0 ${INK}`, fontFamily: FONT.display, fontSize: 21.6, lineHeight: 1.1, color: INK}}>
          {c.name}
        </span>
      </div>
      <div style={{padding: '27px 16px 17px', display: 'grid', gridTemplateRows: '42px 62px 50px', gap: 13}}>
        <p style={{margin: 0, color: BRAND.inkSoft, fontFamily: FONT.body, fontSize: 15.2, lineHeight: 1.35}}>{c.blurb}</p>
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 7}}>
          {CLIP_CAPS.map(({cap, icon}) => (
            <div key={cap} style={{minHeight: 62, padding: '9px 9px 8px', background: BRAND.ground, border: `2px solid ${INK}`, borderRadius: 12, fontFamily: FONT.mono, fontWeight: 500, fontSize: 10.2, letterSpacing: 0.5, textTransform: 'uppercase', color: INK, display: 'flex', flexDirection: 'column', gap: 6}}>
              <svg viewBox="0 0 24 24" style={{width: 17, height: 17, flex: 'none'}} fill="none" stroke={INK} strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
                {icon}
              </svg>
              {cap}
            </div>
          ))}
        </div>
        <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '14px 16px', border: `2.5px solid ${INK}`, borderRadius: 14, background: c.tone, color: c.toneInk, boxShadow: `${4 - 3 * pressed}px ${4 - 3 * pressed}px 0 ${INK}`, transform: `translate(${3 * pressed}px, ${3 * pressed}px)`, fontFamily: FONT.body, fontWeight: 700, fontSize: 16.8, lineHeight: 1}}>
          Install in Waze {ARROW}
        </div>
      </div>
    </div>
  );
};

const PhoneInsert: React.FC<{layout: Layout}> = ({layout}) => {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  const order = CAST.map((c) => c.slug);
  const from = order.indexOf(PHONE.startSlug);
  const to = order.indexOf(PHONE.targetSlug);
  const scrollFor = (i: number) => LIST_TOP + i * (CARD_H + CARD_GAP) + BUTTON_Y - THUMB_Y;
  const st = interpolate(t, [PHONE.hoverUntil, PHONE.scrollEnd], [0, 1], clamp);
  const ease = st < 0.5 ? 4 * st ** 3 : 1 - (-2 * st + 2) ** 3 / 2;
  // The first card can't scroll above the list top: clamp at 0 like a real page.
  const scroll = Math.max(0, scrollFor(from) + (scrollFor(to) - scrollFor(from)) * ease);
  const thumbY = to === 0 ? LIST_TOP + BUTTON_Y - Math.max(0, scroll) : THUMB_Y;
  const thumbYAt = interpolate(st, [0, 1], [THUMB_Y, thumbY], clamp);
  const pressed = interpolate(t, [PHONE.tapAt - 0.04, PHONE.tapAt, PHONE.tapAt + 0.12, PHONE.tapAt + 0.2], [0, 1, 1, 0], clamp);
  const ring = t < PHONE.tapAt ? 1 : interpolate(t, [PHONE.tapAt, PHONE.tapAt + 0.25], [1, 0], clamp);
  const ringScale = t < PHONE.tapAt ? 1 : interpolate(t, [PHONE.tapAt, PHONE.tapAt + 0.25], [0.8, 1.7], clamp);
  const blurPx = st > 0.1 && st < 0.9 ? 1.4 : 0;
  const SW = 390;
  const SH = 844;
  const v = layout.vertical;
  const scale = v ? 1700 / (SH + 36) : 1.28;
  const push = interpolate(t, [0, 0.8], [1, 1.04], clamp);
  return (
    <AbsoluteFill style={{background: '#000', overflow: 'hidden'}}>
      <Img src={staticFile('ga/insert_bg.jpg')} style={{position: 'absolute', inset: -40, width: 'calc(100% + 80px)', height: 'calc(100% + 80px)', objectFit: 'cover', filter: 'blur(26px) brightness(0.45) saturate(1.2)'}} />
      <div style={{position: 'absolute', left: '50%', top: '50%', transform: `translate(-50%, -50%) translateY(${v ? 0 : 200}px) scale(${scale * push}) rotate(${v ? -2 : -8}deg)`}}>
        <div style={{width: SW + 36, height: SH + 36, padding: 18, boxSizing: 'border-box', background: '#0a0b10', borderRadius: 64, boxShadow: '0 0 120px 30px rgba(190,215,255,0.22), inset 0 0 0 2px rgba(255,255,255,0.08)', position: 'relative'}}>
          <div style={{width: SW, height: SH, borderRadius: 48, overflow: 'hidden', background: BRAND.ground, position: 'relative'}}>
            <div style={{position: 'absolute', left: 18, right: 18, top: LIST_TOP - scroll, filter: blurPx ? `blur(${blurPx}px)` : undefined}}>
              {order.map((slug, i) => (
                <VoiceCard key={slug} slug={slug} pressed={i === to ? pressed : 0} />
              ))}
            </div>
            <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: 84, background: BRAND.ground, borderBottom: `2.5px solid ${INK}`, display: 'flex', alignItems: 'flex-end', padding: '0 18px 12px', fontFamily: FONT.display, fontSize: 27, color: INK}}>
              {PHONE.headline}
            </div>
            <div style={{position: 'absolute', left: SW / 2 - 34, top: thumbYAt - 34, width: 68, height: 68, borderRadius: '50%', border: `4px solid ${INK}`, background: 'rgba(255,255,255,0.35)', opacity: ring, transform: `scale(${ringScale})`}} />
            {/* the screen at night: a touch of glass sheen */}
            <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(120deg, rgba(255,255,255,0.10), transparent 35%)'}} />
          </div>
        </div>
      </div>
      <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 50%, rgba(0,0,0,0.55) 100%)'}} />
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

const Chip: React.FC<{line: Line; frame: number; dur: number; big: boolean}> = ({line, frame, dur, big}) => {
  const visible = frame >= 0 && frame < dur;
  const {scale, rot} = slap(frame, dur);
  const face = big ? 104 : 84;
  return (
    <div style={{display: 'inline-flex', alignItems: 'center', gap: 14, padding: '7px 26px 7px 7px', background: BRAND.sun, border: `${big ? 6 : 5}px solid ${INK}`, borderRadius: 999, boxShadow: `${big ? 8 : 6}px ${big ? 8 : 6}px 0 ${INK}`, transform: `scale(${visible ? scale : 0}) rotate(${rot}deg)`, transformOrigin: 'left center', visibility: visible ? 'visible' : 'hidden', whiteSpace: 'nowrap', flex: 'none'}}>
      <FaceBadge slug={line.slug} size={face} ring={big ? 5 : 4} />
      <span style={{fontFamily: FONT.display, fontSize: big ? 48 : 40, color: INK, lineHeight: 1, paddingBottom: 4}}>{line.name}</span>
    </div>
  );
};

/** The preset text exactly; the whole line readable at once, each word inking in as it is spoken. */
const Caption: React.FC<{line: Line; t: number; outT: number; big: boolean; maxWidth: number}> = ({line, t, outT, big, maxWidth}) => {
  const words = LINE_DATA[line.key].words;
  const visible = t >= 0 && t < outT;
  const pop = interpolate(t, [0, 3 / FPS], [0.9, 1], clamp);
  const off = interpolate(t, [outT - 3 / FPS, outT], [1, 0], clamp);
  return (
    <div style={{display: 'inline-block', maxWidth, padding: big ? '12px 24px 15px' : '9px 22px 12px', background: BRAND.white, border: `${big ? 5 : 4}px solid ${INK}`, borderRadius: big ? 20 : 16, boxShadow: `${big ? 6 : 5}px ${big ? 6 : 5}px 0 ${INK}`, transform: `scale(${visible ? pop * (0.6 + 0.4 * off) : 0}) rotate(0.8deg)`, visibility: visible ? 'visible' : 'hidden', fontFamily: FONT.body, fontWeight: 800, fontSize: big ? 54 : 40, lineHeight: 1.12, color: INK, textAlign: 'center', letterSpacing: -0.5}}>
      {words.map((w, i) => {
        const shown = interpolate(t, [w.start, w.start + 2 / FPS], [0, 1], clamp);
        return (
          <span key={i} style={{opacity: 0.3 + 0.7 * shown, display: 'inline-block', transform: `translateY(${-2 * shown}px)`}}>
            {w.w}
            {i < words.length - 1 ? ' ' : ''}
          </span>
        );
      })}
    </div>
  );
};

const VoiceUI: React.FC<{line: Line; layout: Layout; start: number}> = ({line, layout, start}) => {
  const frame = useCurrentFrame();
  const abs = start + frame;
  const chipFrame = abs - (line.at - TAP_LEAD);
  const chipDur = line.out - (line.at - TAP_LEAD);
  const t = (abs - line.at) / FPS;
  const outT = (line.out - line.at) / FPS;
  // Over the phone insert, nothing: the site is the picture.
  if (abs >= T.PHONE.fin && abs < T.PHONE.fout) return null;
  if (!layout.vertical) {
    return (
      <div style={{position: 'absolute', left: 40, right: 40, bottom: 26, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 18}}>
        <Chip line={line} frame={chipFrame} dur={chipDur} big={false} />
        <Caption line={line} t={t} outT={outT} big={false} maxWidth={1460} />
      </div>
    );
  }
  // 9:16: chip over the window's top edge, caption over its bottom edge (safe zone y 200..1500).
  return (
    <>
      <div style={{position: 'absolute', left: 60, top: WIN9.top - 92}}>
        <Chip line={line} frame={chipFrame} dur={chipDur} big />
      </div>
      <div style={{position: 'absolute', left: 60, width: 960, top: WIN9.top + WIN9.size - 56, display: 'flex', justifyContent: 'center'}}>
        <Caption line={line} t={t} outT={outT} big maxWidth={940} />
      </div>
    </>
  );
};

const Voice: React.FC<{line: Line; layout: Layout}> = ({line, layout}) => {
  const start = line.at - TAP_LEAD;
  return (
    <Sequence from={start} durationInFrames={line.out - start} name={`voice ui ${line.key}`}>
      <VoiceUI line={line} layout={layout} start={start} />
    </Sequence>
  );
};

// ================================================================= end card

const EndCard: React.FC<{layout: Layout}> = ({layout}) => {
  const frame = useCurrentFrame();
  const v = layout.vertical;
  const title = interpolate(frame, [0, 2, 4], [0.9, 1.04, 1], clamp);
  const urlS = interpolate(frame, [0, 2, 4], [0.94, 1.05, 1], clamp);
  const cols = v ? 3 : 6;
  const face = v ? 126 : 140;
  const bugsIdx = CAST.findIndex((c) => c.slug === 'bugs-bunny');
  return (
    <AbsoluteFill style={{background: BRAND.sun, alignItems: 'center'}}>
      <div style={{position: 'absolute', top: v ? 230 : 52, left: v ? 60 : 0, width: v ? 960 : 1920, textAlign: 'center', transform: `scale(${title}) rotate(-1.5deg)`, fontFamily: FONT.display, fontSize: v ? 96 : 100, lineHeight: 1.02, color: INK, textShadow: '6px 6px 0 rgba(21,23,43,0.18)'}}>
        {END.title}
      </div>
      <div style={{position: 'absolute', top: v ? 452 : 210, left: v ? 60 : 0, width: v ? 960 : 1920, display: 'flex', justifyContent: 'center'}}>
        <div style={{display: 'grid', gridTemplateColumns: `repeat(${cols}, ${face + (v ? 120 : 64)}px)`, rowGap: v ? 10 : 30, justifyItems: 'center'}}>
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
                <span style={{marginTop: -16, padding: '3px 12px 5px', background: BRAND.white, border: `3px solid ${INK}`, borderRadius: 999, boxShadow: `3px 3px 0 ${INK}`, fontFamily: FONT.display, fontSize: v ? 25 : 21, color: INK, whiteSpace: 'nowrap', position: 'relative'}}>
                  {c.name}
                </span>
              </div>
            );
          })}
        </div>
      </div>
      <div style={{position: 'absolute', top: v ? 1210 : 700, left: v ? 60 : 0, width: v ? 960 : 1920, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: v ? 22 : 20}}>
        <div style={{transform: `scale(${urlS}) rotate(-1deg)`, background: INK, color: BRAND.sun, borderRadius: 999, padding: v ? '16px 48px 24px' : '12px 64px 20px', fontFamily: FONT.display, fontSize: v ? 84 : 100, lineHeight: 1, boxShadow: '10px 10px 0 rgba(21,23,43,0.3)'}}>
          {END.url}
        </div>
        <div style={{fontFamily: FONT.body, fontWeight: 700, fontSize: v ? 46 : 42, color: INK}}>{END.tagline}</div>
      </div>
      <div style={{position: 'absolute', top: v ? 1452 : undefined, bottom: v ? undefined : 30, left: v ? 60 : 0, width: v ? 960 : 1920, textAlign: 'center', fontFamily: FONT.body, fontWeight: 500, fontSize: v ? 26 : 24, color: INK, opacity: 0.85}}>
        {END.footer}
      </div>
    </AbsoluteFill>
  );
};

// ================================================================= the film

const Bars: React.FC = () => (
  <>
    <div style={{position: 'absolute', left: 0, top: 0, width: 1920, height: BAR, background: '#000'}} />
    <div style={{position: 'absolute', left: 0, bottom: 0, width: 1920, height: BAR, background: '#000'}} />
  </>
);

export const Getaway: React.FC<{vertical: boolean}> = ({vertical}) => {
  const layout: Layout = {vertical};
  return (
    <AbsoluteFill style={{background: '#000'}}>
      {SHOTS.map((shot) => (
        <Sequence key={shot.id} from={shot.fin} durationInFrames={shot.fout - shot.fin} name={shot.id}>
          <ShotView shot={shot} layout={layout} />
        </Sequence>
      ))}
      <Sequence from={T.SPEEDO.fin} durationInFrames={T.SPEEDO.fout - T.SPEEDO.fin} name="SPEEDO">
        <Speedo layout={layout} />
      </Sequence>
      <Sequence from={T.PHONE.fin} durationInFrames={T.PHONE.fout - T.PHONE.fin} name="PHONE">
        <PhoneInsert layout={layout} />
      </Sequence>
      {!vertical ? (
        <Sequence from={0} durationInFrames={T.END.fin} name="letterbox">
          <Bars />
        </Sequence>
      ) : null}
      {LINES.map((l) => (
        <Voice key={l.key} line={l} layout={layout} />
      ))}
      <Sequence from={T.END.fin} durationInFrames={TOTAL_FRAMES - T.END.fin} name="end card">
        <EndCard layout={layout} />
      </Sequence>
    </AbsoluteFill>
  );
};

export const GETAWAY_FRAMES = TOTAL_FRAMES;
