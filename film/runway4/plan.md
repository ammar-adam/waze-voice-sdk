# THE GETAWAY v2: the action-chase revision

**A 30-second launch film for Backseat (backseatnav.com). 1920x1080 full frame, 24 fps, 720 frames.**

> **Status: pre-production complete. Production is now "drop in the clips and render".** Seven NEW action shots have approved first frames (`stills_sheet.png`). The edit, voices, captions and mix are built. A timing preview with the stills standing in (`film/out/getaway_v2_preview.mp4`) renders from the real config. Image-to-video for the NEW shots has **not** been run: it needs the owner's go-ahead in this environment (see section 9). Every Runway call is in `ledger.json`. The first cut is documented in `film/runway3/plan.md`.

## 1. What changed, and why (owner feedback on the first cut)

| Feedback | Answer in v2 |
|---|---|
| 16:9 only, full frame, no letterbox | The 2.2:1 bars are gone. The 9:16 composition and its fill are removed: `Root.tsx` registers only `Getaway`, at 1920x1080. |
| Captions look ugly (white boxes) | No box or card. The text is bold white Bricolage 800 at 58 px, with a soft dark outline (`-webkit-text-stroke` painted under the fill) and a two-layer drop shadow. The whole line is readable at once, and each word inks in (from 45 % to 100 %) on its spoken time. The sticker chip (face and name) is kept. |
| Must feel like an action movie, not cut-cut-cut inside the car | From 10.1 s to 20.1 s the film is an exterior chase: the launch, a drift, a lens inches off the asphalt, a near miss with sparks, a blown turn and a handbrake 180, and an alley escape. The interior appears only where the joke lives: Elmo, the head-turn chain and "act natural". |
| Sprinting, not walking; chased by police | The N1 sprint and dive replaces the walk. Patrol cars appear in N2 to N7. |
| A new navigator on every hard turn | Cookie's chip slaps in mid-drift, Gordon's on the handbrake yank, Daffy's as the car swings out of the alley, and Bugs' as the engine dies in the garage. |
| Navigators: Elmo, Cookie Monster, Gordon Ramsay, Daffy Duck, Bugs Bunny | Exactly these five. There is no Vader, Batman or Paddington. Cartman is not needed, because five voices fit with room to breathe. The Vader speedometer and the phone insert are cut. |

## 2. Beat sheet (to the frame, 24 fps)

This is the approved structure, refined to the real line lengths. Cookie needs 4.14 s of speech, so the chase beats run longer than in the sketch. The head-turn chain keeps its first-cut length of 1.96 s. Everything still lands in exactly 30.000 s.

