---
name: lettering
description: Prepare or revise manga page masks, native layouts, fonts, effects and three-layer renders for this repository. Use for visual page work after translation, including cleanup and user revision requests.
---

# Manga lettering

Read `profiles/lettering.json` for the preferred defaults and [the workflow](../../workflow.md#native-layout-cleanup-and-rendering) for commands and metadata. Reviewed page layouts take precedence. Match the source resolution, balloon shape and user feedback rather than forcing one font size or one treatment across a chapter. The translation skill owns wording; do not change a line's meaning just to make it fit.

## Dialogue and narration

Use Anime Ace v3 for ordinary uppercase dialogue and small effects, with horizontal text, phrase-aware breaks and optical centering in the actual cavity. Match weight to nearby lettering and voice. Keep room around the text, preserve punctuation, and avoid unnecessary hyphenation or shrinking text until it is unreadable. Thoughts and shouting can differ when the source calls for it.

Keep the artist's original outline, connected tails, hearts and intentional marks. A plain white balloon or square narration box needs a clean white interior. Use a mask confined to that interior, then inspect below and around the new letters for source fragments, tiny dots, seams, gray smudges and doubled outlines. Do not invent replacement balloons. Restore a damaged outline using a native paste of the original cleaned outline, not a generated approximation.

## Effects over artwork

Preserve expressive Japanese action lettering integrated into the drawing and add a short nearby English subtitle when replacement would damage its character or art. Translate ordinary balloon effects directly when the cavity can be cleaned. Keep subtitles separate from the source stroke and avoid covering adjacent art.

Over a smooth gradient, retain the original background and use the reviewed soft white glow behind the English. Do not simulate the gradient with a patch or add a bubble. Native text stroke/glow effects belong to the text raster. Protect hearts, signatures, screentones, censor bars and intentional symbols even inside a repair area. Compare their surroundings at full resolution.

## Prose and credits

Author commentary and afterwords use Segoe Print, natural sentence case, left alignment and readable paragraph rhythm. For an illustrated commentary page that needs a side translation, keep the complete art and use an aligned pale margin with warm dark ink. The profile's indie commentary reference uses a 2572-pixel art width plus a 1500-pixel right margin on a 4072 by 3674 canvas, ink RGB 106, 93, 83. These dimensions describe that treatment; adapt the layout to another source. Do not put English on protected art merely to match those numbers.

For neutral publication credits, use Arial and Arial Bold with aligned label/value columns and the source's hierarchy. A compact translated layout can use blank space above the original colophon. Keep original publication details below it when this is the chosen treatment. The bundled Arial Unicode font supports unresolved Japanese names. Do not invent romanizations. Check long notices for clipping and afterword paragraph edges for leftover source lines.

## Native preparation

Use the pinned engine's operations for page painting and typography. Scripts may prepare metadata or binary masks, copy files, read pixels and hash. Native inpainting/paste and established FFmpeg operations perform pixel changes; do not introduce custom RGB painting or use image generation for these repairs.

Keep `translation_raw` equal to the canonical revision line. Put visual case and `[BR]` wraps in `translation`. When wording changes, rebuild or clear stale `translation_rich` as well; changing raw text alone may leave the old glyphs in the render. Preserve rich effects that are still intentional. Update native region mappings when a source record is added or split, without renumbering stable IDs.

Set page cleanup explicitly. Native `none` fills the refined mask white. Native `original` retains a prepared base and does not remove source text. For art that needs reconstruction, use a constrained native model and inspect the result. An artistic subtitle usually needs a zero mask over the retained Japanese. Keep mask dimensions equal to the prepared canvas and mark a mask refined only after checking it. Save a lossless base before adding English.

For an expanded canvas or prior manual repair, use a prepared input through `cleanup.source`. It must be inside the chapter and contain no old English that would be lettered twice. Carry forward unaffected manual work. If a new render supersedes an edited page, reconcile its repairs and disclose that change to the user while retaining the parent revision.

Use fresh runs when masks, pixels or settings change. Reusing the engine's old inpainted cache can silently keep an outdated repair. Reuse an unchanged clean base only when its receipt still matches. Verify actual font files and families before rendering. The dialogue and Unicode fonts are bundled; Segoe Print and Arial depend on the OS. Resolve a missing font with the user rather than silently substituting it.

## Render and inspect

Capture original, transparent cleanup paint and transparent English lettering from the same native pass. Decode the original through native image helpers so JPEG decoder rounding is not mistaken for paint across the artwork. Keep all rasters on the complete page canvas at the origin. The original sits at top left; added margins belong to paint, with transparent extension in the original layer.

The PSD stack is English text on top, paint in the middle, locked original at the bottom. Hiding text shows the clean page; hiding paint reveals the source. The Node writer verifies layer records and pixel composition. Empty text is valid for a genuinely textless page, not a substitute for a missing capture. Do not extract supposed English layers from a flattened old revision.

Inspect affected regions with their surroundings at full size, compare against the source or previous revision, and check wrapping, punctuation, weight, clipping, outlines, symbols, smudges and untouched art. File checks do not certify visual quality. Import the new revision, present it in the review app and continue the user's revision loop. User approval belongs to the coordinator's workflow.
