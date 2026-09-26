import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
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
import data from './cuts.json';

// The site's type and palette, so the film and backseatnav.com look like one thing.
const INK = '#15172b';
const SUN = '#ffd23f';
const POP = '#ff5a1f';
const DISPLAY = "'Bagel Fat One', sans-serif";
const BODY = "'Bricolage Grotesque', sans-serif";
const MONO = "'JetBrains Mono', monospace";

// Retried rather than left hanging: under parallel rendering a font load can
// stall in one tab, and a silent fallback font would ship the wrong look.
const fontsReady = delayRender('fonts', {timeoutInMilliseconds: 60000, retries: 2});
Promise.all(
  [
    ['Bagel Fat One', 'fonts/BagelFatOne.ttf', '400'],
    ['Bricolage Grotesque', 'fonts/Bricolage.ttf', '200 800'],
    ['JetBrains Mono', 'fonts/JetBrainsMono.ttf', '100 800'],
  ].map(([family, file, weight]) =>
    new FontFace(family, `url('${staticFile(file)}')`, {weight})
      .load()
      .then((face) => document.fonts.add(face)),
  ),
)
  .then(() => continueRender(fontsReady))
  .catch((error) => cancelRender(error));

export type Segment = {
  slug: string;
  name: string;
  line: string;
  audio: string;
  frames: number;
  bg: string;
  tone: string;
  toneInk: string;
};
type Cut = {
  hook: string;
  scene: string;
  pause: string;
  segments: Segment[];
  button: Segment | null;
};
type Scene = 'exit' | 'police' | 'arrive';

export const FPS = data.fps;
const PAUSE_FRAMES = 36;
const END_FRAMES = 110;
const CUTS = data.cuts as Record<string, Cut>;

export const cutLength = (id: string): number => {
  const cut = CUTS[id];
  return (
    cut.segments.reduce((sum, s) => sum + s.frames, 0) +
    (cut.pause ? PAUSE_FRAMES : 0) +
    (cut.button ? cut.button.frames : 0) +
    END_FRAMES
  );
};

// ---------------------------------------------------------------- the road

const HORIZON = 640;
const ROAD_BOTTOM = 1320;

