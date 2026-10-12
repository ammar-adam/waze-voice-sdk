# Brief: drawing a character face

We are scaling Backseat from 12 to 100 characters. Each one needs a sticker
face that sits in a circle on the site.

Python: C:/Users/aaamm/AppData/Local/Programs/Python/Python313/python.exe

## What to produce

For each slug you were given (from the "main" list in roster/roster.json):

1. `site/faces/<slug>.svg`. Skip any that already exists.
2. One entry in `roster/colors/<your batch>.json`:
   `{slug: {"bg": "#rrggbb", "tone": "#rrggbb", "tone_ink": "#rrggbb"}}`
   - bg: a soft pastel panel behind the face that the face stands out on.
   - tone: the character's signature strong colour, used for the Install
     button.
   - tone_ink: text colour on tone, either #ffffff or #15172b, whichever has
     the better contrast.
   See site/characters.css for the twelve existing sets.

## House style

Read these first and match them: site/faces/elmo.svg, cookie-monster.svg,
bugs-bunny.svg, tigger.svg, mickey-mouse.svg, batman.svg, darth-vader.svg,
eric-cartman.svg, gordon-ramsay.svg.

- `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200' role='img'
  aria-label='<Character name>'>`. Plain SVG: paths, ellipses, circles.
  No text, no images, no gradients, no filters, no scripts, no external refs.
- Ink outline #15172B, stroke-width 5 for the main shapes and 3 to 4 for
  details, round joins and caps. Flat fills.
- HEAD ONLY, centred on (100, 100), no neck or shoulders. The whole head,
  ears and hat included, must fit inside the circle: keep everything within
  about 12 to 188 on both axes, and away from the corners.
  Exception: a character whose body IS the look (SpongeBob, Patrick, a
  Stormtrooper helmet, GLaDOS, HAL 9000's lens, Lightning McQueen and Mater as
  cars seen from the front) is drawn as that shape, still centred and inside
  the circle.
- ON-MODEL above all. The owner rejected earlier faces as "demented" and
  "looks nothing like" the character. Build each face from the two or three
  features that make that character recognisable at 60 pixels: silhouette,
  signature colours, eyes, and one prop or mark (Yoda's long ears and
  wrinkles, Homer's two hairs and stubble area, Mario's cap, M and moustache).
  Friendly, simple, bold. Calm eyes with pupils looking forward: wide staring
  whites with tiny pupils read as deranged.
- Live-action characters (Gandalf, Jack Sparrow, Michael Scott and so on) are
  drawn as a simple cartoon of the costume and hair, in the style of
  gordon-ramsay.svg, never a realistic portrait of the actor.

## Method

Render and LOOK at every face. Do not ship one you have not seen.

    python scripts/face_sheet.py <scratch>/sheet.png --size 420 <slug> <slug>

Then Read the PNG. Critique each one honestly against the real character,
fix it, and render again. At least three rounds for each face. Finish with one
sheet of your whole batch at the default size, next to elmo and
cookie-monster, and confirm yours hold up beside them and still read at that
size.

Write scratch files only under
C:/Users/aaamm/AppData/Local/Temp/claude/C--Users-aaamm-mci-website/64bfc893-a596-48c5-80c6-62df53eb2b58/scratchpad/faces-<your batch>/

Do not edit any other file, do not commit.

## Report

The slugs drawn, the path of your final sheet PNG, and an honest ranking:
which faces are strong, which are only passable, and which you could not get
right.
