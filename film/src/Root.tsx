import React from 'react';
import {Composition} from 'remotion';
import {FPS, Film, cutLength} from './Film';

// One composition per cut in docs/launch-film.md. 9:16 for TikTok, Reels and Shorts.
const CUTS = ['MissedTurn', 'VaderOpen', 'PoliceAhead', 'Arrived'];

export const Root: React.FC = () => (
  <>
    {CUTS.map((id) => (
      <Composition
        key={id}
        id={id}
        component={Film}
        defaultProps={{cut: id}}
        durationInFrames={cutLength(id)}
        fps={FPS}
        width={1080}
        height={1920}
      />
    ))}
  </>
);
