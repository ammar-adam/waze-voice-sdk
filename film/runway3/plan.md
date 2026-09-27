# THE GETAWAY

**A 30-second launch film for Backseat (backseatnav.com)**

> **Status:** as built. Masters: `film/out/getaway_16x9.mp4` (1920x1080) and `film/out/getaway_9x16.mp4` (1080x1920), 30.000 s, 720 frames at 24 fps, plus `_web` copies. Every Runway call is in `ledger.json`. Section 8 is the QA record.

## 1. The film in one breath

A premium heist-trailer played dead straight: night, pouring rain, neon, three friends in black balaclavas walk to a black sedan under a strobing red beacon. The one in the back has "got navigation". It is Elmo. The chain of looks, the peel-out, the sirens; Paddington promises a hard stare and the passenger delivers one; at a red light next to a patrol car Daffy yells "Act natural!" and all three rip their masks off into sunglasses, fake grins and an upside-down newspaper. The officer squints, and glides on. Darth Vader senses a disturbance in the speed limit; the needle eases down; all three bow in perfect sync on "Slow down." The backseat guy installs Bugs Bunny on backseatnav.com with a smirk. In the garage, everyone exhales. "We've arrived. That's all, folks!" Smash to the card on "That's".

Fixes against the rejected TOUGH CROWD: an attractive, stylish cast in a beautiful world; 30.0 s instead of 43 s; every shot has one job; reactions are big and physical (eyes wide, head turns, shrug, masks off, a synchronized bow, a smirk), and when faces are masked the acting is in the eyes and the bodies.

## 2. Cast, world, look (all generated people are fictional)

| | |
|---|---|
| Driver (front left, frame right from the bonnet) | Broad man, late 30s, black leather jacket and gloves; unmasked: short dark hair, trimmed beard. |
| Passenger (front right, frame left) | Woman, early 30s, black turtleneck and blazer; unmasked: sleek dark hair in a low bun. |
| Backseat guy (centre, leaning forward) | Lanky young man in a grey hoodie with the hood up. Holds the phone (never in a dash mount). |
| Car | One sleek, badgeless black sedan, black leather cabin, thin cool-white ambient strip. The spine of the film is the bonnet camera looking in through the rain-beaded windshield. |
| Patrol car | White and black, dark roof bar, no department name, number or emblem (generated door lettering is blurred). The officer wears a plain dark uniform. |
| Look | Night rain, magenta/cyan neon, deep blacks, 2.2:1 letterbox in 16:9, grain and vignette over every shot. |

Characters appear only as the site's sticker faces (`site/faces/<slug>.svg`, colours from `site/characters.css`) and in the site's own UI.

## 3. Beat sheet (as built; frames at 24 fps)

| Film (s) | Frames | Shot (source) | Picture | Sound |
|---|---|---|---|---|
| 0.000-2.000 | 0-48 | WALK, V01 src 2.9-4.9 (1x, slow push) | Low puddle angle, red beacon strobing, the three walk to the car, duffel swinging. | Tension drone (synth) + distant alarm in rain. |
| 2.000-2.750 | 48-66 | PHONE_UP, V02 take B src 0.00-0.75 | Backseat guy holds the phone up, proud; thumb to screen. | Tap on frame 59, drone cuts dead on frame 61. |
| 2.750-7.083 | 66-170 | RACK_A/B/C, V03 (1x, 3x focus pull, 1x) | Driver's eyes go wide; snap focus pull to the passenger's flat, withering look. | **elmo / start_drive_1** from frame 61 (2.542). Rain on the roof. |
| 7.083-9.042 | 170-217 | CHAIN1-3, V02 take A (three cuts, each tighter) | Driver turns to passenger; passenger turns to the back; big innocent shrug. | Silence, rain on the roof. |
| 9.042-9.667 | 217-232 | TYRE, V05 (720p) src 1.15 at 1.3x | Wheel spins, rooster tail of spray, the car tears off into neon. | Rev and screech, road, sirens rise. |
| 9.667-13.750 | 232-330 | BLUERED, V06 src 1.0-5.08 | Red/blue lights; driver glares back; backseat guy swipes; passenger's hard stare at the window. | Tap 236; **paddington / police_ahead** from 238 (9.917). |
| 13.750-17.917 | 330-430 | RED1 src 0-2.25 (1x, 330-384), RED2 src 2.25-5.25 (2.4x, 384-414), RED3 src 5.25 (414-430); V08 made from first and last frames | Red light, patrol car alongside, frozen masked eyes; on "Act natural" the masks come off, sunglasses, upside-down newspaper, fake grins. | Tap 334; **daffy-duck / police_ahead** from 336 (14.000); "Act" lands on the mask grab. |
| 17.917-18.667 | 430-448 | OFFICER, V09 src 2.0 | The officer squints. | Silence under rain. |
| 18.667-19.750 | 448-474 | GLIDE, V09 src 4.9 | He faces front and glides on. | Tap 446; **darth-vader / police_ahead** from 448 (18.667). |
| 19.750-22.833 | 474-548 | SPEEDO (built in Remotion: a digital cluster) | Needle eases 68 to 45 mph. | "I sense a disturbance in the speed limit." |
| 22.833-24.833 | 548-596 | NOD, V11 src 2.1 at 1.5x | All three bow in perfect sync: down on "Slow" (558), bottom on "down." (575), back up by the cut. | |
| 24.833-25.625 | 596-615 | PHONE (Remotion, the real site UI) | "Pick your navigator": thumb scrolls up past Darth Vader to Bugs Bunny, taps Install in Waze. | Tap on frame 609. |
| 25.625-26.083 | 615-626 | SMIRK, V12 src 2.75 | Phone-lit smirk. | |
| 26.083-27.458 | 626-659 | GARAGE, V13 src 2.35 | Garage, engine off, everyone exhales. | **bugs-bunny / arrived** from 626 (26.083); exhale in the gap before "That's". |
| 27.458-30.000 | 659-720 | END card | Who's in your backseat? / 12 faces (Bugs pops first and wiggles) / backseatnav.com (from the first frame) / Free. No account. One tap. / footer. | The cut lands on "That's" (1.37 s into the line); one music hit; rings out to silence on the last frame. |

