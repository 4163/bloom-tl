# Chapter workflow

[PROMPT.md](../PROMPT.md) coordinates the agent and user. This file owns commands and chapter records. [Setup](setup.md) owns environment preparation. The [translation skill](skills/manga-translation/SKILL.md) owns English; the [lettering skill](skills/lettering/SKILL.md) owns page appearance. Run commands from the repository root. `$taskEnginePython` means the full engine interpreter verified during setup.

## Source intake

Check `python -I -B manga.py status` first. Resume an initialized chapter. For a new chapter, use the archive or folder already supplied; otherwise guide the user to `input/<chapter>/` or ask for its existing path. Extract copies without changing image encoding. Determine the actual page order and retain original filenames.

Prepare a manifest outside `source/pages`, for example `input/chapter/manifest.json`:

```json
{"title":"Chapter title","pages":[{"id":"0001","source":"scan-1.jpg","size":[1057,1500]}]}
```

IDs are four digits in reading order. `source` is a basename in the extracted pages directory; `size` is its real width and height. Initialize once:

```powershell
python -I -B manga.py init chapter --manifest input/chapter/manifest.json --pages input/chapter/pages --archive input/chapter/original.zip
```

Omit `--archive` for a scans folder. An archive already placed in the chapter's `source/` can be reused. Init copies and hashes the originals. It does not create translations or alter image pixels.

## Extraction and final transcript pass

```powershell
python -I -B manga.py engine extract chapter --python $taskEnginePython --run ocr-001 --execute
python -I -B manga.py extract-transcript chapter --native-json projects/chapter/work/ocr-001/input/manga_translator_work/json
```

Without `--execute`, engine commands only show a preview. Every new run uses a fresh name. Native inputs are named by page ID even when original filenames differ. The native JSON importer requires every page, including zero-region results. Missing JSON is an extraction failure to investigate, not proof of a textless page.

The importer writes `transcript/raw.jsonl`, `checked.jsonl`, `coverage.json`, the native OCR snapshot and `native/region-map.json`. JSONL contains text records, not placeholder rows for textless pages. Coverage accounts for every page.

Compare checked JSONL with every page in order. Check missed balloons, small effects, margins, reading order and clipped characters. Keep stable IDs. Edit only checked JSONL; update coverage and native mappings for added, removed or split regions. Mapping entries identify the native page and region index. Visually certain OCR corrections are retained in the audit's correction record. Ambiguous readings need the user's decision. Omitting an extracted record also needs a recorded user decision.

```powershell
python -I -B manga.py issue chapter --stage transcript --record chapter.p0001.r001 --question "Evidence, uncertainty and proposed reading"
python -I -B manga.py resolve chapter q0001 --decision "The user's confirmed reading" --by user
python -I -B manga.py audit-transcript chapter --note "Describe the completed visual pass and corrections"
```

The audit binds checked JSONL and coverage. Editing either requires a new visual pass and audit before handoff or final output. Raw extraction stays immutable.

## Translation handoff and decisions

```powershell
python -I -B manga.py handoff chapter r001
```

Give a writing agent only `projects/chapter/handoffs/r001/TASK.md` and a translation-only assignment. The packet contains the source, glossary, decisions, page paths and copied writing skills. The writer returns only `en.jsonl`, `glossary.out.json`, `questions.json` and `completion.json`. The completion record confirms separate accuracy and fluency reviews. Every source ID appears once in English, in order. Intentional empty translations must be declared in project data.

```powershell
python -I -B manga.py accept-translation chapter r001
```

The import creates the revision and records returned questions. Present material ambiguities, transcript doubts and intentional departures in chat with evidence and proposed wording. Record the user's decisions using `resolve --by user`. If the source changes, re-audit it and make a fresh packet. Do not let the writer silently repair disputed source text. Do not start lettering with open source or translation questions.

## Native layout, cleanup and rendering

Prepare `native/layouts/r001/<page>_translations.json` from the native OCR metadata. Follow the lettering skill for geometry, masks, wraps, fonts, rich text, protected art and effect choices. `translation_raw` must equal the corresponding canonical English line; `translation` may contain uppercase styling and `[BR]` breaks. Keep `translation_rich` synchronized or remove stale rich text when updating a line.

Each page selects cleanup settings in its native payload:

```json
{"cleanup":{"inpainter":"none","device":"cpu"},"mask_is_refined":true,"mask_raw":"base64-encoded PNG mask","regions":[]}
```

This illustrates the fields, not a complete text layout. Use actual native regions and a reviewed mask matching the output canvas. `none` fills masked pixels white. `original` preserves a prepared base. For art requiring reconstruction, select the appropriate stock model such as `lama_mpe` with a tightly constrained mask. Retained source effects use an explicit zero mask. Truly textless pages can omit the mask. Optional `cleanup.source` is a project-relative prepared base, useful for an already expanded commentary canvas or retained repairs; it must contain no old English that the new text would duplicate.

```powershell
python -I -B manga.py engine clean chapter --revision r001 --python $taskEnginePython --run clean-001 --execute
```

The adapter calls the pinned native inpainter and writes lossless bases in `work/clean-001/output`. Inspect them against the originals. Native paste overlays restore approved outlines or repairs during layer capture. Once masks, fonts, layout and art protection have actually been checked, write `native/layouts/r001/preflight.json`:

```json
{
  "english_sha256":"SHA-256 of revisions/r001/en.jsonl",
  "profile_sha256":"SHA-256 of profiles/render.json",
  "masks_checked":true,"fonts_checked":true,"layout_checked":true,"protected_art_checked":true,
  "layout_sha256":{"0001":"SHA-256 of the native page layout"},
  "bases":{"0001":{"path":"work/clean-001/output/0001.png","sha256":"SHA-256 of that base"}}
}
```

Include each page to be rendered. These booleans record the visual checks, not a substitute for them. Do not mark them true just to pass a gate.

```powershell
python -I -B manga.py engine render chapter --revision r001 --python $taskEnginePython --run render-001 --execute
python -I -B manga.py import-pages chapter r001 --from projects/chapter/work/render-001/output
```

Render captures native text, paint and original rasters. Its layer manifests bind the English hash from the start of the run; editing English during or after that run requires a fresh render. Import checks that binding and the capture receipts before creating PSD bundles. The first revision needs every page. A new flat-only import cannot stand in for native layers.

## Review and agent revisions

Start the review server using setup's launch instructions and share its URL. Show the complete first revision. The app opens on Output selection, which assembles the chosen version of every page. It compares merged pages against originals or earlier revisions and refreshes after changes. Its controls include Append note, Export PSD, Import PSD, Use this version for output and Use latest. Individual PSD layers are edited in the user's image editor, not toggled in this browser.

Read chat feedback and open chapter notes, then fork for agent changes:

```powershell
python -I -B manga.py fork chapter r002 --from r001
```

Fork copies English and glossary, records the parent and leaves the displayed output in place until the new render is imported. It preserves explicit page choices. Apply wording changes using the translation skill, then prepare layouts and bases for affected pages. For a local fix, select only those pages:

```powershell
python -I -B manga.py engine clean chapter --revision r002 --python $taskEnginePython --run clean-002 --pages 0001 --execute
python -I -B manga.py engine render chapter --revision r002 --python $taskEnginePython --run render-002 --pages 0001 --execute
python -I -B manga.py import-pages chapter r002 --from projects/chapter/work/render-002/output
```

Unrendered pages inherit their parent's verified native bundles and manual exports. English changes on an unrendered page are rejected. A parent that has only old flattened pages needs a full native capture before partial revisions. A rendered page supersedes any old manual override on that page; reconcile its repairs first and tell the user. `render.json` lists superseded manual pages. Prior revision files remain available.

Record an implemented visual fix without claiming user approval:

```powershell
python -I -B manga.py resolve chapter q0002 --decision "Removed the leftover source strokes in Area 2 and restored the white balloon fill." --by agent --revision r002
```

Run this after importing and inspecting the completed revision containing the fix. The required `--revision` identifies that revised page; it must differ from the note's original reviewed revision. The note retains its original `revision` and areas, stores the explanation in `decision`, and adds `addressed_revision`, `addressed_image_path` and `addressed_image_sha256`. Its `status` becomes `resolved`, displayed as Addressed by agent. This is an implementation response, not user acceptance. Older resolved notes without these fields remain readable. Repeat presentation and revision until the user is satisfied. Source and wording ambiguities always use `--by user` with the actual answer.

