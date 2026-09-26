# TOUGH CROWD

**A 42-second launch film for Backseat (backseatnav.com)**
Director's plan for the production agent. Everything needed to generate the footage and cut the film is in this file, `shots.json`, `lines.json` and `keyframes/`.

---

## 1. The film in one breath

**Logline.** His friend gets hold of his phone and throws every famous voice at the most unimpressable man alive. He won't crack. Then she gets out of the truck.

**The story.** A huge, bearded, stone-faced man drives an old powder-blue pickup. His friend in the passenger seat has his phone, and she has discovered Backseat. She installs Elmo. He does not blink. Stuck in traffic, she goes through voice after voice, faster and faster (Gordon Ramsay, Winnie the Pooh, Eric Cartman, Darth Vader), each one reacting to the same jam in its own way, while she falls apart laughing and he stares ahead like a statue. Vader gets one tiny twitch out of him. He misses his exit, Ramsay calls him a donkey, and he gives her the slowest, flattest look in cinema history. They arrive; Bugs Bunny says "That's all, folks!" and she hops out. It sounds like the end of the film. It isn't. Alone, he checks that nobody is watching, picks up his phone, and quietly installs Elmo for himself. "Here we go! Elmo loves you!" And the man who could not be cracked breaks into the biggest, warmest grin. Cut to the 12 faces: *Who's in your backseat?*

