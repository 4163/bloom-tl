import './theme.js';
import { createState, pageRevisions, pageRevisionLabel, canDiscardPage } from './state.js';
import { createRegionTool } from './regions.js';

const byId = id => document.getElementById(id);
const frame = byId('comparison');
const regionTool = createRegionTool({ frame, button: byId('mark-area'), clearButton: byId('clear-area'),
  status: byId('region-status'), overlay: byId('note-region'), label: byId('note-area-label'),
  list: byId('region-list'), noteButton: byId('write-note'), references: byId('note-areas'),
  onSelect: () => byId('note').focus(),
  onReference: id => {
    const note = byId('note');
    const prefix = note.selectionStart && !/\s/.test(note.value[note.selectionStart - 1]) ? ' ' : '';
    note.setRangeText(`${prefix}[Area ${id.slice(5)}] `, note.selectionStart, note.selectionEnd, 'end');
    note.focus();
  },
});
let restored = {};
try { restored = JSON.parse(localStorage.getItem('manga-translation.review')) || {}; } catch {}
const state = createState(restored);
let catalogVersion = '', token = '', drag = null, bounds, lastImage = '', pending = false;
let imageGeneration = 0;
let split = 50;
let fileSelection = null;
let dropSelection = null, fileDragDepth = 0;
let catalogRequest = null;
let mutationGeneration = 0;
let renderedSelection = '';
const imageCache = new Map();
function loadImage(url) {
  let entry = imageCache.get(url);
  if (!entry) {
    const image = new Image();
    image.src = url;
    entry = { image, ready: image.decode() };
    imageCache.set(url, entry);
    entry.ready.catch(() => imageCache.delete(url));
    while (imageCache.size > 6) imageCache.delete(imageCache.keys().next().value);
  }
  return entry.ready;
}
const resize = new ResizeObserver(() => { bounds = frame.getBoundingClientRect(); });
resize.observe(frame);