const Road: React.FC<{scene: Scene; mood: string}> = ({scene, mood}) => {
  const frame = useCurrentFrame();
  const dusk = scene === 'arrive';
  const phase = (frame * 0.045) % 1;
  const dashes = Array.from({length: 9}, (_, i) => {
    const d = (i + phase) / 9;
    const y = HORIZON + (ROAD_BOTTOM - HORIZON) * Math.pow(d, 2.1);
    return {y, h: 6 + 90 * d * d, w: 3 + 22 * d};
  });
  const lamps = Array.from({length: 4}, (_, i) => {
    const d = (i + ((frame * 0.03) % 1)) / 4;
    const t = Math.pow(d, 2.2);
    return {x: 470 - 620 * t, y: HORIZON - 10 - 520 * t, s: 0.15 + 1.4 * t, o: Math.min(1, d * 3)};
  });
  const buildings = [60, 130, 95, 170, 120, 80, 150, 110, 70, 140, 100, 160, 90];
  return (
    <svg width={1080} height={1920} style={{position: 'absolute', inset: 0}}>
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={dusk ? '#2d2463' : '#0e1128'} />
          <stop offset="1" stopColor={dusk ? '#f08a5d' : '#2c3163'} />
        </linearGradient>
      </defs>
      <rect width={1080} height={HORIZON + 4} fill="url(#sky)" />
      {Array.from({length: 26}, (_, i) => (
        <circle
          key={i}
          cx={(i * 397) % 1080}
          cy={60 + ((i * 211) % 480)}
          r={i % 4 === 0 ? 3.5 : 2}
          fill="#fff"
          opacity={dusk ? 0.25 : 0.4 + 0.4 * Math.abs(Math.sin(frame / 20 + i))}
        />
      ))}
      <circle cx={860} cy={200} r={54} fill={dusk ? '#ffd9a0' : '#f4f1de'} stroke={INK} strokeWidth={6} />
      {buildings.map((h, i) => (
        <g key={i}>
          <rect x={i * 84 - 10} y={HORIZON - h} width={78} height={h} fill={dusk ? '#3b2e5a' : '#1c2045'} stroke={INK} strokeWidth={4} />
          {Array.from({length: Math.floor(h / 34)}, (_, j) => (
            <rect key={j} x={i * 84 + 8 + (j % 2) * 30} y={HORIZON - h + 14 + j * 30} width={14} height={12} fill={SUN} opacity={(i + j) % 3 === 0 ? 0.9 : 0.25} />
          ))}
        </g>
      ))}
      <rect y={HORIZON} width={1080} height={1920 - HORIZON} fill={dusk ? '#4b3f62' : '#1a1d3a'} />
      {/* Road, and the exit ramp peeling off to the right: the one we miss. */}
      <polygon points={`505,${HORIZON} 575,${HORIZON} 1480,${ROAD_BOTTOM} -400,${ROAD_BOTTOM}`} fill="#2b2f45" stroke={INK} strokeWidth={6} />
      {scene !== 'arrive' && (
        <polygon points={`585,${HORIZON + 6} 640,${HORIZON + 6} 1080,${HORIZON + 250} 1080,${HORIZON + 420}`} fill="#2b2f45" stroke={INK} strokeWidth={5} />
      )}
      <line x1={512} y1={HORIZON} x2={-300} y2={ROAD_BOTTOM} stroke="#f4f1de" strokeWidth={8} />
      <line x1={568} y1={HORIZON} x2={1380} y2={ROAD_BOTTOM} stroke="#f4f1de" strokeWidth={8} />
      {dashes.map((d, i) => (
        <rect key={i} x={540 - d.w / 2} y={d.y} width={d.w} height={d.h} fill={SUN} rx={d.w / 3} />
      ))}
      {lamps.map((l, i) => (
        <g key={i} transform={`translate(${l.x} ${l.y}) scale(${l.s})`} opacity={l.o}>
          <rect x={-8} y={0} width={16} height={460} fill="#3a3f5c" stroke={INK} strokeWidth={5} />
          <rect x={-8} y={-10} width={120} height={22} rx={10} fill="#3a3f5c" stroke={INK} strokeWidth={5} />
          <circle cx={104} cy={22} r={26} fill={SUN} opacity={0.9} />
        </g>
      ))}
      {scene === 'arrive' && <House />}
      {mood === 'darth-vader' && <rect width={1080} height={1920} fill="#ff1a1a" opacity={0.16} />}
      {mood === 'vito-corleone' && <rect width={1080} height={1920} fill="#000" opacity={0.25} />}
    </svg>
  );
};

const House: React.FC = () => {
  const frame = useCurrentFrame();
  const s = interpolate(frame, [0, 90], [0.8, 1.05], {extrapolateRight: 'clamp'});
  return (
    <g transform={`translate(540 ${HORIZON + 20}) scale(${s}) translate(-150 -250)`}>
      <polygon points="0,110 150,0 300,110" fill="#d8312a" stroke={INK} strokeWidth={8} strokeLinejoin="round" />
      <rect x={25} y={105} width={250} height={150} fill="#f4e1c1" stroke={INK} strokeWidth={8} />
      <rect x={120} y={165} width={60} height={90} fill="#8a5a2b" stroke={INK} strokeWidth={6} />
      <rect x={50} y={135} width={50} height={45} fill={SUN} stroke={INK} strokeWidth={6} />
      <rect x={200} y={135} width={50} height={45} fill={SUN} stroke={INK} strokeWidth={6} />
    </g>
  );
};

