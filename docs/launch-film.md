# Launch film

**One moment every driver knows, twelve ways.** You miss the exit. The GPS
says "Recalculating." Then it says it again, and again, each time as a
different character, each one angrier than the last, until Darth Vader.

The first plan was three short loops (Default, Paddington, Cookie Monster)
running the same three beats. That worked with seven gentle characters. With
villains in the cast, the strongest thing we have is contrast: Paddington and
Darth Vader reacting to the *same* mistake. So the film is one beat, cut hard,
in escalating order.

Every line is a real prompt from a live pack, cut by
`scripts/build_film_audio.py` into `film-audio/` (git-ignored). The exact words
and lengths are in [film-line-sheet.md](film-line-sheet.md). Trimming the tail
of a clip is fine; adding a word that is not in the pack is not.

## Rendering: no hand edit

All four cuts are rendered straight to MP4 by the Remotion project in `film/`:
an illustrated night drive in the site's sticker style, the character's face
landing on the phone, and the line as a word-by-word caption. Timing comes
from the real clip lengths, so a changed line re-times itself.

    python scripts/build_film_audio.py     # cut the beats from the live packs
    python scripts/prepare_film.py         # cuts.json + audio, faces, fonts
    cd film && npm install && npm run render

The four MP4s land in `film/out/`, ready to post. The cut order and hooks live
in `CUTS` in `scripts/prepare_film.py`; the look lives in `film/src/Film.tsx`.
Runway footage (below) is an optional upgrade that goes behind the same edit.

---

## Cut A: "Missed turn" (hero, 44s, 9:16)

Rendered to `film/out/missed-turn.mp4`. Timings are the real clip lengths.

| Time | Picture | Audio (real prompt) |
| --- | --- | --- |
| 0.0 | Night POV, the exit sign slides past on the right. Text: **POV: you missed your exit** | "Recalculating." |
| 1.7 | Hard cut. Paddington's face slams onto the phone | "Oh dear. Things are always happening to me. Recalculating." |
| 7.8 | Hagrid | "Missed it! Blimey. That's my fault, that is. Recalculating." |
| 14.3 | Cookie Monster | "Oops. Me find new way. Om nom nom." |
| 18.8 | Gordon Ramsay | "You missed it, you donkey! Recalculating." |
| 22.9 | Eric Cartman | "You missed it! Oh my God, you guys. Recalculating." |
| 26.0 | Batman | "Wrong turn. Why do we fall? Recalculating." |
| 29.9 | Vader. Red tint, the car goes silent | "You have failed me for the last time with that turn. Recalculating." |
| 36.3 | A beat of nothing. Indicator blinks. Text: **Next exit. Very carefully.** | (silence) |
| 37.5 | Driveway, a house at the end of the road | Eric Cartman: "We're here! Screw you guys, I'm going home." |
| 39.9 | End card, below | none |

**Why this order.** Each cut has to be a harder turn than the last, or the
supercut flattens into a list. Sweet (Paddington, Hagrid), then chaos
(Cookie), then fury (Ramsay), rude (Cartman), cold (Batman), and Vader to
close it. The silence after Vader is the laugh. Cartman's "I'm going home" is
the button because it undercuts all the menace that came before.

**End card.** The twelve faces pop in one at a time, the same layout as
`site/og.png`. **Make your GPS iconic.** Under it: **backseatnav.com**, and "Free.
One tap into Waze."

## Cut B: "Vader cold open" (about 21s)

For feeds where the first second decides everything. Rendered to
`film/out/vader-open.mp4`.

Vader first, with no setup: "You have failed me for the last time with that
turn." Then Cartman, Elmo and Ramsay, one after another, and the Cartman arrival
as the button. Text on frame one: **your GPS, but it's Darth Vader**. Post it
as a separate video, not as a remix of A, so the two get compared cleanly.

## The series

Each post is one beat, cut the same way, on a different slot. Rendered to
`film/out/`:

| Post | Beat | Order | Video |
| --- | --- | --- | --- |
| 2. Police ahead | `police_ahead` | Default, Paddington ("I shall give them a hard stare"), Hagrid ("I shouldn't have said that"), Daffy ("Act natural!"), Ramsay ("Idiot sandwich? Not today"), Cartman ("Respect their authoritah!"), Batman ("GCPD"), Vader ("a disturbance in the speed limit") | `police-ahead.mp4` |
| 3. You've arrived | `arrived` | Default, Elmo, Hagrid ("I'll put the kettle on"), Bugs ("That's all, folks!"), Ramsay ("Finally! Beautiful"), Cartman | `arrived.mp4` |
| 4. Cute vs. evil | any | Split screen: Elmo against Vader on the same beat, and Pooh against Ramsay | not rendered yet |
| 5. Pick yours | none | The twelve faces. "Which one's riding with you?" Point people to the comments | none |

Post 2 is the strongest follow-up. The police alert is where the villains
are funniest, and it is a prompt people actually hear.

---

## Picture: what to generate in Runway

Generate the driving, not the characters. Each face on screen is its sticker
from `site/faces/`, composited onto the phone in the edit. That keeps every
cut visually on-brand with the site, costs four generations instead of twelve,
and avoids asking a video model for copyrighted likenesses, which it may
refuse or render off-model.

1. **Missed exit.** "Night, driver's point of view through a rain-streaked
   windshield on a lit highway. A green exit sign approaches on the right and
   passes; the car stays in its lane and the exit ramp slides away. A phone in
   a dashboard mount glows in the lower right. Cinematic, shallow focus,
   vertical 9:16." 10s. **This one shot is reused under every character.** The
   repetition is the joke: same mistake, different judge.
2. **Phone insert.** "Close-up of a smartphone in a car vent mount at night,
   screen solid bright green, soft dashboard glow, slight road vibration,
   9:16." 5s, loopable. Key the green and drop in the sticker plus the line as
   a caption.
3. **Driveway.** "Car pulls into a suburban driveway at dusk, porch light on,
   headlights switch off, 9:16." 5s.
4. **Rear-view police**, for post 2. "Rear-view mirror at night, red and blue
   light bokeh growing behind, 9:16." 5s.

I'll quote the credit cost from the Runway API before generating anything.

## Edit notes

- **Captions on every line.** Most views are muted. Put the words in a sticker
  speech bubble in Bagel Fat One, with the character's name as a tag in
  JetBrains Mono, both from the site.
- **Colour per character.** On each cut, wash the frame in that character's
  `--bg` from `site/characters.css` for four frames. It reads as a hard cut
  even with the sound off.
- **Link:** `backseatnav.com/?utm_source=tiktok&utm_campaign=missed-turn`, one
  `utm_campaign` per post, so Plausible shows which post drove installs rather
  than just views.
- **Pinned comment:** "Free. Tap a voice on backseatnav.com and it's in your Waze."
- **Takedown risk.** Vader (Disney) and Batman (Warner Bros.) are the likeliest
  to be muted or claimed. Cut A still lands without them, ending on Cartman, so
  keep that export ready.