| Film (s) | Frames | Beat | Picture | Voice (start frame; speech length) |
|---|---|---|---|---|
| 0.000-3.000 | 0-72 | Cold open | SPRINT_A (48 frames): alarm, rain, red beacon; the three sprint from the doorway, water exploding under their feet. SPRINT_B (24): the same angle, later; they dive in and three doors slam (the last slam is 17 frames in). | None: drone, plus the alarm in the rain |
| 3.000-8.167 | 72-196 | "I've got navigation" | PHONE_UP (18): the phone goes up and the thumb lands at frame 83. RACK_A/B/C (55+18+33): the driver's eyes go wide, then a 3x focus pull to the passenger's flat look. | **Elmo** from frame 85 (3.542 s): "Hi! Elmo is so happy to see you! Let's go!" Speech 4.62 s; "go!" ends at 190. The tap and the chip land at 83. The drone cuts dead on 85. |
| 8.167-10.125 | 196-243 | The look chain | CHAIN1/2/3 (15+15+17): driver to passenger, passenger to the back, backseat shrug. Each cut is tighter. | Silence (rain on the roof) |
| 10.125-12.125 | 243-291 | Launch | TYRE (12): wheel spin, smoke and spray, with the rev building under the shrug. LAUNCH (36): the sedan tears off the kerb at the camera, fishtailing, while two patrol cars skid round the corner behind it. Sirens erupt. | None (engine, screech, sirens) |
| 12.125-16.375 | 291-393 | First corner: Cookie | DRIFT (36): fully sideways through the flooded intersection. LOWTRACK (30): a hand's width off the asphalt, with a patrol car at the bumper. NEARMISS (36): through the gap past the truck, while the patrol car scrapes the barrier in a fountain of sparks. | **Cookie Monster** from 301 (12.542 s): "Police ahead! Me behave! Me hide cookies!" The chip slaps in at 299, 8 frames into the drift. Speech 4.14 s, ending at 400. |
| 16.375-18.625 | 393-447 | Blown turn: Gordon | OVERSHOOT (54): from overhead, they blow past the turn, pull a handbrake 180 in a ring of smoke, and launch back the way they came as the patrol cars brake too late. | **Gordon Ramsay** from 405 (16.875 s): "You missed it, you donkey!" The chip lands at 403, on the yank. Speech 2.24 s, ending at 459. |
| 18.625-25.625 | 447-615 | Alley, red light: Daffy | ALLEY (36): barrelling down the alley at the lens as the cops overshoot the mouth; the car swings out at the far end. RED1 (42): masked at the red light, the cruiser alongside. RED2 (30, at 2.4x): masks off, sunglasses on. RED3 (16): acting natural with the upside-down newspaper. OFFICER (18): he squints. GLIDE (26): he glides on. | **Daffy Duck** from 477 (19.875 s): "Police ahead! Act natural. Act natural!" The chip lands at 475, on the alley exit. Speech 3.83 s. "Act" lands at 506, which is V08 src 1.46: the same frame of the mask grab as in the first cut. The caption leaves at 577. |
| 25.625-27.458 | 615-659 | Arrival: Bugs | SMIRK (11): the phone-lit smirk. GARAGE (33): engine off, everyone exhales. | **Bugs Bunny** from 626 (26.083 s): "We've arrived. That's all, folks!" Speech 2.50 s. The exhale sits in the gap (647). |
| 27.458-30.000 | 659-720 | End card | Smash cut on "That's" (1.37 s into the line) to: Who's in your backseat? / 12 faces (Bugs pops first) / backseatnav.com / Free. No account. One tap. / footer. | The music hit lands on the cut and rings out to silence on frame 720. |

Line rules:
- Every chip lands 2 frames before its line and leaves as the next chip lands (Cookie's leaves at 403, Gordon's at 475).
- No two voices overlap. The gap from Cookie to Gordon is 5 frames; from Gordon to Daffy it is 18.
- Only Elmo is tapped in. The other navigators arrive with the turns.

## 3. Shot list

REUSE sources are the first cut's takes (in `film/runway3/takes/`, staged as `public/ga/clips/<id>.mp4`). Source ranges are in seconds.

