# Brief: writing a character preset

We are scaling Backseat from 12 to 100 Waze voice packs. A preset is the
43-line navigation script for one character, spoken later by a voice clone.

Python: C:/Users/aaamm/AppData/Local/Programs/Python/Python313/python.exe

## What to produce

For each slug you were given (from the "main" list in roster/roster.json):

1. `presets/<slug>.json`. Skip any that already exists and leave it untouched.
   Model it EXACTLY on presets/mickey-mouse.json. Also read
   presets/darth-vader.json, presets/eric-cartman.json and
   presets/cookie-monster.json for tone range, and docs/presets.md.
   Same keys: schema_version, label, description, provider "fish", voice,
   direction, provider_options {"temperature": 0.5, "top_p": 0.6}, notes,
   units "both", rights, and all 43 `lines` keys.
   - `voice`: the literal string "TBD". Another agent is choosing the voice
     models. If the loader rejects "TBD", report it; never invent an id.
   - `direction`: how the voice should deliver the lines.
   - `rights`: status "in-copyright", with an accurate source_work, author and
     year for that character, and the same covered / not_covered / notes
     wording pattern as Mickey's, adjusted truthfully.
2. One entry in `roster/blurbs/<your batch>.json`:
   `{slug: {"blurb": "...", "tags": [...], "waze_name": "..."}}`
   - blurb: one punchy line, at most 60 characters, in the style of the blurbs
     in site/voices.json. No em dashes.
   - tags: the franchise, then 2 to 5 lowercase terms someone might type into
     a search box ("star wars", "jedi", "green").
   - waze_name: the name drivers see in Waze, normally the character's name.

## Writing rules

tests/test_repetition.py and `python scripts/wvs.py presets check <slug>`
enforce these. Read both to learn the exact rules and required tokens.

- A pack has ONE recording per prompt and Waze replays it constantly. Prompts
  heard at every junction stay PLAIN, in the exact wording Mickey's preset
  uses: turn_left, turn_right, keep_left, keep_right, exit_left, exit_right,
  go_straight, and_then, roundabout, exit_first to exit_fourth, in_tenth_mile,
  in_quarter_mile, in_half_mile, in_200_meters, in_400_meters, in_800_meters.
  When in doubt, copy Mickey's plain lines.
- Character and catchphrases go on: all 9 start_drive greetings (all
  different; no more than 3 may share the same first three words), the six
  alerts, reroute_chime (never the word "Recalculating"), u_turn, exit_fifth
  to exit_seventh, in_one_mile, in_1000_meters, in_1500_meters, and arrived.
- Every line must still say its navigation meaning clearly. Arrived needs
  "arrived", "here" or "we're there"; police needs "police"; a distance line
  states the distance.
- Write for the ear. Frequent prompts are at most 70 characters. Nothing a
  voice clone will trip over: no stage directions, no emoji, no ALL CAPS,
  numbers spelled as words, plain punctuation.
- Make each one funny and unmistakably that character: real catchphrases,
  speech patterns and references a fan would recognise.
- Family-friendly, always: no profanity, no slurs, nothing sexual, even for
  edgy or adult-animation characters.
- Never quote more than a short catchphrase from the source.

## Verify

- `python scripts/wvs.py presets check <slug>` for each of yours.
- `python -m unittest tests.test_repetition`. It globs every preset and other
  agents are adding presets at the same time, so judge by failures that name
  YOUR slugs.

Do not edit any other file, do not touch other agents' presets, do not commit.

## Report

The slugs written, anything skipped, the test results, and three sample lines
for each of four characters so the voice can be judged.