Line placement rule: the tap SFX and the chip land 2 frames before each line; captions show the preset text exactly, the whole line readable at once and each word inking in on its spoken time.

## 4. Voice lines (verified three ways)

Text from `presets/<slug>.json`; audio from `packs/<slug>/audio/master/<phrase_id>.mp3`; transcribed with faster-whisper small.en (cross-checked with base.en and medium.en where small.en slipped); durations measured with ffprobe and an RMS speech detector on the trimmed, untreated file. Treatment (scripts/build_getaway_voices.py): silence trim below -45 dB at the ends only, phone band-limit (high-pass 250 Hz, Vader 180 Hz), short small-room echo, -16 LUFS. No voice is cut, sped up or pitch-shifted.

| slug / phrase_id | Preset text | Heard | Speech (trimmed) |
|---|---|---|---|
| elmo / start_drive_1 | Hi! Elmo is so happy to see you! Let's go! | Hi! Elmo is so happy to see you. Let's go! | 4.56 s (file 4.68) |
| paddington / police_ahead | Police ahead. I shall give them a hard stare. | Police ahead. I shall give them a hard stare. | 3.36 s (file 4.23) |
| daffy-duck / police_ahead | Police ahead! Act natural. Act natural! | Police ahead! Act natural! Act natural! | 3.78 s (file 3.88) |
| darth-vader / police_ahead | Police ahead. I sense a disturbance in the speed limit. Slow down. | small.en: "Gleece ahead. ..."; base.en and medium.en: "Police ahead. I sense a disturbance in the speed limit. Slow down." | 5.46 s (file 5.52) |
| bugs-bunny / arrived | We've arrived. That's all, folks! | We've arrived. That's all folks. | 2.48 s (file 2.54); "That's" at 1.37 s |

## 5. Claims and rights on screen

- "Free. No account." Site: "Free, and no account." "One tap." Site: "One tap and it's riding in your car", "free, one tap to install". The insert shows only our site; it never shows Waze's dialog (the real flow then asks for a Yes in Waze).
- 12 faces = the 12 voices in `site/voices.json`, in site order.
- "Independent project. Not affiliated with Waze or Google." is the site's footer.
- The insert copies the site UI (site/app.js, style.css): headline "Pick your navigator", card blurbs from voices.json, preview captions Starting a drive / Recalculating / Arrived, button "Install in Waze". The earlier film's toast ("... is riding with you") is not site copy and is not used.
- No Waze UI or logo, no Google marks, no character likeness in generated footage, no real police department names or logos. No em dashes on screen.

## 6. Production (see ledger.json for every call)

Stills: Gemini 3 Pro Image (gemini_image3_pro, 20 credits) for the cast and every frame that had to match; gen4_image (8) for the tyre. The first interior master defined the look; a red-light variant came back unmasked and became the canonical unmasked cast; every later frame references it. Video: Veo 3.1 Fast, 1080p 8 s (80 credits; 1080p only allows 8 s) except the tyre (720p 4 s, 40). Act natural used first and last frames (masked, then sunglasses). SFX: eleven_text_to_sound_v2 (1 credit/s); the drone, the tap and the music hit are synthesised in scripts/stage_getaway.py.

Pipeline: `build_getaway_voices.py` -> `stage_getaway.py` -> `finish_getaway.py` (renders both compositions muted with --concurrency=2, builds the mix with `mix_getaway.py` from the same config, checks line sync by cross-correlation, converts full-range yuvj420p to limited yuv420p, masters with `master_ad.py` to -14 LUFS / under -1 dBTP, writes web copies). Every tunable value lives in `film/src/getaway.config.ts`.

## 7. 9:16

