# Translate and review a chapter

You coordinate the chapter from source intake to the final flattened pages. Start by telling the user what you are doing. Give updates before each stage and during long operations, then report the result and the next step. Do not leave a render, download or extraction running without progress updates.

## Set up before processing

Follow [setup](.agents/setup.md) first. Check the parent tools and the complete pinned submodule environment, install missing prerequisites and dependencies, and test the actual engine interpreter. An existing folder or a working review server does not prove that OCR and inpainting are installed. Reuse a working environment; repeat setup only when dependencies, the engine pin or the machine changed.

Run `manga.py status` and inspect the source location already supplied. Resume an initialized chapter without importing its originals again. If the source has not been provided, ask the user to place the archive or scans folder in `input/<chapter>/`, or give its existing path. Skip that request when the files are already available. Confirm unclear chapter boundaries or page order before processing. Preserve source bytes and keep all chapter work under its project.

## Extract, check and translate

Use [the workflow](.agents/workflow.md) for the commands and file contracts.

1. Initialize the source manifest and run extraction. Import the native results into JSONL, then compare the transcript with every source page in order. Include small effects and margins; record textless pages in coverage.
2. Correct visually certain OCR mistakes in the checked transcript. Keep raw extraction untouched. Present unresolved readings, names, speakers or meanings to the user with the relevant image and a proposed reading. Record their decisions, then finish the visual transcript audit before translation.
3. Create a translation handoff. Give a writing agent only the generated packet's `TASK.md` path and translation-only scope. It reads the copied writing skills, works in context, and returns English, glossary, questions and its separate accuracy/fluency reviews. If delegation is unavailable, perform this bounded writing step yourself. Keep engine and implementation work out of that step.
4. Import the writing outputs. Discuss material ambiguities and intentional departures with the user. If a question changes the source transcript, return to its audit and make a fresh handoff. Continue independent work while awaiting an answer, without deciding the disputed reading yourself.

## Letter and present the first revision

Use [the lettering skill](.agents/skills/lettering/SKILL.md) for masks, fonts, balloons, effects, prose and credits. It owns visual choices; the translation skill owns wording. Prepare the native layouts, run cleanup, inspect its result, then render and import the separate original, paint and English text rasters. Keep the three-layer PSDs available alongside every new rendered page.

Start or reuse the loopback review app yourself and give the user its actual URL. Open it for the user when browser tools are available; do not ask them to run a launcher or terminal command. Present the chapter through Output selection after its first pages and PSDs are ready. Explain comparison, Append note, Remove note, Export PSD, PSD drag and drop or Import PSD, Use this version for output and Use latest. Appending a note saves feedback; it does not start a revision. PSD layers are edited in the user's image editor; the browser displays the merged page.

## Repeat the review loop

Read feedback from chat and the chapter's open review notes. A note can include selected `regions`; use the workflow's area IDs and coordinate contract to inspect its exact reviewed page and locate each issue before editing. Fork an agent revision for changes, update wording and layouts as needed, and import the changed pages. Unchanged rendered pages and manual overrides carry forward. If a page with manual retouching needs a new render, preserve those repairs in its native base where possible and tell the user when that page is being superseded. The parent revision retains their prior file.

At any point during review, the user can export a layered PSD, revise a page manually and import it. A changed PSD automatically creates a new revision and a preview for continued review. It must be saved as 8-bit RGB with a merged compatibility image. Manual and agent revisions can alternate; manual editing is not limited to finishing touches. The app uses manual previews where present and revision pages for the rest.

After importing and checking a revised page, mark each implemented visual note as addressed through the workflow's resolve command. Identify the completed revision containing the fix and explain what changed for the note's specific areas or wording. The app shows that response and links to the addressed page. Skip notes the user removed; removal withdraws a request without claiming it was fixed. Each page follows its latest completed render or PSD import unless the user pins a specific version for output. Honor those page choices across revisions. Browsing another revision does not change them. Read the resolved output through the workflow's `output` command; present that assembled selection and repeat revisions until the user says the chapter is finished. There is no revision approval button, and choosing a page version does not finish the chapter.

## Finish

When the user says the chapter is finished, ask whether they want the full output suite (ordered flattened PNGs, chapter ZIP and available selected PSDs) or just the flattened pages in a ZIP, unless they have already specified their preference. This is a delivery choice, not another approval of the chapter. Record their completion statement against the exact resolved output, including all page choices and manual edits, then finalize with the chosen format using the workflow commands. If the selected output changes after that statement, present the changed pages before recording completion again. Verify hashes and page count, then give the user the requested delivery paths. For ZIP-only delivery, link the ZIP without adding source or editable files to the deliverable. Originals, revision layers and manual working files remain available in the project. Do not publish, upload or push the repository as part of chapter finalization.

Keep skill and guide prose as one source line per paragraph. Do not hard-wrap paragraphs or add manual indentation. Preserve Markdown lists, tables, code blocks and intentional lettering breaks.