| # | Shot | Film frames | Type | Source / range | Notes |
|---|---|---|---|---|---|
| 1 | SPRINT_A | 0-48 | **NEW N1** | N1 src 0.5-2.5 (set on delivery) | Sprint to the car. |
| 2 | SPRINT_B | 48-72 | **NEW N1** | N1 src about 4.5-5.5 (set on delivery) | Dive in, doors slam. Same take, jumping forward in time. |
| 3 | PHONE_UP | 72-90 | REUSE | V02_chain_b src 0.00-0.75 | 1.12 crop; neon band softened. |
| 4 | RACK_A | 90-145 | REUSE | V03_rack_a src 0.72-3.01 | |
| 5 | RACK_B | 145-163 | REUSE | V03_rack_a src 3.00-5.25 at 3x | Focus pull. |
| 6 | RACK_C | 163-196 | REUSE | V03_rack_a src 5.25-6.63 | |
| 7 | CHAIN1-3 | 196-243 | REUSE | V02_chain_a src 1.55-2.17, 4.55-5.17, 6.45-7.16 | Punch-ins at 1.0 / 1.18 / 1.36. |
| 8 | TYRE | 243-255 | REUSE | V05_tyre_a src 1.15-1.80 at 1.3x | 720p source, motion-blurred. |
| 9 | LAUNCH | 255-291 | **NEW N2** | N2 src about 1.0-2.5 | |
| 10 | DRIFT | 291-327 | **NEW N3** | N3 src about 1.5-3.0 | Cookie's chip lands at 299. |
| 11 | LOWTRACK | 327-357 | **NEW N4** | N4 src about 1.0-2.25 | |
| 12 | NEARMISS | 357-393 | **NEW N5** | N5 src about 1.5-3.0 | |
| 13 | OVERSHOOT | 393-447 | **NEW N6** | N6 src about 0.5-2.75 | Gordon's chip lands at 403. |
| 14 | ALLEY | 447-483 | **NEW N7** | N7 src about 1.0-2.5 | Daffy's chip lands at 475. |
| 15 | RED1 | 483-525 | REUSE | V08_natural_a src 0.50-2.25 | Starts 0.5 s later than in the first cut, so "Act" still hits the grab. |
| 16 | RED2 | 525-555 | REUSE | V08_natural_a src 2.25-5.25 at 2.4x | |
| 17 | RED3 | 555-571 | REUSE | V08_natural_a src 5.25-5.92 | Newspaper strip softened. |
| 18 | OFFICER | 571-589 | REUSE | V09_officer_a src 2.00-2.75 | |
| 19 | GLIDE | 589-615 | REUSE | V09_officer_a src 4.90-5.98 | Door lettering gets a tracked blur. |
| 20 | SMIRK | 615-626 | REUSE | V12_smirk_a src 2.75-3.21 | |
| 21 | GARAGE | 626-659 | REUSE | V13_garage_a src 2.35-3.72 | Never past src 4.0 (the face drifts). |
| 22 | END | 659-720 | Remotion | end card | |

Continuity carried over from the first cut:
- **Car:** the same badgeless black luxury sedan, with slim wraparound LED tail lights.
- **Cast:** the same three in black knitted three-hole balaclavas. The broad man wears a black leather jacket and gloves and carries the duffel. The slim woman wears a black turtleneck and blazer. The lanky young man wears a grey hoodie with the hood up.
- **World:** the same stone street and strobing red beacon, night rain, sodium and magenta/cyan neon.
- **Patrol cars:** fictional white-and-black sedans with a dark roof bar and nothing readable on them.

## 4. NEW shots: first frames (approved) and image-to-video prompts

Pricing was checked on docs.dev.runwayml.com (pricing guide, 2026-09-27):
- Video: **veo3.1_fast without audio costs 10 credits/s** (15 with audio); veo3.1 costs 20/s, gen4.5 12/s and gen4_turbo 5/s.
- Images: gemini_image3_pro costs 20 per image, gen4_image 8 (1080p), gemini_2.5_flash 5 and gen4_image_turbo 2.

Veo 3.1 Fast at 1080p renders 8 s only (established on the first cut). So **every NEW shot is Veo 3.1 Fast, image-to-video, 1920:1080, 8 s, no audio, at 80 credits.** The negative prompt is the first cut's (no talking, text, logos, extra fingers, face morphing, identity change, extra people, cartoon or handheld wobble), plus "lettering on cars, words, numbers, licence plates, emblems, badges, slow motion, freeze frame".

The first frames are `stills/<N>_first.png`: each approved still, cropped to 1920x1080, with every plate, emblem and sign glyph painted out by `scripts/prep_getaway_frames.py` (the regions are listed in `frames.json`). This way Veo starts from a frame with nothing readable in it.

### N1 SPRINT + DIVE

- First frame: `stills/N1_first.png`, from `S1_sprint` (gemini_image3_pro, 20 credits; refs: scene = the first-cut walk still, crew = the first-cut interior master).
- Video: Veo 3.1 Fast, image-to-video, 1920:1080, 8 s, no audio, **80 credits**. Take name: `takes/N1_a.mp4`.