Append note saves a page review note in `issues.json`; it does not render a page or start agent work. Agents read open notes as part of the next review pass. The app displays the original note separately from an agent's explanation and offers View addressed page for a revision-linked fix. Remove note withdraws a page note from the visible list, preserving its record with `status: removed`, `removed_by` and `removed_at`. Removed notes are not open requests and must not be marked fixed or reused as new note IDs. Source and translation decisions retain their existing decision workflow.

### Notes with a selected area

Mark area shows the English page and lets the user draw several numbered rectangles with a mouse, pen or touch. Write note focuses the note form, where each area appears with its ID and coordinates. Clicking an area reference inserts a label such as `[Area 2]` into the text. The boxes attach together to the next Append note note. Remove individual areas with their numbered chips, or use Clear all or Escape. IDs stay stable when another area is removed. A page, revision or reviewed-image change clears the selection so it cannot attach to another page. Page-wide notes remain available. Saved notes offer Show areas, which opens their recorded page version and highlights the boxes. Alternate comparison variants do not accept area selections.

The existing `issues.json` record retains the page ID in `record` and the reviewed revision in `revision`. Its optional `regions` array contains one object per area:

```json
[
 {
  "id": "area-2",
  "coordinate_space": "page_pixels",
  "x": 120, "y": 340, "width": 260, "height": 180,
  "canvas_size": [1200, 1600],
  "image_path": "revisions/r001/pages/0001.png",
  "image_sha256": "SHA-256 of the reviewed merged page"
 }
]
```

Coordinates are integer pixels on the complete English canvas, including any added margins. The origin is its top-left corner, x increases rightward and y increases downward. The selected pixels run from x to x + width and y to y + height, excluding the right and bottom bounds. Browser zoom and responsive display scaling do not change these coordinates. `image_path` is relative to the chapter project; it points to a manual preview when that was the reviewed image. The server checks dimensions, bounds and the reviewed-image state before saving.

Area IDs are local to the note. `[Area 2]` refers to `regions` entry `area-2`, even if Area 1 has been removed; array positions are not identities. New boxes reuse the lowest available number without renumbering remaining boxes. Ask the user to clarify a text reference whose area is missing. Older notes with a single `region` remain readable as one area. Notes without areas apply to the page or their stated text.

When acting on a note, open each area's `image_path`, verify its hash and inspect the rectangle with surrounding context. Match text references to the area's ID, then compare against the source and locate relevant transcript IDs or native regions; the box itself is not a transcript ID or a mask to paint in full. Carry the user's request into the next revision. If the page has changed, compare the recorded image with the current one before reusing its coordinates. Resolve the implemented fix through the normal review loop.

## Manual revisions during review

Export and import PSDs at any point in the review loop. Manual edits and agent changes can alternate; neither is reserved for finishing touches. Each changed PSD import creates a revision that can be compared, discussed and revised again.

Export PSD downloads the selected page. Its top-to-bottom stack is English text, cleanup paint, locked original. Text includes native lettering effects; paint is transparent outside native changes. The bundle also keeps transparent `text.png`. These are raster layers, not editable font objects. Layers reproduce the merged revision page pixel for pixel. No editor application is needed by the exporter.

The user saves an 8-bit RGB PSD with a merged compatibility preview, then drops it anywhere on the app or chooses Import PSD. Both routes import one file into the currently displayed page and revision; filenames do not select a different page. A drop hint identifies the target. The importer rejects multiple files, unsupported files and a page selection or image state that changed during selection or dragging. Importing a changed file preserves it and creates a new revision automatically. The app returns to Output selection for that page. If the user pinned an output version, it instead opens Latest for this page to show the imported preview while keeping the pin unchanged. An identical reimport leaves the revision and browsing mode unchanged. Import carries the other pages and existing manual overrides forward. The selected page uses the saved preview. Reimport after saving further changes. The CLI also accepts a matching PNG when a layered file is unnecessary:

```powershell
python -I -B manga.py import-edit chapter r002 0001 --from saved-page.psd
```

PSD import changes the selected page image; it does not recover editable font objects or synchronize `en.jsonl` from the PSD. The manual preview owns that page's displayed result. If manual wording also needs to enter the English records or glossary, review it with the user and incorporate it into the next agent revision when reconciling its native layout.

