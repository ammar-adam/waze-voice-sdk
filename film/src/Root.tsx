import React from 'react';
import {Composition} from 'remotion';
import {Ad} from './Ad';
import * as AD from './config';
import {FPS, Film, cutLength} from './Film';

// One composition per cut in docs/launch-film.md. 9:16 for TikTok, Reels and Shorts.
const CUTS = ['MissedTurn', 'VaderOpen', 'PoliceAhead', 'Arrived'];

export const Root: React.FC = () => (
  <>
    <Composition
      id="Backseat30"
      component={Ad}
      durationInFrames={AD.TOTAL_SECONDS * AD.FPS}
      fps={AD.FPS}
      width={AD.WIDTH}
      height={AD.HEIGHT}
    />
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