function editStatus(text, error = false) {
  byId('edit-status').textContent = text;
  byId('edit-status').dataset.error = String(error);
}
function selectionKey(value) { return `${value.project}/${value.revision}/${value.page}`; }
function importTarget() {
  const { value, page, revision } = state.current();
  if (pending || !page || !revision.complete || value.variant || frame.dataset.loading === 'true' || frame.dataset.error === 'true') return null;
  return { key: selectionKey(value), expected: page.edit_state };
}
function showNotePage(project, revision, pageId, imageHash) {
  const page = project.revisions.find(item => item.id === revision)?.pages.find(item => item.id === pageId);
  if (!page || page.review_image_sha256 !== imageHash) {
    editStatus('This note refers to a page image that is no longer available. Give the agent its recorded revision and image path.', true);
    return false;
  }
  state.select({ revision, page: pageId, outputView: false, followLatest: false, variant: '', split: 0 });
  return true;
}
function paintSplit(value) {
  split = Math.max(0, Math.min(100, Number(value) || 0));
  frame.style.setProperty('--split', `${split}%`);
  byId('scrub').value = split;
  byId('scrub').setAttribute('aria-valuetext', `${Math.round(split)}% comparison, ${Math.round(100 - split)}% English`);
}
function options(id, items, selected) {
  const select = byId(id);
  const signature = JSON.stringify(items);
  if (select.dataset.options !== signature) {
    const template = byId('option-template');
    const nodes = items.map(([value, label]) => {
      const option = template.content.firstElementChild.cloneNode(true);
      option.value = value; option.textContent = label;
      return option;
    });
    select.replaceChildren(...nodes);
    select.dataset.options = signature;
  }
  select.value = selected;
}
async function images(english, original, size, baselineWidth) {
  const signature = `${english}|${original}|${size}|${baselineWidth}`;
  if (signature === lastImage) return;
  lastImage = signature;
  const generation = ++imageGeneration;
  frame.dataset.loading = 'true';
  frame.dataset.error = 'false';
  try {
    await Promise.all([loadImage(english), loadImage(original)]);
    if (generation !== imageGeneration) return;
    frame.style.setProperty('--page-ratio', size[0] / size[1]);
    frame.style.setProperty('--page-width', `${size[0]}px`);
    frame.style.setProperty('--baseline-width', `${baselineWidth}%`);
    byId('english').width = size[0];
    byId('english').height = size[1];
    byId('english').src = english;
    byId('original').src = original;
    frame.dataset.loading = 'false';
    render(state.current());
    const { value, project, revision, page } = state.current();
    const index = revision?.pages.indexOf(page);
    for (const adjacent of [revision?.pages[index - 1], revision?.pages[index + 1]]) {
      if (!adjacent) continue;
      const output = project.output?.pages.find(item => item.id === adjacent.id);
      const revisionId = value.outputView ? output?.revision : value.followLatest ? output?.latest_revision : revision.id;
      const next = project.revisions.find(item => item.id === revisionId)?.pages.find(item => item.id === adjacent.id) || adjacent;
      const comparison = project.revisions.find(item => item.id === value.baseline)?.pages.find(item => item.id === adjacent.id);
      loadImage(next.manual || next.english).catch(() => {});
      loadImage(comparison?.manual || comparison?.english || next.source).catch(() => {});
    }
  } catch {
    if (generation === imageGeneration) {
      frame.dataset.loading = 'false';
      frame.dataset.error = 'true';
      byId('select-output').disabled = true;
      editStatus('A page could not load. Check the render and source files.', true);
      lastImage = '';
    }
  }
}
function render({ value, catalog, project, revision, page }) {
  try { localStorage.setItem('manga-translation.review', JSON.stringify(value)); } catch {}
  const versions = pageRevisions(project, value.page);
  const revisionLabel = id => pageRevisionLabel(project, value.page, id);
  const revisionOptions = versions.map(item => [item.id, revisionLabel(item.id)]);
  options('chapter', catalog.projects.map(item => [item.id, item.title]), value.project);
  options('revision', project ? [['__output__', 'Output selection'], ['__current__', 'Latest for this page'], ...revisionOptions] : [], value.outputView ? '__output__' : value.followLatest ? '__current__' : value.revision);
  options('page', revision?.pages.map(item => [item.id, item.id]) || [], value.page);
  options('baseline', [['source', 'Original'], ...revisionOptions], value.baseline);
  for (const id of ['chapter', 'revision', 'page', 'baseline', 'variant', 'append-note']) byId(id).disabled = pending;
  if (!page) {
    regionTool.setPage('', null, '', false);
    for (const id of ['append-note', 'select-output', 'export-psd', 'import-edit', 'discard-revision']) byId(id).disabled = true;
    byId('latest-output').hidden = true;
    byId('output-status').textContent = 'Final translation: waiting for completed pages';
    byId('discard-label').hidden = true;
    editStatus('No rendered pages yet. Import a revision to review it.'); return;
  }
  if (renderedSelection !== selectionKey(value)) {
    renderedSelection = selectionKey(value);
    editStatus('');
  }
  options('variant', [['', 'Revision page'], ...page.variants.map(item => [item.url, item.label])], value.variant);
  byId('variant-label').hidden = !page.variants.length;
  const english = value.variant || page.manual || page.english;
  const previous = project.revisions.find(item => item.id === value.baseline)?.pages.find(item => item.id === page.id);
  const baseline = previous?.manual || previous?.english || page.source;
  const index = revision.pages.indexOf(page);
  byId('previous').disabled = pending || index === 0;
  byId('next').disabled = pending || index === revision.pages.length - 1;
  byId('reference').textContent = `${project.id} / ${revisionLabel(revision.id)} / ${page.id}`;
  byId('heading').textContent = `Page ${index + 1} of ${revision.pages.length}`;
  const showingManual = page.manual && !value.variant;
  const psd = showingManual ? page.manual_psd : page.psd;
  const psdLink = byId('psd-link');
  if (psd && !value.variant) {
    psdLink.href = psd;
    psdLink.download = `${project.id}-${revision.id}-${page.id}.psd`;
  } else {
    psdLink.removeAttribute('href');
  }
  byId('export-psd').disabled = pending || !psd || Boolean(value.variant);
  const canDiscard = canDiscardPage(revision, page, value.variant);
  byId('discard-label').hidden = !canDiscard;
  byId('discard-revision').disabled = pending || !canDiscard;
  byId('discard-revision').title = `Discard ${revisionLabel(revision.id)} for page ${page.id}`;
  byId('discard-revision').setAttribute('aria-label', `Discard ${revisionLabel(revision.id)} for page ${page.id}`);
  byId('editable-status').hidden = Boolean(psd) && !value.variant;
  byId('left-label').textContent = previous ? revisionLabel(value.baseline) : 'Original';
  if (drag === null) paintSplit(value.split);
  images(english, baseline, page.canvas_size, previous ? 100 : page.source_width / page.canvas_size[0] * 100);
  byId('import-edit').disabled = !importTarget();
  regionTool.setPage(`${selectionKey(value)}/${value.variant}`, page.canvas_size, page.edit_state,
    !pending && !value.variant && frame.dataset.loading !== 'true' && frame.dataset.error !== 'true');
  const notes = project.issues.filter(item => item.status !== 'removed');
  const open = notes.filter(item => item.status === 'open');
  const outputPage = project.output?.pages.find(item => item.id === page.id);
  const pinnedHere = outputPage?.pinned && outputPage.revision === revision.id && outputPage.sha256 === page.review_image_sha256;
  byId('output-status').textContent = project.output?.error ? `Final translation: ${project.output.error}`
    : outputPage ? outputPage.pinned ? `Final translation will use ${revisionLabel(outputPage.revision)} for this page, as selected by you.`
      : `Final translation will use this page’s latest revision: ${revisionLabel(outputPage.revision)}.`
      : 'Final translation: waiting for completed pages';
  byId('select-output').textContent = pinnedHere ? 'Selected for output' : 'Use this version for output';
  byId('select-output').disabled = pending || frame.dataset.loading === 'true' || frame.dataset.error === 'true'
    || Boolean(value.variant) || !revision.complete || !project.output?.selection || pinnedHere;
  byId('latest-output').hidden = !outputPage?.pinned;
  byId('latest-output').disabled = pending;
  byId('latest-output').title = outputPage?.latest_revision ? `Use latest: ${revisionLabel(outputPage.latest_revision)}` : 'Use latest';
  byId('question-count').textContent = `${open.length} open review note${open.length === 1 ? '' : 's'}`;
  const signature = JSON.stringify([project.id, notes]);
  if (byId('questions').dataset.items !== signature) {
    byId('questions').replaceChildren(...notes.map(item => {
      const node = byId('question-template').content.firstElementChild.cloneNode(true);
      const status = item.status === 'resolved' ? 'Addressed by agent' : item.status === 'accepted' ? 'Decision recorded' : 'Open';
      node.querySelector('.question-ref').textContent = `${item.id} / ${item.record} / ${item.revision || 'chapter'} / ${status}`;
      node.querySelector('.question-text').textContent = item.question;
      const response = node.querySelector('.question-resolution');
      response.hidden = !item.decision;
      response.textContent = item.decision ? `${item.addressed_revision ? `Addressed in ${item.addressed_revision}`
        : item.decided_by === 'agent' ? 'Agent response' : 'User decision'}: ${item.decision}` : '';
      const showArea = node.querySelector('.show-area');
      const areas = item.regions || (item.region ? [item.region] : []);
      showArea.hidden = !areas.length;
      showArea.disabled = pending;
      showArea.textContent = areas.length === 1 ? 'Show area' : 'Show areas';
      showArea.addEventListener('click', () => {
        if (pending) return;
        if (showNotePage(state.current().project, item.revision, item.record, areas[0].image_sha256)) regionTool.show(areas);
      });
      const showFix = node.querySelector('.show-fix');
      showFix.hidden = !item.addressed_revision;
      showFix.disabled = pending;
      showFix.addEventListener('click', () => {
        if (!pending && showNotePage(state.current().project, item.addressed_revision, item.record, item.addressed_image_sha256)) {
          document.querySelector('.review-heading').scrollIntoView({ behavior: 'instant', block: 'start' });
        }
      });
      const remove = node.querySelector('.remove-note');
      remove.hidden = item.stage !== 'visual';
      remove.disabled = pending;
      remove.setAttribute('aria-label', `Remove note ${item.id}`);
      remove.addEventListener('click', async () => {
        if (!pending && await action('/api/remove-note', { project: project.id, issue: item.id })) editStatus('Note removed.');
      });
      return node;
    }));
    byId('questions').dataset.items = signature;
  }
  for (const button of byId('questions').querySelectorAll('button')) button.disabled = pending;
}
state.subscribe(render);