**One idea:** nobody is too tough for a voice in the backseat. Every beat serves it: the game (can she crack him?), the escalation (more voices, faster cuts, a twitch), the peak (the donkey stare), the fake ending, and the payoff (he's secretly one of us). The call to action is earned because the viewer has just watched the hardest possible customer convert.

### Why it spreads
- **The hook, 0 to 1.5s.** Frame 1 is already a joke: a giant deadpan trucker, a gleeful friend holding his phone, and the caption "he said i could pick the GPS voice". At 0.29s Elmo squeaks "Hi!" at this man. Works with the sound off (caption, chip, face) and lands a laugh inside one second with it on.
- **An open loop.** "Will he crack?" is a question the viewer has to stay to answer. The same situation (traffic) played through four voices is a sketch structure: repetition with variation, cuts getting shorter (4.3s, 2.9s, 2.1s), then one long hold on the first twitch.
- **The shareable moment.** "You missed it, you donkey!" into his slow head turn. It's a sub-5-second clip people will screenshot, stitch and send.
- **A fake ending.** "That's all, folks!" and she leaves. Silence. The viewer who is about to swipe is caught by the twist.
- **A payoff with heart.** The tough guy secretly choosing Elmo is wholesome, surprising and relatable ("this is my dad", "this is my boyfriend"): tag-a-friend fuel.
- **Rewatch loop.** The last line ("Elmo loves you!") rhymes with the first ("Hi! Elmo is so happy to see you!"). On a looping platform the end card flows back into the hook, and the second watch reads differently: he always wanted Elmo.
- **Comment bait built in.** She looks to the lens after Pooh: "what would crack him?" invites the viewer to name their voice, which is the product.
- **Product truth on screen.** Every word a character says is a real line from its live pack, playing on real Waze events (start of drive, traffic, reroute, arrival). The site itself appears in the payoff insert and turns into the end card.

### Formats
- **16:9 master**, 1920x1080, 24 fps, 42.0s (1008 frames). For X, LinkedIn, YouTube.
- **9:16 cut**, 1080x1920, same timeline, same audio. For TikTok, Reels, Shorts. Every two-shot becomes a **stacked split** (her half on top, his half below, each a native-resolution 960x853 crop scaled x1.125; nothing mushy). Every close-up and exterior is a 608x1080 centre crop on the subject (x1.776). Crop centres per shot are in `shots.json` (`crop_9x16`).
- 9:16 safe zone for all graphics: x 60 to 900, y 200 to 1500 (keep clear of the TikTok/Reels right rail and bottom caption area).

---

## 2. Cast, world, look (all generated people are fictional)

| | |
|---|---|
| **The driver** | A huge broad-shouldered man, 40s, thick black beard, navy cap, faded red flannel. Deadpan. Never touches the phone while the truck is moving (he's parked in the payoff). |
| **The friend** | Early 30s, curly dark hair, freckles, mustard-yellow corduroy jacket (the brand yellow, on the agent of chaos). Holds his phone the whole ride. |
| **The truck** | Faded powder-blue 1970s pickup, white roof, rust streaks, bench seat, painted blue metal inside. |
| **Camera** | A hood-mounted two-shot through the windshield (the spine of the film: it returns at the start, the jam, the donkey, the arrival and, with the empty seat, the payoff), plus passenger-seat close-ups of him (always looking frame right) and a driver-seat close-up of her. |
| **Light** | Golden morning (start), hot midday (jam), bright afternoon (highway, town, alone). Kodak Portra warmth, gentle grain. |
| **Grade** | One campaign grade over everything: blacks slightly lifted warm, highlights creamy, saturation 0.95, the yellow jacket protected. Match S02's golden flare as the warmest point. |

Characters never appear in the footage. They are voices, plus the site's sticker faces composited in the edit (`site/faces/<slug>.svg`, colours from `site/characters.css`).

---

## 3. Beat sheet (24 fps; film times in seconds; frame = time x 24)

Voice files: `packs/<slug>/audio/master/<phrase_id>.mp3`. Durations measured with ffprobe; text verified against `presets/<slug>.json` and transcribed with faster-whisper (details in section 6 and `lines.json`, which also holds word-level timings for the captions). A line is never cut, sped up or pitch-shifted.

| Beat | Film in to out | Shot (source window) | Picture | Voice line (slug / phrase_id / exact text / duration / placed at) | Sound | On-screen text |
|---|---|---|---|---|---|---|
| **B1 HOOK** | 0.00 to 1.50 | S01 (src 0.25 to 1.75) | Hood two-shot, parked on a leafy street, morning. She holds his phone up, grinning; taps it. He stares ahead, dead. | **elmo / start_drive_1** / "Hi! Elmo is so happy to see you! Let's go!" / 4.90s / 0.29 to 5.19 | Tap SFX 0.21. Idle engine, birds. No music. | Hook caption from frame 0: **he said i could pick the GPS voice**. Elmo chip slaps in at 0.21. Line caption word by word. |
| **B2** | 1.50 to 6.00 | S02 (0.90 to 5.40) | Golden close-up of him through the whole Elmo line. One slow blink. Line ends; 0.4s of nothing; he exhales through his nose and turns the wheel, pulling out. | (Elmo continues, ends 5.19) | Engine note rises on the pull-out. | Chip stays until 5.4, then pops off. |
| **B3** | 6.00 to 7.25 | S03 (2.00 to 3.25) | Telephoto from behind: the truck dead still in a jam to the horizon, heat haze. | none | Hard cut to traffic: idling engines, one distant horn. | none |
| **B4 Voice 2** | 7.25 to 11.50 | S04 (0.90 to 5.15) | Hood two-shot in the jam. She taps, then covers a snort. He does not react at all. | **gordon-ramsay / traffic_ahead** / "Traffic ahead. It's moving slower than your risotto." / 3.84s / 7.42 to 11.26 | Tap 7.34. Cab idle. | Ramsay chip; caption. |
| **B5 Voice 3** | 11.50 to 14.40 | S05 (0.50 to 3.40) | Her close-up: two taps, hopeful eyes at him; nothing; her eyes slide to the lens. | **pooh / traffic_ahead** / "Traffic ahead. Oh, bother." / 2.68s / 11.60 to 14.28 | Tap 11.52. | Pooh chip (name: Winnie the Pooh); caption. |
| **B6 Voice 4** | 14.40 to 16.50 | S06 window 1 (0.00 to 2.10) | His close-up in traffic. A statue. One blink. | **eric-cartman / traffic_ahead** / "Traffic ahead. Screw this traffic!" / 1.85s / 14.48 to 16.33 | Tap 14.40 (her hand is off screen). | Cartman chip; caption. |
| **B7 Voice 5** | 16.50 to 20.75 | S06 window 2 (2.10 to 6.35), punched in 112% | Tighter on him. After "disturbing": the corner of his mouth twitches for an instant; he clamps it down. Hold. | **darth-vader / traffic_ahead** / "Traffic ahead. I find this delay disturbing." / 3.69s / 16.58 to 20.27 | Tap 16.50. After the line, total silence except the idle: let the twitch breathe. | Vader chip; caption. |
| **B8** | 20.75 to 22.00 | S08 (1.00 to 2.25) | Aerial: the truck cruises straight past the exit ramp. | Ramsay pre-laps from 21.30 (next row) | Whoosh as the ramp passes. | Ramsay chip slaps in at 21.22 over the aerial. |
| **B9 THE STARE** | 22.00 to 27.00 | S09 = `tests/T2` (0.10 to 5.10), already generated | Hood two-shot on the highway. She is crying with laughter. At 24.57 he slowly turns his head to her: a long, flat, unimpressed stare. Hold. | **gordon-ramsay / reroute_chime** / "You missed it, you donkey!" / 2.42s / 21.30 to 23.72 | Road noise. Nothing else during the stare. | Caption; chip off at 24.0 so the stare plays clean. |
| **B10 FAKE END** | 27.00 to 30.50 | S10 (0.50 to 4.00) | The truck stops at a small-town curb. She salutes him, still laughing, and hops out. Door shuts. Empty seat. | **bugs-bunny / arrived** / "We've arrived. That's all, folks!" / 2.67s / 27.15 to 29.82 | Street air; door thunk on the visible shut (~30.2). | Bugs chip; caption. |
| **B11 ALONE** | 30.50 to 33.00 | S11 = `tests/T1` (0.00 to 2.50), already generated | Same hood framing, empty passenger seat. He glances left, right. Nobody. He looks down at his phone. | none | Near silence: room tone, one bird. The quiet is the twist. | none |
| **B12 THE CHOICE** | 33.00 to 35.00 | S12, Remotion insert (no generation) | His phone screen, full frame: the backseatnav.com voice grid in the site's sticker style. A thumb hovers over Darth Vader... slides past... taps **Install in Waze** under Elmo. | **elmo / start_drive_9** / "Here we go! Elmo loves you!" / 2.98s / 34.45 to 37.43 | Tap 33.95. | Site UI (see section 4). No chip here: the screen is the chip. |
| **B13 PAYOFF** | 35.00 to 37.60 | S13 (2.40 to 5.00), new take | Back on him, parked, phone low. On "Elmo loves you!" the grin blooms: huge, warm, bashful; he shakes his head at himself. | (Elmo continues, ends 37.43) | **First music of the film**: `film/runway/score.wav` from offset 12.00s, entering at 35.10 so its swell (score 12.5s) lands at 35.6 on the grin. | Elmo chip; caption. |
| **B14 END CARD** | 37.60 to 42.00 | Remotion | See section 4. | none | Score continues (offset 14.5 to 18.9, already fading), out at 42.0. One tap SFX on the URL. | Who's in your backseat? / 12 faces / backseatnav.com / Free. No account. One tap. / Independent project. Not affiliated with Waze or Google. |

**Fallback timing for B13** (if S13 fails twice): use T1 src 6.00 to 8.00 (frames 144 to 191, approved grin, phone lowered). B13 becomes 35.00 to 37.00, the Elmo line tail carries 0.43s into the end card, end card 37.00 to 41.40, film 41.4s.

**Timing rule for every line:** the chip, the tap SFX and her visible thumb tap all land on the same frame, 0.08s before the line starts. When a real take puts the tap on a different frame, move the line with it; never move the tap.

---

## 4. How characters appear (graphics, all in the site's style)

Fonts: Bagel Fat One (names, titles), Bricolage Grotesque 700 to 800 (captions, body), JetBrains Mono (URL detail). Brand yellow `#ffd23f`, ink `#15172b`. Sticker language: thick ink outline (6px at 1080p), hard offset shadow (8px down-right, ink, no blur), slight rotation (-2 to 2 degrees).

- **Voice chip** (the well-received version): a yellow sticker with the character's face badge (the `site/faces/<slug>.svg` face on its `--bg` colour in a circle with an ink ring) and the name in Bagel Fat One. No "Navigator:" label, no thin lower-thirds. It slaps in over 5 frames (scale 0 to 1.12 to 1.0, rotation settles), synced to the tap SFX, and pops off in 4 frames. 16:9: bottom-left, 64px margins, face 104px, name 48px. 9:16: top-left inside the safe zone (x 60, y 220), face 120px.
- **Line captions** (needed for sound-off autoplay on X and in feeds): the exact preset text, in Bricolage Grotesque 800, ink on a white sticker with an ink outline, words appearing on their spoken timings (word timings in `lines.json`). 16:9: bottom centre, max 2 lines, 56px. 9:16: centre of the lower half (y about 1300), 64px, max 3 lines. The caption shows the preset text exactly as written (for example "Oh, bother." and "That's all, folks!").
- **Hook caption** (0.00 to 1.50): "he said i could pick the GPS voice", lower case, Bricolage Grotesque 800, ink on white sticker. 16:9: top centre. 9:16: straddling the seam of the split at y 960.
- **S12 phone insert** (33.00 to 35.00): full-frame yellow background, a phone mockup in ink outline filling 80% of the height (in 9:16 it fills the frame). On the screen: the site's "Pick your navigator" grid in the real site styling (face cards on their character colours). 0.0 to 0.6s: a thumb-tap ring hovers over Darth Vader. 0.6 to 0.9s: it slides to Elmo. 0.95s: tap; the **Install in Waze** button under Elmo depresses. 1.2 to 2.0s: a sticker toast pops: **Elmo is riding with you**. (The real flow is: tap Install in Waze, then Waze asks to add the voice and you say yes. We show only our own site, never Waze's interface or logo.)
- **End card** (37.60 to 42.00), yellow background, grain off:
  - 0.00: **Who's in your backseat?** (Bagel Fat One, ink, sticker shadow).
  - 0.35 onward: the 12 face stickers pop in, 2 frames apart (16:9: 2 rows of 6; 9:16: 4 rows of 3). Elmo pops last and gives a single 6-frame wiggle.
  - 1.30: **backseatnav.com** in a big ink pill with yellow text (JetBrains Mono or Bagel), tap SFX.
  - 1.60: **Free. No account. One tap.** (Bricolage 700).
  - Footer from 0.00, small: **Independent project. Not affiliated with Waze or Google.**
  - Hold the complete card at least 2.4s. The 12 faces, in site order: bugs-bunny, cookie-monster, daffy-duck, elmo, tigger, pooh, paddington, hagrid, darth-vader, batman, gordon-ramsay, eric-cartman.

No em dashes anywhere on screen. No Waze logo or UI, no Google marks, no character imagery beyond the site's own sticker faces.

---

## 5. Sound

- **Voices:** from the masters via `scripts/build_ad_voices.py` (update its `LINES` dict to the 8 lines above). Use the `_phone` version (band-limited dash-speaker treatment, -16 LUFS) so the voices sound like they come out of the phone in the cab, but ride the high-pass at 180 Hz instead of 250 Hz for Vader so his low end survives.
- **No music until the payoff.** Deadpan comedy lives in silence; the music arriving on the grin is the emotional turn.
- **Ambience:** morning street (B1 to B2), cab idle in traffic (B3 to B7; generate `cab_idle`, fallback `film/runway/sfx_truck.wav`), road noise (B8 to B9), town street plus door thunk (B10), room tone only (B11), then score.
- **Tap SFX** on every voice switch (the rhythm of the montage).
- **Master:** `scripts/master_ad.py` to -14 LUFS integrated, true peak at most -1 dBTP. Voices sit 6 to 8 dB above ambience.

---

## 6. Fact check (done in pre-production)

**Every spoken line** was checked three ways: text read from `presets/<slug>.json`; audio transcribed from `packs/<slug>/audio/master/<phrase_id>.mp3` with faster-whisper small.en; duration and loudness measured (ffprobe, ebur128). All are 44.1 kHz mono, about -16 LUFS integrated, true peak -1.6 to -3.3 dBFS, no clipping, clean starts and ends.

| slug / phrase_id | Preset text | Transcript | Duration |
|---|---|---|---|
| elmo / start_drive_1 | Hi! Elmo is so happy to see you! Let's go! | Hi! Elmo is so happy to see you! Let's go! | 4.90 s |
| gordon-ramsay / traffic_ahead | Traffic ahead. It's moving slower than your risotto. | traffic ahead it's moving slower than your risotto | 3.84 s |
| pooh / traffic_ahead | Traffic ahead. Oh, bother. | "Traffic ahead. Who bother?" in context; the isolated tail from 1.1s transcribes as "Oh, bother." in all three models (tiny, base, small). The "d" of "ahead" runs into "Oh". Verified. | 2.68 s |
| eric-cartman / traffic_ahead | Traffic ahead. Screw this traffic! | Traffic ahead. Screw this traffic. | 1.85 s |
| darth-vader / traffic_ahead | Traffic ahead. I find this delay disturbing. | Traffic ahead. I find this delay disturbing. | 3.69 s |
| gordon-ramsay / reroute_chime | You missed it, you donkey! | You missed it! You donkey! | 2.42 s |
| bugs-bunny / arrived | We've arrived. That's all, folks! | We've arrived. That's all folks. | 2.67 s |
| elmo / start_drive_9 | Here we go! Elmo loves you! | Here we go! Elmo loves you! | 2.98 s |

Alternates, all verified the same way (`lines.json`, `voice_check.json`): batman / traffic_ahead (4.11 s), hagrid / reroute_chime (3.74 s), eric-cartman / arrived (1.85 s), elmo / arrived (3.57 s), plus all 12 characters' traffic_ahead, reroute_chime and arrived.

**Every claim on screen** is checked against the live site copy (`site/index.html`, `site/install.html`, `site/voices.json`):
- "Free. No account." The site says "Free, and no account."
- "One tap." The site's headline says "One tap and it's riding in your car" and "free, one tap to install". (The install page says "Usually one tap", because Waze then asks for a Yes; our insert shows only the tap on our site, never Waze's dialog.)
- 12 faces: `site/voices.json` lists exactly 12 voices, matching the 12 files in `site/faces/`.
- "Independent project. Not affiliated with Waze or Google." is the site's own footer line.
- The film shows only the site's own UI. Saying "Waze" in text (Install in Waze) is how the site describes itself; no Waze logo, UI or colours.

**Contextual truth:** each line plays on the event it was written for (start of drive, traffic, missed turn, arrival). Switching voices mid-drive is the passenger installing a new pack from the site, which is what the product does.

**No copyrighted characters or real people in generated footage:** every prompt describes only the two fictional actors, the truck and places. Characters appear only as audio and as the site's own sticker faces.

---

## 7. Keyframes (in `keyframes/`, all 1920x1080, all checked by eye)

| File | Used for | Verdict |
|---|---|---|
| KF01b_hook_twoshot.png | S01 | Approved. Hood two-shot, her grin, his deadpan, clean hands. Her star-glitter freckles are a character detail and stay consistent. |
| KF02b_driver_cu_start.png | S02 | Approved. The most beautiful frame: golden flare, correct screen direction (looks frame right like KF06b). |
| KF03c_ext_jam_rear.png | S03 | Approved with a fix: garbled plate text, blur or crop in the edit (noted in shots.json). |
| KF04c_twoshot_traffic.png | S04 | Approved (third try; KF04 and KF04b had a smudge under her lip). |
| KF05_passenger_cu_traffic.png | S05 | Approved. |
| KF06b_driver_cu_traffic.png | S06 | Approved (KF06 had a snarl and looked at the lens). |
| KF07b_ext_missed_exit.png | S08 | Approved (KF07 had a gantry sign with garbled text). |
| KF08_twoshot_highway.png | S09 (done, T2) | Approved. |
| KF09_twoshot_arrival.png | S10 | Approved. |
| KF10b_alone_twoshot.png | S11 (done, T1), S13 | Approved. Empty seat, same framing as the film's spine. |
| KF13_T1_lastframe.png | Reference only | Last frame of T1 (the grin), for continuity checks on S13. |
| KF01, KF02, KF03, KF03b, KF03d, KF04, KF04b, KF06, KF07, KF10 | Rejected or superseded, kept for the record | Reasons: a mirror hanging on the wrong window, wrong screen direction, a visible wrong driver, garbled text, facial smudges, a snarl. |
| ref_driver.png, ref_passenger.png, ref_passenger_face.png, ref_truck.png | Reference crops used for consistency | |

Test clips in `tests/`: **T1** (payoff, 8s) and **T2** (donkey, 8s), both Veo 3.1 Fast 1080p. Both are production footage now: T2 is S09; T1 gives S11 and the S13 fallback. Contact sheets: `tests/T1_detail.jpg`, `tests/T1_cutpoints.jpg`, `tests/T2_detail.jpg`.

**Reused from film/runway/**: `score.wav` (payoff swell) and `sfx_truck.wav` / `sfx_dusk.wav` as ambience fallbacks. None of the 7 old clips are used: they star four different drivers in four different vehicles, and one continuous story with one cast is the whole point of this film.

---

## 8. Production order

1. Read `shots.json`. Keep the Runway key in a shell environment variable only; append every call to `ledger.json`.
2. Generate in order of risk: **S06, S13, S01, S04, S05, S10, S02, S08, S03**, then the SFX. Review each clip against the QA list before generating the next; retake only for a real failure (max two takes, then the fallback).
3. Export the voices (section 5), build the chips, captions, S12 insert and end card in Remotion (reuse the patterns in `film/src/Ad.tsx` and `config.ts`: a new composition, e.g. `ToughCrowd` 16:9 and `ToughCrowdVertical` 9:16, both reading one shared timeline config).
4. Cut to the beat sheet. Then run the QA checklist on both renders. Master to -14 LUFS.

---

## 9. QA checklist (the production agent must pass every item before delivering)

**Story and timing**
- [ ] Watch both cuts start to finish, sound on, then again sound off. With the sound off the whole story still reads (hook caption, chips, captions, the stare, the grin).
- [ ] Each line lands on the beat in section 3 to within 2 frames; every tap SFX, visible thumb tap and chip slap share a frame.
- [ ] The Vader twitch lands 0.2 to 0.5s after the line ends; the donkey stare starts after "donkey"; the grin blooms on "Elmo loves you!".
- [ ] Runtime 42.0s (or 41.4s on the S13 fallback). The end card holds complete for at least 2.4s.

**Frame-by-frame at every cut** (step through 6 frames either side of every cut, in both aspect ratios)
- [ ] No flash frames, no black frames, no frozen or duplicated frames, no half-dissolves left behind.
- [ ] Faces: identity holds within and across shots (beard, cap, freckles, jacket); no morphing, no melting teeth, no extra eyes or eyebrows. Discard any frame range where a face drifts (T2 after src 5.2 is known bad).
- [ ] Hands: five fingers, no fused fingers or hands merging with the wheel or phone; the phone never passes through a hand.
- [ ] Continuity: the driver is always behind the wheel on the correct side (frame right in hood shots; in close-ups he looks frame right); the passenger is always frame left; the seat is empty after B10; the phone is in her hands until B10 and his after; no phone ever goes to an ear.
- [ ] Car interior: the steering wheel stays one wheel with a consistent number of spokes, the mirror stays put, no doors opening by themselves, background motion matches parked vs moving.
- [ ] Text artifacts: no readable AI text anywhere (plates, signs, screens). S03's plate is blurred or out of frame on every frame of both cuts.
- [ ] No character likeness, logo, Waze UI or Google mark anywhere in the generated footage.

**Graphics and copy**
- [ ] Every caption matches `presets/<slug>.json` character for character.
- [ ] No em dashes anywhere on screen. Search the Remotion source for the em dash character and find zero.
- [ ] Chips and captions sit inside the 9:16 safe zone (x 60 to 900, y 200 to 1500) and never cover a face.
- [ ] End card: 12 faces, the right names in the right colours, backseatnav.com spelled exactly, footer present.

**Audio**
- [ ] Master at -14 LUFS integrated (plus or minus 0.5), true peak at most -1 dBTP, checked with ebur128 on both renders.
- [ ] Voices clear over ambience, never clipped, never cut short, never sped up; no voice overlaps another.
- [ ] No music before 35.10; the score swell lands on the grin; clean fade to silence at the end.
- [ ] Audio and picture in sync at the last frame (no drift): check the door thunk and the final tap.

**Delivery**
- [ ] Renders: `ToughCrowd_16x9.mp4` (1920x1080) and `ToughCrowd_9x16.mp4` (1080x1920), H.264 high profile, 24 fps, AAC 320 kbps, yuv420p.
- [ ] Pull a still at 0.0s from each cut and check it works as the thumbnail and the first frame (it's the hook).
- [ ] Ledger total and the real balance agree; no key in any file, commit or log.

---

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Veo 1080p only generates 8s clips (80 credits each), so every shot costs the same. | Each 8s take is planned to serve its beat with room to slide; S06 serves two beats. Exteriors have gen4_turbo fallbacks at 15 credits. |
| Micro-performances (the twitch, the grin) may be too big or too small. | They get first call on the reserve, S13 has an approved fallback already in hand (T1), and the edit can punch in to sell a small twitch. |
| Identity drift late in an 8s clip (seen in T2 after 5.2s). | Edit windows sit in the first 5 to 6s wherever possible; the QA list demands frame checks at every cut. |
| Veo interprets a phone as a phone call. | Prompts say the phone stays low and never rises; negativePrompt includes it; T1 frames 64 to 140 are banned. |
| Garbled AI text (license plate on S03). | Blur patch or crop, verified per frame in both cuts. |
| CDN download resets. | Use curl with retries; re-fetch the output URL from GET /v1/tasks/{id}. |
| The fake-out might read as the real end and lose viewers. | No black frame: the cut to the empty seat is immediate and the silence is short (2.5s) before the phone insert. |
| Safety optics (phone use while driving). | The driver never touches the phone while moving; the passenger operates it, and he's parked in the payoff. |

---

## 11. Budget

| | Credits |
|---|---|
| Allowance | 1500 |
| Spent in pre-production (22 stills 54, test T1 80, test T2 80) | 214 |
| **Balance at handoff** | **1286** |
| Must-have production: 9 Veo clips (S01, S02, S03, S04, S05, S06, S08, S10, S13) at 80 each | 720 |
| Must-have SFX (eleven_text_to_sound_v2, 14 s at 1 per second) | 14 |
| Retake reserve (15.6% of balance) | 200 |
| Nice-to-have: N1 second take of S01, N2 second take of S06 | 160 |
| **Planned total** | **1094** |
| Unallocated buffer | 192 |

Full details, prompts, edit windows, crops and fallbacks per shot: `shots.json`. Every call so far: `ledger.json`.
