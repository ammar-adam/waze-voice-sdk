import React from 'react';
import {Composition} from 'remotion';
import {Ad} from './Ad';
import * as AD from './config';
import {FPS, Film, cutLength} from './Film';
import {GETAWAY_FRAMES, Getaway} from './Getaway';

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
    {/* TOUGH CROWD (film/runway2/plan.md): one timeline, two frames. */}
    {/* THE GETAWAY, action-chase revision (film/runway4/plan.md): 16:9 full frame only. */}
    <Composition id="Getaway" component={Getaway} durationInFrames={GETAWAY_FRAMES} fps={24} width={1920} height={1080} />
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
