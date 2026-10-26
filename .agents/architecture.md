# Workflow ownership

The parent repository owns chapter records and the review loop. The pinned `manga-translator-ui` submodule owns OCR, native inpainting, paste restoration and Qt text rendering. Parent adapters invoke those operations; they do not implement another image-painting engine.

## Instructions

| File | Owner and purpose |
| :--- | :--- |
| `PROMPT.md` | Coordinator behavior, progress updates, stage order and the user loop |
| `.agents/setup.md` | Parent tools and complete pinned engine environment |
| `.agents/workflow.md` | Commands, records, transitions and final selection |
| `manga-translation/SKILL.md` | Translation accuracy, fluency, voice and writing outputs |
| `lettering/SKILL.md` | Visual choices, masks, native metadata, fonts and page checks |
| `unslop/SKILL.md` | Prose cleanup, subordinate to source voice for translations |
| `code-guidelines/SKILL.md` | Explicitly invoked code and architecture changes, implementation constraints and verification |
| `profiles/lettering.json` | Preferred numerical/style defaults, overridden by reviewed page choices |
| `profiles/extract.json`, `render.json` | Native execution defaults |
| `profiles/editing.json` | PSD layer names/order, import mode and size limits |
| `commit-pipeline/SKILL.md` | Explicitly requested commits and pushes, including submodule updates and local pruning |

Skill paths above are under `.agents/skills/`. The coordinator reads the detailed resources when their stage needs them. The writing packet contains only writing inputs and skills, not implementation history or lettering instructions.

## Code

| Module | Responsibility |
| :--- | :--- |
| `files.py` | Chapter paths, JSON/JSONL, hashes and immutable-source checks |
| `workflow.py` | Source intake, transcript audit, writing packets, decisions, agent forks and render import |
| `output.py` | Completed page history, persistent output pins, resolved selection, finished-chapter receipt and flattened release |
| `native.py` | Native OCR metadata import and fresh extract/clean/render runs |
| `editing.py` | Native PSD bundles, saved-edit revisions, manual receipts and imported-revision discard |
| `review.py` | Catalog, verified downloads and asset allowlist |
| `server.py` | Loopback HTTP routes, request checks and mutation serialization |
| `cli.py` | Command parsing and dispatch to those owners |
| `tools/native_cleanup.py` | Stock native inpainting on reviewed masks |
| `tools/native_text_layers.py` | Stock Qt text rasters, native paste and FFmpeg layer assembly |
| `tools/psd.mjs` | Portable raster PSD serialization and saved merged-preview decoding |
| `web/state.js` | Selection state without DOM dependencies |
| `web/regions.js` | Page-note rectangle drawing and full-resolution coordinate conversion |
| `web/app.js`, `theme.js` | Review interactions and appearance |
| `web/index.html`, `global.css`, `review.css` | Interface structure and styling |

The server serves only named UI files and cataloged chapter assets on loopback. Heavy native runs happen outside HTTP handlers. The browser displays merged pages; it does not render PSD font layers or perform native inpainting.

The review catalog tracks the metadata and assets it displays, reuses unchanged page records and caches hashes against filesystem identity, size and timestamps. Polling returns an unchanged response when the catalog version matches. Agent renders, output history and addressed-note records are discovered by the same polling path; visible pages and notes update without a reload, while historical browsing and output pins keep their meaning. Versioned images use the browser cache, and adjacent page images are prefetched within a bounded decoded-image cache. Asset downloads stream without rebuilding the catalog or holding the mutation lock.

## Chapter records

The bundled `projects/cosmos-5-final/` chapter, 秋桜が咲いた日に 第5-終わり話, is a review/export reference. Its historical pages, manual edits and final output are retained, but its native OCR mappings and reviewed layouts are not included. Use a new chapter for transcript extraction, translation and native rendering; do not resume agent rendering from this reference snapshot.

```text
projects/<chapter>/
  project.json                    Ordered source manifest and current revision
  output.json                     Completed page history and explicit output choices
  output-finished.json            User's completion statement bound to the resolved output
  source/                         Preserved archive and original page copies
  transcript/                     Raw/checked JSONL, page coverage and visual audit
  glossary.json, issues.json       Shared terms and recorded decisions/notes
  handoffs/<revision>/            Bounded writer inputs and outputs
  native/ocr/                     Preserved native extraction metadata
  native/region-map.json          Transcript IDs mapped to page/region indexes
  native/layouts/<revision>/      Page geometry, masks, cleanup choices and preflight
  work/<run>/                     Fresh inputs, native outputs and execution receipts
  revisions/<revision>/           English, glossary, merged pages and native PSD bundles
  manual/<revision>/              Saved user files, merged previews and import receipts
  final/<selection>/              Immutable flattened release, ZIP and hash manifest
  final/current.json              Latest finalized selection
```

An agent fork records `parent.json`; a saved-edit revision records `import.json`. Partial render import inherits unchanged native bundles and manual overrides from its parent. Re-rendered pages replace only their new revision's selected images. Completed page versions enter output history without changing explicit pins or marking the chapter finished. Source corrections never overwrite raw extraction.

Stored PNGs and PSDs in revision snapshots are immutable. Imports and partial agent revisions share unchanged rasters through filesystem hard links when supported, falling back to copies on other filesystems. Metadata is copied independently. A changed page or PSD replaces its directory entry before saving new bytes; never modify a shared stored raster in place. Exported PSD downloads remain independent files for the user's editor. Import staging and uploads have cleanup on success, identical reimport and failure; persistent OS locks can leave temporary files for later cleanup. Existing historical work is retained. Atomic JSON writes use unique temporary files and bounded retries for transient Windows sharing violations.

Output selection resolves each page independently. Completed agent renders update only their rendered pages; PSD imports update only the imported page. A user's pinned revision overrides that page's latest history and binds its exact merged image and any manual PSD. Browsing does not write output choices. The browser and agent commands read the same resolver. No revision approval button is involved.

The user's completion statement binds the resolved page versions, audited source, selected English records, glossaries, profile, notes and file hashes. Delivery format is separate: the full suite contains PNGs, a ZIP and available selected PSDs; ZIP-only output contains the flattened-page archive and a manifest. The final manifest records the revision and source path for every page. Changing selected output makes that completion receipt stale; an unselected newer version of a pinned page does not. Technical checks establish file consistency; the user decides when the chapter is finished. Historical revision approval files remain readable for retention of existing work.

`.runtime/` contains installed environments, native caches and temporary uploads or server logs. It is not part of the chapter record. `.gitmodules` plus the parent Git gitlink identify the engine; dependency setup preserves that pin. The commit-pipeline owns `.exclusion-config` and applies its reversible local sparse checkout during preparation. An explicitly requested commit or push updates submodules from upstream first, reapplies the exclusions, then reviews the engine change before committing its new gitlink. Chapter translation and finalization do not trigger commits or pushes.