Only imported leaf revisions that are unpinned and not retained by a finished chapter or historical approval can be discarded in the app. Discard page revision appears only on the page identified by that import, and its confirmation names both the page and revision. The HTTP action also checks the page against the import receipt. Inherited copies on other pages never expose this action. Discarding a latest imported revision restores the previous completed version of its changed page; unrelated page choices stay intact. Agent forks and final work are retained. Discard is a user action, not automatic cleanup of their work.

## Page output choices and final flattened output

Each page follows its latest completed version by default. Agent renders update the history of their rendered pages; PSD imports update only the imported page, including imports based on an older revision. Carried-forward copies do not count as new versions of unchanged pages. Incomplete runs and translation-only drafts never become the latest output. Existing chapters begin at their current completed selection when no output history has been recorded yet.

The catalog identifies each revision's `changed_pages`, `parent` and optional `imported_page` from its render or import receipt. Legacy snapshots without page-change metadata remain available as full-page versions. The browser's Revision and Compare with lists show only completed versions that changed the current page. Labels count that page's retained versions consecutively, for example `Revision 2 (r012)`. The internal `r012` ID identifies the chapter snapshot and can skip numbers because other pages, drafts and earlier manual work share that namespace. Discarding the latest PSD version lets its replacement reuse the displayed page revision number. Latest for this page follows its own newest completed version, independently of the chapter's `current_revision`. Browsing an inherited snapshot resolves to the originating parent version for that page. Output selection still preserves an explicitly pinned snapshot, including older choices made before page-specific browsing.

The UI opens on Output selection. Its Final translation label explains that the latest revision will be exported by default and identifies the current revision for that page, independently of the revision being browsed. A pinned page instead names the revision selected by the user. Use this version for output stores a pin for the viewed page; Use latest removes it. A pin survives later agent and PSD revisions. The pin binds the exact merged image, manual status and any saved manual PSD, so changed files cannot silently replace it. Browsing and comparison never change output choices. A pinned revision cannot be discarded while selected.

`output.json` owns the completion history and explicit pins. The agent reads the same resolved selection as the app:

```powershell
python -I -B manga.py output chapter
```

The result lists each page's revision, project-relative image path, hash, manual status and whether it is pinned. When the user specifies a page choice in chat, record it with:

```powershell
python -I -B manga.py select-output chapter 0001 --revision r003
python -I -B manga.py select-output chapter 0001 --latest
```

The second command returns that page to its latest completed version. These commands change output selection, not revision content, and do not mark the chapter finished. Do not override an explicit user pin during ordinary agent revisions. Manual previews are part of their revision's page version; they do not permanently outrank newer agent renders.

Present the assembled output for review. When the user says the chapter is finished, ask whether they want the full output suite or only a ZIP of the flattened pages, unless their delivery preference is already known. The full suite includes ordered flattened PNGs, the chapter ZIP and available PSDs for the selected pages. ZIP-only delivery excludes editable files and separate PNG copies. Resolve outstanding notes and record their completion statement against that exact selection, then export the chosen format. The delivery question does not reopen chapter approval:

```powershell
python -I -B manga.py confirm-finished chapter --note "The user's statement that this assembled output is finished"
python -I -B manga.py finalize chapter --format full
```

Use `python -I -B manga.py finalize chapter --format zip` for ZIP-only delivery. Omitting `--format` keeps the full-suite default. If this selection and format have already been finalized, verify and reuse that release rather than generating another copy.

`output-finished.json` is the agent's record of the user's actual statement, not permission to infer completion. It binds selected page revisions, image and PSD hashes, audited source, English records, glossaries, style and relevant notes. Open transcript questions always block finishing. Page notes on an unselected version stay in history without blocking the chosen version. Changes to selected output invalidate that receipt. A newer unselected version of a pinned page does not. If selected pages change, present those changes to the user before recording completion again.

The immutable `final/<selection>/` contains the full suite: ordered flattened PNG pages, the chapter ZIP, a hash manifest and available selected PSDs. Native PSDs must match their verified page provenance; manual PSDs come from the selected import. ZIP-only releases use `final/<selection>-zip/` and contain only the chapter ZIP and its hash manifest. Both formats identify every page's revision, manual status, pin and project-relative source. Finalization verifies sources, dimensions, page count, copied files where present, ZIP integrity and each member hash, then updates `final/current.json`. Report only the requested delivery paths. Originals, native bundles and other working files stay in the project for continued editing. Chapter finalization does not publish the repository.