// The exit sign sweeps past at the start of every line: same mistake, new judge.
const ExitSign: React.FC = () => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [0, 26], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const e = p * p * p;
  if (p >= 1) return null;
  return (
    <div
      style={{
        position: 'absolute',
        left: 640 + 620 * e,
        top: HORIZON - 70 - 380 * e,
        transform: `translate(-50%, -50%) scale(${0.22 + 1.9 * e})`,
        transformOrigin: 'center',
      }}
    >
      <div style={{background: '#1f7a3a', border: `6px solid #fff`, outline: `5px solid ${INK}`, borderRadius: 18, padding: '10px 26px', color: '#fff', fontFamily: DISPLAY, fontSize: 64, whiteSpace: 'nowrap'}}>
        EXIT 42 ↗
      </div>
    </div>
  );
};

const Mirror: React.FC = () => {
  const frame = useCurrentFrame();
  const red = Math.floor(frame / 6) % 2 === 0;
  return (
    <div style={{position: 'absolute', left: 290, top: 250, width: 500, height: 150, borderRadius: 40, background: '#0b0d1e', border: `8px solid ${INK}`, boxShadow: `8px 8px 0 ${INK}`, overflow: 'hidden'}}>
      <div style={{position: 'absolute', left: red ? 60 : 280, top: 20, width: 160, height: 110, borderRadius: '50%', background: red ? '#ff2a2a' : '#2a6cff', filter: 'blur(28px)', opacity: 0.95}} />
    </div>
  );
};

// ---------------------------------------------------------------- the dash

const Dash: React.FC = () => (
  <svg width={1080} height={1920} style={{position: 'absolute', inset: 0}}>
    <path d="M-20 1330 Q540 1220 1100 1330 L1100 1940 L-20 1940Z" fill="#1b1d33" stroke={INK} strokeWidth={8} />
    <path d="M40 1330 Q540 1245 1040 1330" fill="none" stroke="#3a3f5c" strokeWidth={6} strokeLinecap="round" />
    <rect x={470} y={1860} width={140} height={60} rx={14} fill="#2b2f45" stroke={INK} strokeWidth={6} />
  </svg>
);

const Phone: React.FC<{children: React.ReactNode; bg: string}> = ({children, bg}) => (
  <div style={{position: 'absolute', left: 250, top: 1090, width: 580, height: 760, borderRadius: 64, background: INK, padding: 18, boxShadow: `14px 14px 0 #000`}}>
    <div style={{width: '100%', height: '100%', borderRadius: 48, background: bg, overflow: 'hidden', position: 'relative', border: `5px solid ${INK}`}}>
      {children}
    </div>
  </div>
);

// ---------------------------------------------------------------- a line