Still prompt:

> Cinematic film still from a premium action-thriller trailer, anamorphic 32mm lens at T2, 1/48 shutter, night, pouring rain. The exact street, building, red beacon, puddle and sleek black badgeless four-door sedan of @scene, same extreme low angle just above the wide puddle. New moment: the three friends from @crew, same black knitted three-hole balaclavas and clothes (the broad man in the black leather jacket and black gloves clutching a black duffel bag, the slim woman in the black turtleneck and black blazer, the lanky young man in the grey hoodie with the hood up), are SPRINTING flat out from the doorway toward the car, mid-stride, bodies leaning hard forward, arms pumping, feet splashing up sheets of water, the woman in front already reaching for the open rear door. Strong motion blur on legs and splashes, the red warning beacon strobing hard red light through the rain, the puddle mirroring the running figures. Distant neon is only soft abstract bokeh. Deep blacks, wet sheen, rim light, fine grain. Five fingers on every visible hand. No text, no signs, no logos, no licence plates, no wheel emblems.

Video prompt:

> Real-time speed, no slow motion. Static low camera just above the puddle, 32mm anamorphic lens, 1/48 shutter. The three friends in black balaclavas sprint flat out from the doorway to the black sedan, feet smashing through the puddle and throwing sheets of water; they fling the doors open and dive inside head first, the broad man in the leather jacket hurls the black duffel bag in and throws himself in after it, and the doors slam shut one after another. The red warning beacon above the door strobes hard red light through the pouring rain and across the wet stone. Motion blur on the pumping arms and legs, raindrops bouncing, reflections rippling. Urgent, intense, cinematic action. The masks stay on.

### N2 LAUNCH

- First frame: `stills/N2_first.png`, from `S2_launch_b` (gemini_2.5_flash, 5 credits; refs: scene = the first-cut walk still, patrol = the first-cut officer still. The gen4_image take S2_launch was rejected (plate text, door emblems, the wrong street)).
- Video: Veo 3.1 Fast, image-to-video, 1920:1080, 8 s, no audio, **80 credits**. Take name: `takes/N2_a.mp4`.

Still prompt:

> Photorealistic cinematic film still from a premium action-thriller car chase, night, pouring rain, 24mm lens, low camera. The same wet street, dark stone building and strobing red beacon above the doorway as @scene. The sleek black badgeless four-door sedan from @scene launches from the kerb straight toward the camera at full throttle, nose dipping, front three-quarter view, headlights blazing through the rain, thick white tyre smoke and spray pouring from its rear wheels. At the far end of the street behind it, two white and black patrol cars like @patrol skid sideways around the corner in pursuit, roof light bars blazing red and blue. Sodium-orange streetlight and magenta and cyan neon glow, wet asphalt reflections, motion blur, deep blacks, fine grain. No licence plates anywhere: the bumpers are smooth and blank. No emblems, badges, lettering or numbers on any car. No text, no signs, no logos.

Video prompt:

> Real-time speed, no slow motion. Low camera on the wet cobbles, 24mm lens. The black sedan launches from the kerb at full throttle, rear tyres smoking and spraying water, the tail fishtailing, and roars straight past the lens in a violent blur; behind it at the far end of the street two patrol cars with blazing red and blue roof lights slide sideways around the corner and accelerate hard after it. Pouring rain, the red beacon strobing on the stone building, sodium streetlight, motion blur, the camera jolts as the car blasts past. High-stakes action, pure speed.

### N3 CORNER DRIFT (Cookie)

- First frame: `stills/N3_first.png`, from `S3_drift` (gen4_image, 8 credits; ref: car = a crop of the first-cut walk still).
- Video: Veo 3.1 Fast, image-to-video, 1920:1080, 8 s, no audio, **80 credits**. Take name: `takes/N3_a.mp4`.