The footage sits in a sharp, native 1080x1080 window (no upscaling of the main picture; the chain's punch-ins are at most 1.2x) from y 300 to 1380. Behind it, the whole 1080x1920 frame is filled with the same shot: a 9:16 column of the clip around the window's centre, scaled to cover, blurred 50 px and darkened to 55 % brightness, overscanned 1.12x so the blur never pulls in black. It is drawn from the same source on the same frame, so its motion matches the window exactly. The speedometer gets the same treatment; the phone insert and the end card are full-frame already. The chip rides the window's top edge (y >= 208) and the caption its bottom edge (ending by y 1500), over the fill and inside the safe zone. Crops are per shot (`f9` in the config); the rack pans with the focus pull so both faces stay in frame.

Lead review: the 16:9 master is approved as delivered; the 9:16 was re-rendered with the fill (`finish_getaway.py --only 9x16`, which leaves the 16:9 files byte-identical; checked by SHA-256). The re-rendered 9:16 passed the same QA: 720 frames and 30.000 s, -14.0 LUFS and -1.5 dBTP, every line on its frame (0 ms in the mix, 5 ms after AAC), no black, flash or frozen frames, and every large change a planned cut (plus the insert's whip-scroll); frames checked either side of every cut.

## 8. QA record (final masters)

**Delivery.** `getaway_16x9.mp4` 1920x1080 and `getaway_9x16.mp4` 1080x1920: H.264 High, yuv420p limited range (bt709), 24 fps, 720 frames, video and audio both 30.000 s, AAC 48 kHz (320k target). Web copies `getaway_*_web.mp4`: H.264 High about 8.5 Mbps, AAC 192k, faststart.

**Sound.** Both cuts -14.0 LUFS integrated, true peak -1.5 dBTP, LRA 5.7 LU (ebur128). Every line cross-correlates to its planned frame: 0 ms in the mix, 5 ms after AAC encoding (encoder priming, under a frame). faster-whisper medium.en on the final 16:9 master hears all five lines word for word. Section RMS: lines -13 to -17 dBFS; the chain silence -27, the squint silence -29, the nod tail -28 (the jokes' silences are rain only); the voice is the loudest element throughout (the peel-out, between lines, peaks at the same level). The drone cuts dead on Elmo's first frame. The music hit lands on the cut to the card at -12 dB so "That's all, folks!" stays on top, and rings out to the last frame.

**Picture, automated (both cuts).** No near-black frames, no single-frame flashes, no frozen or duplicated frames before the card (the walk originally ran at 0.8x and repeated every fifth frame in 9:16: fixed by running it at 1x; the speedometer's first frames barely moved: fixed with an ease-out needle). Every large frame change is a planned cut, except the phone insert's intended whip-scroll (9:16 frames 601-607).

**Picture, by eye.** Four frames around all 20 cuts in 16:9; a frame every 8 frames through the whole 16:9 master; key frames through every shot in 9:16; full-resolution checks of hands and faces at the phone grip, the shrug, the mask scramble, the newspaper, the officer, the bow and the garage. Found and fixed: a jump cut in the act-natural scramble (the passenger went from masked to unmasked across a cut: the 2.4x scramble now runs straight into the hold); the rack shot's 9:16 crop lost the passenger once focus pulled to her (it now pans with the pull); the nod cut away while all three were still bowed (1.5x, back up by the cut); the Vader caption wrapped onto the picture in 16:9 (wider caption); the 9:16 end card's last row of faces collided with the URL (tighter grid). Generated text is handled: the patrol car's door lettering is blurred on every frame it shows; the neon glyphs behind the interior shots are softened by a depth band; the upside-down newspaper's headline strip is softened (its photo reads upside down; its print is unreadable); the walk's far-left sign is blurred; V06's backseat passenger, who vanishes after src 5.6, and V13's face drift after src 4.0 are never used.

**Copy.** Captions equal the preset text character for character (automated check). No em or en dashes in the Remotion source or the line data. End card: "Who's in your backseat?", the 12 faces and names in site order, backseatnav.com on the card's first frame, "Free. No account. One tap.", the footer; complete from frame 672 and held 2.0 s.

**Known and accepted.** The driver's black gloves are gone once the masks come off (V08 onward, including the nod and the garage): Veo dropped them in the unmasking take and the budget did not allow regenerating three shots. The officer wears a generic cap badge and shoulder patch (no department, no readable text). The tyre shot is a 720p source (motion-blurred spray). The speedometer is a built digital cluster, not generated footage.

## 9. Budget

API balance 1371 before, 228 after: 1143 credits spent, and the ledger total agrees. Veo 3.1 Fast 840 (10 takes at 1080p/8 s plus the 720p/4 s tyre; one chain retake, rejected, but its first 0.75 s became the phone-up beat), Gemini stills 260 (13 frames), gen4_image 8, SFX 35. That is 143 over the ~1000 aim: the reference-consistent Gemini stills cost more than planned, and the head-turn chain retake was spent as a priority beat.