function fetchCatalog() {
  if (!catalogRequest) {
    catalogRequest = fetch('/api/catalog', { cache: 'no-store', headers: catalogVersion ? { 'If-None-Match': `"${catalogVersion}"` } : {} }).then(response => {
      if (response.status === 304) return null;
      if (!response.ok) throw new Error('Catalog unavailable');
      return response.json();
    }).finally(() => { catalogRequest = null; });
  }
  return catalogRequest;
}
function applyCatalog(next) {
  if (!next) return;
  token = next.token;
  if (catalogVersion !== next.version) { catalogVersion = next.version; state.update(next); }
}
async function reloadCatalog() {
  // A request started before the write may still contain the previous selection.
  if (catalogRequest) await catalogRequest;
  applyCatalog(await fetchCatalog());
}
async function refresh() {
  try {
    const generation = mutationGeneration;
    const next = await fetchCatalog();
    if (!pending && generation === mutationGeneration) applyCatalog(next);
  } catch {
    catalogVersion = '';
  }
  setTimeout(refresh, document.hidden ? 5000 : 1500);
}
async function action(url, payload) {
  mutationGeneration++;
  pending = true;
  render(state.current());
  try {
    const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Review-Token': token }, body: JSON.stringify(payload) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    if (url === '/api/issues' || url === '/api/remove-note') {
      const current = state.current().catalog;
      state.update({ ...current, projects: current.projects.map(project => project.id !== payload.project ? project
        : { ...project, issues: project.issues.some(item => item.id === result.id)
          ? project.issues.map(item => item.id === result.id ? result : item) : [...project.issues, result] }) });
    } else {
      catalogVersion = '';
      await reloadCatalog();
    }
    editStatus('Saved.');
    return true;
  } catch (error) { editStatus(error.message, true); return false; }
  finally { pending = false; render(state.current()); }
}
function step(direction) {
  if (pending) return;
  const { value, revision } = state.current();
  const index = revision?.pages.findIndex(item => item.id === value.page);
  const page = revision?.pages[index + direction];
  if (page) { state.select({ page: page.id, variant: '' }); window.scrollTo(0, 0); }
}
for (const [id, key] of [['chapter', 'project'], ['page', 'page'], ['baseline', 'baseline'], ['variant', 'variant']]) {
  byId(id).addEventListener('change', event => state.select({ [key]: event.target.value }));
}
byId('revision').addEventListener('change', event => state.select(event.target.value === '__output__'
  ? { outputView: true } : event.target.value === '__current__'
    ? { outputView: false, followLatest: true } : { outputView: false, followLatest: false, revision: event.target.value }));