Still prompt:

> Cinematic film still, premium action-thriller car chase, night, pouring rain. Low camera on a Russian arm at the apex of a wide wet city intersection, 21mm anamorphic lens. The sleek black badgeless four-door sedan from @car is fully sideways in a violent controlled drift through the corner, front wheels counter-steered, a huge fan of spray and tyre smoke peeling off the rear wheels and glowing in the sodium-orange streetlight and magenta and cyan neon. Behind it, red and blue emergency light floods the rain from pursuing patrol cars just out of frame. Dramatic speed, motion blur on the wheels and spray, rain streaks, mirror-like wet asphalt, deep blacks, fine grain. No text, no signs, no logos, no licence plates, no wheel emblems.

Video prompt:

> Real-time speed, no slow motion. Low camera on a Russian arm swinging with the car, 21mm lens. The black sedan drifts fully sideways through the flooded intersection at high speed, front wheels counter-steered, a huge fan of spray and white tyre smoke glowing in sodium-orange and neon light; it snaps straight and rockets away down the street while red and blue emergency light from the pursuing patrol cars floods the rain behind it. Motion blur, rain streaks, mirror-wet asphalt. Violent, precise, thrilling.

### N4 LOW TRACKING

- First frame: `stills/N4_first.png`, from `S4_lowtrack` (gen4_image, 8 credits; refs: car, patrol. Both plates and the patrol emblems are painted out).
- Video: Veo 3.1 Fast, image-to-video, 1920:1080, 8 s, no audio, **80 credits**. Take name: `takes/N4_a.mp4`.

Still prompt:

> Cinematic film still, premium action-thriller car chase, night, pouring rain. Camera rig mounted a hand's width above the wet asphalt, tracking at full speed right behind the rear bumper of the sleek black badgeless four-door sedan from @car, 18mm lens, red tail lights glowing, rear tyre throwing spray straight at the lens. Just behind and to one side, the nose of a white and black patrol car from @patrol is closing in, headlights flaring, its dark roof light bar strobing red and blue. The road surface and lane markings streak into long motion blur, raindrops smear across the frame, sodium-orange streetlights and magenta and cyan neon smear into light trails. Extreme sense of speed, deep blacks, fine grain. The patrol car has no lettering, numbers or emblems. No text, no signs, no logos, no licence plates.

Video prompt:

> Real-time speed, no slow motion. Camera car tracking a hand's width above the wet asphalt right behind the black sedan at extreme speed, 18mm lens. The patrol car with a blazing red and blue roof light bar surges alongside and noses at the sedan's rear bumper; lane markings streak past in long blur, spray blasts at the lens, raindrops smear across frame, streetlights and neon whip by as light trails. Relentless, dangerous, heart-pounding.

### N5 NEAR MISS, SPARKS

- First frame: `stills/N5_first.png`, from `S5_nearmiss_c` (gemini_image3_pro, 20 credits; refs: shot = the gen4 composition S5_nearmiss, car).
- Video: Veo 3.1 Fast, image-to-video, 1920:1080, 8 s, no audio, **80 credits**. Take name: `takes/N5_a.mp4`.

Still prompt:

> Photorealistic cinematic film still from a premium action-thriller car chase, night, pouring rain, 24mm lens, low camera racing behind the action. Use the composition, camera angle, big plain white box truck on the left, orange spark shower, rain and neon lighting of @shot. The car in the centre, seen from behind, is exactly the sleek black badgeless four-door luxury sedan from @car: same long body, slim wraparound LED tail lights glowing red, glossy wet black paint. It knifes through the gap past the truck at insane speed, its mirror inches from the truck. Right beside its rear bumper a white and black patrol car with a dark roof bar blazing red and blue scrapes a steel barrier, throwing a shower of bright orange sparks. Heavy motion blur on the road and background, spray off the tyres. No licence plates on any vehicle: every bumper is smooth and blank. No emblems, badges, letters or numbers on the sedan, the patrol car or the truck. Neon signs are abstract glowing shapes with no letters. No text anywhere, no logos.