const Bubble: React.FC<{text: string; speakFrames: number}> = ({text, speakFrames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pop = spring({frame: frame - 2, fps, config: {damping: 11, stiffness: 180}});
  const words = text.split(' ');
  const per = Math.max(2, (speakFrames * 0.8) / words.length);
  const size = text.length > 52 ? 60 : text.length > 32 ? 68 : 80;
  return (
    <div style={{position: 'absolute', left: 70, right: 70, top: 730, display: 'flex', justifyContent: 'center'}}>
      <div style={{transform: `scale(${0.6 + 0.4 * pop}) rotate(${-1.5 + 1.5 * pop}deg)`, opacity: pop, background: '#fff', border: `7px solid ${INK}`, borderRadius: 40, boxShadow: `12px 12px 0 ${INK}`, padding: '30px 40px', position: 'relative', maxWidth: 940}}>
        <div style={{fontFamily: BODY, fontWeight: 800, fontSize: size, lineHeight: 1.08, color: INK, letterSpacing: -1}}>
          {words.map((w, i) => (
            <span key={i} style={{opacity: frame >= 3 + i * per ? 1 : 0.14}}>
              {w}{' '}
            </span>
          ))}
        </div>
        <div style={{position: 'absolute', left: '50%', bottom: -44, width: 56, height: 56, background: '#fff', borderRight: `7px solid ${INK}`, borderBottom: `7px solid ${INK}`, transform: 'translateX(-50%) rotate(45deg)'}} />
      </div>
    </div>
  );
};

const Face: React.FC<{seg: Segment; speakFrames: number}> = ({seg, speakFrames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const slam = spring({frame, fps, config: {damping: 9, stiffness: 220, mass: 0.7}});
  const talking = frame < speakFrames;
  const bob = talking ? Math.sin(frame / 2.2) : 0;
  if (seg.slug === 'default') {
    return (
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 30}}>
        <svg width={300} height={300} viewBox="0 0 100 100" style={{transform: `rotate(${frame * 6}deg)`}}>
          <path d="M50 12 A38 38 0 1 1 16 36" fill="none" stroke={INK} strokeWidth={9} strokeLinecap="round" />
          <polygon points="4,30 26,24 22,46" fill={INK} />
        </svg>
        <div style={{fontFamily: MONO, fontWeight: 700, fontSize: 40, color: INK, letterSpacing: 2}}>YOUR GPS</div>
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column'}}>
      <div style={{width: 420, height: 420, borderRadius: '50%', background: '#fff', border: `8px solid ${INK}`, boxShadow: `10px 10px 0 ${INK}`, display: 'grid', placeItems: 'center', transform: `scale(${2.3 - 1.3 * slam}) rotate(${(1 - slam) * -24 + bob * 3}deg) translateY(${bob * 6}px)`}}>
        <Img src={staticFile(`faces/${seg.slug}.svg`)} style={{width: 380, height: 380}} />
      </div>
      <div style={{marginTop: 44, background: seg.tone, color: seg.toneInk, border: `5px solid ${INK}`, borderRadius: 999, padding: '12px 30px', fontFamily: MONO, fontWeight: 700, fontSize: 36, letterSpacing: 2, textTransform: 'uppercase', boxShadow: `6px 6px 0 ${INK}`, opacity: slam}}>
        {seg.name}
      </div>
    </AbsoluteFill>
  );
};

const Line: React.FC<{seg: Segment; scene: Scene; sweep: boolean}> = ({seg, scene, sweep}) => {
  const frame = useCurrentFrame();
  const speakFrames = seg.frames - Math.round(0.3 * FPS);
  const wash = interpolate(frame, [0, 7], [0.6, 0], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill>
      <Audio src={staticFile(seg.audio)} />
      <Road scene={scene} mood={seg.slug} />
      {scene === 'police' && <Mirror />}
      {sweep && scene === 'exit' && <ExitSign />}
      <Dash />
      <Phone bg={seg.bg}>
        <Face seg={seg} speakFrames={speakFrames} />
      </Phone>
      <Bubble text={seg.line} speakFrames={speakFrames} />
      <AbsoluteFill style={{background: seg.bg, opacity: wash}} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- the rest

const Pause: React.FC<{text: string}> = ({text}) => {
  const frame = useCurrentFrame();
  const on = Math.floor(frame / 8) % 2 === 0;
  return (
    <AbsoluteFill>
      <Road scene="exit" mood="" />
      <Dash />
      <Phone bg="#1b1d33">
        <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
          <svg width={260} height={200} viewBox="0 0 130 100" opacity={on ? 1 : 0.15}>
            <polygon points="10,35 70,35 70,10 120,50 70,90 70,65 10,65" fill="#3ddc6b" stroke={INK} strokeWidth={6} strokeLinejoin="round" />
          </svg>
        </AbsoluteFill>
      </Phone>
      <div style={{position: 'absolute', top: 560, width: '100%', textAlign: 'center', fontFamily: BODY, fontWeight: 800, fontSize: 64, color: '#fff', textShadow: `5px 5px 0 ${INK}`}}>{text}</div>
    </AbsoluteFill>
  );
};

const Hook: React.FC<{text: string}> = ({text}) => (
  <div style={{position: 'absolute', top: 110, width: '100%', display: 'flex', justifyContent: 'center'}}>
    <div style={{background: SUN, border: `6px solid ${INK}`, borderRadius: 999, boxShadow: `8px 8px 0 ${INK}`, padding: '16px 38px', fontFamily: BODY, fontWeight: 800, fontSize: 52, color: INK}}>{text}</div>
  </div>
);

const EndCard: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const head = spring({frame, fps, config: {damping: 12}});
  return (
    <AbsoluteFill style={{background: SUN, alignItems: 'center'}}>
      <div style={{marginTop: 150, transform: `scale(${0.7 + 0.3 * head}) rotate(${-2 + 2 * head}deg)`, background: '#fff', border: `8px solid ${INK}`, borderRadius: 48, boxShadow: `16px 16px 0 ${INK}`, padding: '44px 56px', width: 900}}>
        <div style={{fontFamily: DISPLAY, fontSize: 150, lineHeight: 0.92, color: INK}}>
          Make your GPS{' '}
          <span style={{display: 'inline-block', color: POP, transform: 'rotate(-3deg)', textShadow: `6px 6px 0 ${INK}`}}>iconic.</span>
        </div>
      </div>
      <div style={{marginTop: 70, display: 'grid', gridTemplateColumns: 'repeat(4, 200px)', gap: 18}}>
        {data.cast.map((c, i) => {
          const s = spring({frame: frame - 6 - i * 2, fps, config: {damping: 10, stiffness: 200}});
          return (
            <div key={c.slug} style={{width: 200, height: 200, borderRadius: '50%', background: c.bg, border: `6px solid ${INK}`, boxShadow: `7px 7px 0 ${INK}`, display: 'grid', placeItems: 'center', transform: `scale(${s}) rotate(${(i % 2 ? 5 : -6) * s}deg)`}}>
              <Img src={staticFile(`faces/${c.slug}.svg`)} style={{width: 180, height: 180}} />
            </div>
          );
        })}
      </div>
      <div style={{marginTop: 80, background: INK, color: SUN, borderRadius: 999, padding: '22px 52px', fontFamily: MONO, fontWeight: 700, fontSize: 60, opacity: interpolate(frame, [30, 40], [0, 1], {extrapolateRight: 'clamp'})}}>
        backseatnav.com
      </div>
      <div style={{marginTop: 28, fontFamily: BODY, fontWeight: 700, fontSize: 46, color: INK, opacity: interpolate(frame, [38, 48], [0, 1], {extrapolateRight: 'clamp'})}}>
        Free. One tap into Waze.
      </div>
    </AbsoluteFill>
  );
};

export const Film: React.FC<{cut: string}> = ({cut}) => {
  const c = CUTS[cut];
  const scene = c.scene as Scene;
  let at = 0;
  const parts: React.ReactNode[] = [];
  c.segments.forEach((seg, i) => {
    parts.push(
      <Sequence key={`s${i}`} from={at} durationInFrames={seg.frames}>
        <Line seg={seg} scene={scene} sweep />
      </Sequence>,
    );
    at += seg.frames;
  });
  const runEnd = at;
  if (c.pause) {
    parts.push(
      <Sequence key="pause" from={at} durationInFrames={PAUSE_FRAMES}>
        <Pause text={c.pause} />
      </Sequence>,
    );
    at += PAUSE_FRAMES;
  }
  if (c.button) {
    parts.push(
      <Sequence key="button" from={at} durationInFrames={c.button.frames}>
        <Line seg={c.button} scene="arrive" sweep={false} />
      </Sequence>,
    );
    at += c.button.frames;
  }
  const hookEnd = at;
  parts.push(
    <Sequence key="end" from={at} durationInFrames={END_FRAMES}>
      <EndCard />
    </Sequence>,
  );
  return (
    <AbsoluteFill style={{background: INK}}>
      {parts}
      <Sequence from={0} durationInFrames={hookEnd}>
        <Hook text={c.hook} />
      </Sequence>
      <Sequence from={0} durationInFrames={runEnd}>
        <div style={{position: 'absolute', bottom: 22, width: '100%', textAlign: 'center', fontFamily: MONO, fontWeight: 700, fontSize: 34, color: '#8c93c7'}}>backseatnav.com</div>
      </Sequence>
    </AbsoluteFill>
  );
};
