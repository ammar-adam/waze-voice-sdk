# Brief: drawing a character face, v2 (the approved rich style)

The owner rejected the first flat faces as ugly, with "no design or detail",
and approved the richer style shown in the bottom row of
roster/face-kit/before_after.png. Read that image first, then read the three
approved examples: site/faces/ted.svg, site/faces/yoda.svg,
site/faces/gandalf.svg. roster/face-kit/example_build_faces.py is the script
that generated them (helpers for cel-shaded forms, fur outlines and fur
ticks): copy and adapt it into your own scratch folder rather than writing raw
SVG by hand.

Python: C:/Users/aaamm/AppData/Local/Programs/Python/Python313/python.exe

## What to produce

For each slug you were given: `site/faces/<slug>.svg`, REPLACING the flat
first-pass file if one is there (look at it for the idea, then redraw it
properly). For any slug not already in roster/colors/*.json, also add
`{slug: {"bg", "tone", "tone_ink"}}` to `roster/colors/<your batch>.json`
(bg: soft pastel panel the face stands out on; tone: the character's strong
signature colour; tone_ink: #ffffff or #15172b, whichever contrasts better).

## The owner's standard

"Make sure the faces look proper." Each one must look like THAT character to a
fan at a glance, and look designed: appealing, bold, detailed, professional
mascot quality. He has called earlier attempts "demented" (staring eyes),
"looks nothing like" the character, and "stupid". A face that is merely
passable is not done.

## Style guide

1. Canvas: viewBox 0 0 200 200, plain SVG, round joins and caps. No text, no
   raster images, no scripts, no filters, no external refs. Internal
   `<clipPath>` is fine; prefix every id with the slug.
2. Fill the circle: the silhouette spans 88 to 96 percent of it. The face takes
   at least half the area. Corners are cropped, so stay within about 105 units
   of the centre.
3. Line: outer contours in ink #15172B at 4.5 to 5. Interior lines 1.8 to 3.6,
   mostly in a dark tint of the local colour. Ink inside the shape only for
   eyes, mouth and props.
4. Four tones per material: base, shade (about 20 percent darker), highlight
   (about 15 percent lighter), deep line tint. No gradients.
5. Light from the top-left: shade on the lower right of every form, one
   highlight upper-left, cast shadows under brims, brows, nose and chin.
6. Eyes with life: sclera, coloured iris, pupil, one large and one small
   highlight, upper lid over 25 to 40 percent of the iris, brows as filled
   shapes that carry the attitude. Never wide staring whites. For characters
   whose real design has simple eyes (Homer, SpongeBob, Mario, Peppa Pig,
   South Park), keep their real eye design and add the depth elsewhere.
7. Texture: fur gets a zigzag silhouette and short ticks; hair and beards get
   overlapping locks with strand lines; cloth gets folds and stitching; metal
   and plastic get crisp highlights and panel lines; skin gets a few wrinkle
   lines and soft blush.
8. One prop or costume cue that tells the story, overlapping the edge of the
   face (Mario's cap and M-shaped emblem without the letter drawn as text is
   fine as a path; Thor's hammer; Shaggy's sandwich). Lettering must be drawn
   as paths, never <text>, and only when it is part of the design.
9. Busts are allowed when the costume aids recognition. Never let one run off
   y=200: clip it to a circle of radius 97 at (100,100) and close it with an
   ink arc, as yoda.svg does.
10. On-model first. Cartoon characters follow their real model sheet:
    proportions, colours, signature shapes. Live-action characters are a
    stylised cartoon of costume, hair and attitude, never a realistic portrait.

## Method

1. Reference: before drawing each character, look at real art of it. Use the
   built-in browser (mcp__Claude_Browser__* tools; load with ToolSearch if
   deferred). Create YOUR OWN tab with tabs_create and pass that tabId on
   every call, because other artists share the browser. Open an image search,
   for example https://www.bing.com/images/search?q=<character>+official+art,
   and take a screenshot. Look only: do not download, copy or trace. If the
   browser fails twice, work from knowledge and say so in your report.
2. Draw, render and LOOK:
   `python scripts/face_sheet.py <scratch>/sheet.png --size 420 <slug> ...`
   then Read the PNG. Critique hard against the reference: likeness first,
   then expression, then detail. Fix and re-render. At least four rounds per
   face. Check a 64 pixel render as well (`--size 64`).
3. Finish with one sheet of your whole batch at `--size 300`, with ted and
   yoda on it for comparison, saved as `<scratch>/final.png`.

Scratch files only under
C:/Users/aaamm/AppData/Local/Temp/claude/C--Users-aaamm-mci-website/64bfc893-a596-48c5-80c6-62df53eb2b58/scratchpad/facesv2-<your batch>/
Use file names unique to your batch. Do not edit any other repo file, do not
commit. Save each SVG as soon as it is good.

## Report

The slugs drawn, the path of final.png, whether you could view references,
and an honest ranking: strong, good, and any you are not satisfied with.