Video prompt:

> Real-time speed, no slow motion. Camera car racing right behind, 24mm lens. The black sedan swerves through the gap past the big plain white box truck, missing it by inches, the truck's flank rushing past the lens; the patrol car beside it scrapes along the steel barrier throwing a fountain of orange sparks, fishtails and drops back. Heavy motion blur, spray, pouring rain, red and blue light strobing across wet paint. Near-miss, insane speed.

### N6 OVERSHOOT, HANDBRAKE 180 (Gordon)

- First frame: `stills/N6_first.png`, from `S6_overshoot_c` (gen4_image_turbo, 2 credits; ref: car. The earlier S6_overshoot was a two-door coupe).
- Video: Veo 3.1 Fast, image-to-video, 1920:1080, 8 s, no audio, **80 credits**. Take name: `takes/N6_a.mp4`.

Still prompt:

> Cinematic film still, premium action-thriller car chase, night, pouring rain. Overhead drone view looking straight down on a wide wet empty city intersection glowing with sodium-orange streetlight pools and magenta and cyan neon reflections. In the centre, the long black four-door luxury sedan from @car (four doors, long wheelbase, glossy black roof) is mid handbrake turn, spun sideways across the lanes, a curved arc of white tyre smoke and spray tracing the spin on the glossy asphalt. Far up the road, two white and black patrol cars with blazing red and blue roof lights race toward the intersection. Motion blur on the smoke, rain streaks, deep blacks, fine grain. No text, no words on the road, no signs, no logos, no licence plates, no emblems.

Video prompt:

> Real-time speed, no slow motion. High overhead drone looking down at the wet intersection. The black sedan, mid handbrake turn, whips around through a full 180 degrees in a tight arc of white tyre smoke and spray, then launches hard back the way it came and darts away as the two patrol cars with blazing red and blue roof lights race in and brake too late. Pouring rain, sodium-orange and neon reflections, motion blur on the smoke. Precise, audacious, high-stakes action.

### N7 ALLEY ESCAPE

- First frame: `stills/N7_first.png`, from `S7_alley` (gen4_image, 8 credits; ref: car. The plate and grille emblem are painted out).
- Video: Veo 3.1 Fast, image-to-video, 1920:1080, 8 s, no audio, **80 credits**. Take name: `takes/N7_a.mp4`.

Still prompt:

> Cinematic film still, premium action-thriller car chase, night, pouring rain. Low head-on angle, 35mm anamorphic lens, inside a narrow wet brick alley barely wider than a car, steam rising from grates, a single sodium-orange lamp and magenta neon spill. The sleek black badgeless four-door sedan from @car barrels straight toward camera at full speed, headlights blazing with anamorphic flares, its wing mirrors inches from the walls, spray flying off the puddles. Far behind it at the mouth of the alley, red and blue emergency lights flash past on the street as the pursuit overshoots the turn. Motion blur, rain streaks, deep blacks, fine grain. No text, no signs, no graffiti words, no logos, no licence plates, no grille emblem.

Video prompt:

> Real-time speed, no slow motion. Low head-on camera inside the narrow wet brick alley, 35mm anamorphic lens. The black sedan barrels straight toward the lens at full speed, mirrors inches from the walls, steam and spray exploding around it, headlights flaring, and blasts past the camera; behind it the patrol car with red and blue roof lights overshoots the alley mouth and is gone. Pouring rain, steam, sodium lamp and magenta neon spill, motion blur. The escape.
## 5. Budget