byId('scrub').addEventListener('input', event => { regionTool.compare(); paintSplit(event.target.value); });
byId('scrub').addEventListener('change', () => state.select({ split }));
byId('reset').addEventListener('click', () => { regionTool.compare(); state.select({ split: 50 }); });
byId('previous').addEventListener('click', () => step(-1));
byId('next').addEventListener('click', () => step(1));
frame.addEventListener('pointerdown', event => {
  if (regionTool.active || pending || frame.dataset.loading === 'true' || !event.isPrimary || event.button !== 0) return;
  bounds = frame.getBoundingClientRect(); drag = event.pointerId; frame.setPointerCapture(drag);
  paintSplit((event.clientX - bounds.left) / bounds.width * 100);
});
frame.addEventListener('pointermove', event => {
  if (drag === event.pointerId && bounds?.width) paintSplit((event.clientX - bounds.left) / bounds.width * 100);
});
function endDrag(event) {
  if (drag !== event.pointerId) return;
  drag = null;
  if (frame.hasPointerCapture(event.pointerId)) frame.releasePointerCapture(event.pointerId);
  state.select({ split });
}
frame.addEventListener('pointerup', endDrag);
frame.addEventListener('pointercancel', endDrag);
frame.addEventListener('lostpointercapture', endDrag);
frame.addEventListener('dblclick', () => { if (!regionTool.active) state.select({ split: 50 }); });
document.addEventListener('keydown', event => {
  if (['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(event.target.tagName)) return;
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); step(event.key === 'ArrowLeft' ? -1 : 1); }
});
byId('note-form').addEventListener('submit', async event => {
  event.preventDefault(); if (pending) return;
  const { value } = state.current();
  if (await action('/api/issues', { project: value.project, revision: value.revision, page: value.page,
    note: byId('note').value, regions: regionTool.draft() })) {
    byId('note').value = ''; regionTool.clear();
  }
});
byId('select-output').addEventListener('click', async () => {
  if (pending) return;
  const { project, revision, page } = state.current();
  await action('/api/output-choice', { project: project.id, page: page.id, revision: revision.id,
    selection: project.output.selection, image_sha256: page.review_image_sha256 });
});
byId('latest-output').addEventListener('click', async () => {
  if (pending) return;
  const { project, page } = state.current();
  await action('/api/output-choice', { project: project.id, page: page.id, revision: null, selection: project.output.selection });
});
byId('export-psd').addEventListener('click', () => byId('psd-link').click());
byId('import-edit').addEventListener('click', () => {
  fileSelection = importTarget();
  if (!fileSelection) return;
  byId('edit-file').value = '';
  byId('edit-file').click();
});
async function importPsd(file, target) {
  if (pending) return;
  if (!file) return;
  const { value, page } = state.current();
  if (!importTarget() || target?.key !== selectionKey(value) || target.expected !== page.edit_state) {
    editStatus('The page or revision changed. Review it, then choose or drop the PSD again.', true); return;
  }
  if (!file.name.toLowerCase().endsWith('.psd')) { editStatus('Choose a saved PSD file.', true); return; }
  if (!file.size || file.size > 512 * 1024 * 1024) { editStatus('Import a nonempty PSD no larger than 512 MiB.', true); return; }
  pending = true;
  mutationGeneration++;
  render(state.current());
  editStatus('Importing your PSD and reading its preview.');
  try {
    const response = await fetch('/api/import', { method: 'POST', body: file, headers: {
      'Content-Type': 'application/octet-stream', 'X-Review-Token': token,
      'X-File-Name': encodeURIComponent(file.name), 'X-Project': value.project,
      'X-Revision': value.revision, 'X-Page': value.page,
      'X-Edit-State': target.expected,
    } });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    byId('edit-file').value = ''; fileSelection = null; catalogVersion = '';
    await reloadCatalog();
    const pinned = state.current().project.output?.pages.find(item => item.id === value.page)?.pinned;
    state.select({ revision: result.revision, outputView: result.created ? !pinned : value.outputView,
      followLatest: result.created ? true : value.followLatest, variant: '' });
    editStatus(result.created ? `PSD imported for page ${value.page}. Saved as ${pageRevisionLabel(state.current().project, value.page, result.revision)}.${pinned ? ' Your selected final-output version stays in place.' : ''}`
      : 'This PSD is already saved in this revision.');
  } catch (error) { editStatus(error.message, true); }
  finally { pending = false; render(state.current()); }
}
byId('edit-file').addEventListener('change', () => importPsd(byId('edit-file').files[0], fileSelection));