| Item | Credits |
|---|---|
| Stills (this run, per the ledger): 2 x gemini_image3_pro, 6 x gen4_image, 2 x gemini_2.5_flash, 1 x gen4_image_turbo | **100** spent (cap 100) |
| Video, first takes: 7 x Veo 3.1 Fast 1080p 8 s | 560 |
| Retake reserve, in priority order: N1 sprint and dive, N3 drift, N5 near miss, N6 handbrake 180 (3 of the 4, at 80 each) | 240 |
| Chase SFX (eleven_text_to_sound_v2, 1 credit/s): splashing footsteps 4, three door slams 3, drift screech 4, handbrake and slide 3, truck horn doppler 4, metal scrape and sparks 3, close siren pass-by 5, alley whoosh 3 | 29 |
| **Production total still to spend** | **About 829** (560 at minimum) |

Balance: 1228 before this run (the brief expected about 228; the account had already been topped up), and 1128 after the stills. A full production at the ceiling would leave about 299.

## 6. Voices (verified three ways)

Sources and checks:
- **Text:** from `presets/<slug>.json`.
- **Audio:** from `packs/<slug>/audio/master/<phrase>.mp3`.
- **Transcription:** faster-whisper small.en for the word timings, cross-checked with medium.en.
- **Speech length:** measured on the trimmed, untreated file with an RMS detector (peak - 35 dB).

Treatment (`scripts/build_getaway_voices.py`): the end silence is trimmed below -45 dB (nothing else is cut), then a phone band-limit (high-pass at 250 Hz; 180 Hz for Cookie, to keep his growl), a small-room echo, and -16 LUFS. No voice is cut, sped up or pitch-shifted.

| Key | slug / phrase | Preset text | Heard (medium.en) | Speech | File (treated) |
|---|---|---|---|---|---|
| elmo_hello | elmo / start_drive_1 | Hi! Elmo is so happy to see you! Let's go! | Hi! Elmo is so happy to see you! Let's go! | 4.62 s | 4.708 s |
| cookie_police | cookie-monster / police_ahead | Police ahead! Me behave! Me hide cookies! | Police ahead! Me behave! Me hide cookies! | 4.14 s (a growl tail after "cookies!", which ends at 3.68) | 4.209 s |
| gordon_missed | gordon-ramsay / reroute_chime | You missed it, you donkey! | You missed it! You donkey! | 2.24 s | 2.307 s |
| daffy_police | daffy-duck / police_ahead | Police ahead! Act natural. Act natural! | Police ahead! Act natural! Act natural! | 3.83 s | 3.906 s |
| bugs_arrived | bugs-bunny / arrived | We've arrived. That's all, folks! | We've arrived! That's all folks! | 2.50 s; "That's" at 1.37 | 2.565 s |

The captions show the preset text exactly; the punctuation differences in the "Heard" column come from the transcriber. `stage_getaway.py` snaps each phrase's first word to the measured onset. The snap now moves only the word nearest the onset; the old rule wrongly moved Gordon's "missed" onto "You".

## 7. Edit, sound and pipeline

- **`film/src/getaway.config.ts`:** the whole timeline (shots laid end to end in frames), the five lines, the beds and the hits. It no longer imports `toughcrowd.config.ts`, which was never committed, so a fresh checkout of main could not build the film. BRAND, FONT and CAST are now inlined.
- **`film/src/Getaway.tsx`:** 16:9 full frame with no bars. The 9:16 layout, the speedometer and the phone insert are removed, and the captions are boxless. A NEW shot that is still a placeholder gets a 6 % push and a small "N3 STILL"-style tag in the top left, so the preview is honest about what it shows.
- **`scripts/stage_getaway.py`:** stages the reused takes. For each NEW shot it copies `film/runway4/takes/N*_a.mp4` if that exists; otherwise it holds `stills/N*_first.png` for 8 s. It then writes `src/getaway-media.json`.
- **`scripts/finish_getaway.py`:**
  1. Renders the picture muted.
  2. Builds the mix with `mix_getaway.py`.
  3. Checks every line by cross-correlation (each must be under half a frame off).
  4. Converts to limited-range yuv420p and masters to -14 LUFS, under -1 dBTP (`master_ad.py`).
  5. Writes a web copy.

  While any placeholder remains the output is `film/out/getaway_v2_preview.mp4`. Once all seven NEW shots are takes, it is `film/out/getaway_v2_16x9.mp4` plus `_web`.
- **Preview sound:** the first cut's SFX (peel-out on the spin and on the 180, sirens, road, whooshes, three door thunks) stand in for the chase SFX listed in section 5.

**Production, step by step:**
1. For each of N1..N7, run `python scripts/runway_getaway.py --dir runway4 video takes/N1_a.mp4 --first stills/N1_first.png --seconds 8 --prompt-file prompts/V_N1.txt --negative "lettering on cars, words, numbers, licence plates, emblems, badges, slow motion, freeze frame" --purpose "..."`. The key goes only in `RUNWAY_KEY`.
2. Review each take. Set `srcIn` for each NEW shot in the config to its best 1.25 to 2.25 s, and add blur tracks for any generated lettering.
3. Generate the chase SFX and swap them into BEDS/HITS.
4. Run `python scripts/stage_getaway.py && python scripts/finish_getaway.py`.

## 8. Risks

- **Veo and speed.** Veo tends to slow action down and drift into "cinematic" slow motion. The prompts ask for real time and the negative prompt bans slow motion. The edit uses only 1.25 to 2.25 s of each 8 s take, sped up to 1.3x if a take feels soft (voices are never touched).
- **N1 is the hardest shot:** three people sprinting, doors opening, diving in. Expect glitches in limbs and doors, which is why it heads the retake queue. Fallback: use only the sprint (src 0.5-2.5) and cover the slam with SPRINT_B from a second take.
- **N6, the handbrake 180 from overhead:** Veo may not complete a clean 180, or may reverse badly. The first frame is already mid-spin, so even a partial rotation reads.
- **Car continuity:** the N4 and N7 stills came from gen4_image with a generic sedan body, and the N4 tail lights differ. In 1.25 to 1.5 s of motion-blurred rain it should read as the same black car. N4 is the first candidate for a new still if it does not.
- **Generated text** (plates, "POLICE" on doors, neon glyphs) will reappear in moving footage, even from clean first frames. Budget time for tracked blurs, as on the first cut.
- **Cookie says "Police ahead!" while the police are behind.** It plays as a joke, and N2's first frame also has patrol cars at the end of the street, but it is the least literal line.

## 9. Open item: image-to-video not run

Mid-run, the lead relayed the owner's top-up and asked to continue into full production. The attempt to start the seven Veo generations was refused by this environment's permission check: spending 560+ credits on a paid API counts as a real-world transaction and needs the owner's own approval here. Nothing was generated or charged. Once the owner approves, the production steps in section 7 run as written.

## 10. Preview QA (`film/out/getaway_v2_preview.mp4`, stills standing in for N1-N7)

- **Delivery:** H.264 High, yuv420p limited range, 1920x1080, 24 fps, 720 frames, with video and audio both 30.000 s. The web copy is `getaway_v2_preview_web.mp4`.
- **Sound:** -14.1 LUFS integrated, true peak -1.5 dBTP.
  - Sync: every line cross-correlates to its planned frame (0 ms in the mix, 5 ms after AAC, which is under a frame).
  - Content: faster-whisper medium.en on the master hears all five lines word for word.
  - Chase beds: the road and sirens were lowered to -11 and -13 dB after "Police ahead" was masked in the first mix.
  - Section RMS: lines -13.7 to -17.0 dBFS; the look-chain silence -27; the officer's squint -24.
- **Picture:** every large frame change is a planned cut (72, 90, 196, 211, 226, 243, 255, 291, 327, 357, 393, 447, 483, 571, 615, 626, 659). There are no black frames. The only near-static frames are the held end card and the first frames of the placeholder pushes, which will go away with the real takes. A frame sheet across all cuts and every line was checked by eye: the captions show the preset text, each chip lands on its turn, there are no letterbox bars and no caption boxes.