function fileDrag(event) { return Array.from(event.dataTransfer?.types || []).includes('Files'); }
function clearFileDrag() {
  fileDragDepth = 0; dropSelection = null; byId('psd-drop-hint').hidden = true;
}
document.addEventListener('dragenter', event => {
  if (!fileDrag(event)) return;
  event.preventDefault();
  if (fileDragDepth++ === 0) dropSelection = importTarget();
  const { value } = state.current();
  byId('psd-drop-hint').firstElementChild.textContent = dropSelection
    ? `Drop one PSD to revise page ${value.page} (${value.revision}). Changes save as a new revision.`
    : pending ? 'Wait for the current action to finish before importing a PSD.' : 'Open a completed page before importing a PSD.';
  byId('psd-drop-hint').hidden = false;
});
document.addEventListener('dragover', event => {
  if (!fileDrag(event)) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = importTarget() ? 'copy' : 'none';
});
document.addEventListener('dragleave', event => {
  if (fileDragDepth && --fileDragDepth === 0) clearFileDrag();
});
document.addEventListener('drop', event => {
  if (!fileDrag(event)) return;
  event.preventDefault();
  const target = dropSelection || importTarget();
  const files = Array.from(event.dataTransfer.files);
  clearFileDrag();
  if (pending) { editStatus('Wait for the current action to finish before importing a PSD.', true); return; }
  if (files.length !== 1) { editStatus('Drop one PSD for the currently displayed page.', true); return; }
  importPsd(files[0], target);
});
window.addEventListener('blur', clearFileDrag);
document.addEventListener('keydown', event => { if (event.key === 'Escape') clearFileDrag(); });
byId('discard-revision').addEventListener('click', async () => {
  if (pending) return;
  const { project, revision, page, value } = state.current();
  if (!canDiscardPage(revision, page, value.variant)) return;
  if (!window.confirm(`Discard ${pageRevisionLabel(project, page.id, revision.id)} for page ${page.id}? This removes the imported PSD and preview for this page. Other pages keep their versions.`)) return;
  pending = true;
  mutationGeneration++;
  render(state.current());
  editStatus(`Discarding ${revision.id}...`);
  try {
    const response = await fetch('/api/discard-revision', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Review-Token': token },
      body: JSON.stringify({ project: project.id, revision: revision.id, page: page.id })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    catalogVersion = '';
    await reloadCatalog();
    state.select({ outputView: true, followLatest: true, variant: '' });
    editStatus(`Discarded ${result.discarded} for page ${page.id}. Showing the final translation selection.`);
  } catch (error) {
    editStatus(error.message, true);
  } finally {
    pending = false;
    render(state.current());
  }
});
refresh();
document.addEventListener('visibilitychange', () => {
  const generation = mutationGeneration;
  if (!document.hidden) fetchCatalog().then(next => { if (!pending && generation === mutationGeneration) applyCatalog(next); }).catch(() => {});
});
