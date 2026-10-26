// Pure selection state. UI and storage belong to the caller.
export function pageRevisions(project, pageId) {
  return project?.revisions.filter(revision => revision.complete !== false && revision.pages.some(page => page.id === pageId)
    && (!revision.changed_pages || revision.changed_pages.includes(pageId))) || [];
}

export function pageRevisionLabel(project, pageId, revisionId) {
  const index = pageRevisions(project, pageId).findIndex(revision => revision.id === revisionId);
  return index < 0 ? revisionId : `Revision ${index + 1} (${revisionId})`;
}

function revisionForPage(project, revisionId, pageId) {
  const versions = pageRevisions(project, pageId);
  const visited = new Set();
  let revision = project.revisions.find(item => item.id === revisionId);
  while (revision && !visited.has(revision.id)) {
    if (versions.includes(revision)) return revision;
    visited.add(revision.id);
    revision = project.revisions.find(item => item.id === revision.parent);
  }
}

export function canDiscardPage(revision, page, variant = '') {
  return Boolean(revision?.can_discard && revision.imported_page === page?.id && !variant);
}

export function createState(initial = {}) {
  let catalog = { projects: [] };
  let value = { project: '', revision: '', outputView: true, followLatest: true, page: '0001', baseline: 'source', variant: '', split: 50, ...initial };
  // Ignore the retired toggles in previously saved browser selections.
  delete value.manual;
  delete value.compare;
  const listeners = new Set();
  function selection() {
    const project = catalog.projects.find(item => item.id === value.project);
    const revision = project?.revisions.find(item => item.id === value.revision);
    const page = revision?.pages.find(item => item.id === value.page);
    return { value: { ...value }, catalog, project, revision, page };
  }
  function normalize() {
    const project = catalog.projects.find(item => item.id === value.project) || catalog.projects[0];
    if (!project) return;
    value.project = project.id;
    const pages = project.output?.pages.length ? project.output.pages
      : (project.revisions.find(item => item.id === project.current_revision) || project.revisions.at(-1))?.pages || [];
    if (!pages.some(item => item.id === value.page)) value.page = pages[0]?.id || '0001';
    const selected = project.output?.pages.find(item => item.id === value.page);
    const versions = pageRevisions(project, value.page);
    const latest = selected?.latest_revision || versions.at(-1)?.id;
    const requested = value.outputView && selected ? selected.revision : value.followLatest ? latest : value.revision;
    const revision = (value.outputView && selected ? project.revisions.find(item => item.id === requested)
      : revisionForPage(project, requested, value.page))
      || revisionForPage(project, latest, value.page) || versions.at(-1);
    value.revision = revision?.id || '';
    if (value.baseline !== 'source') value.baseline = revisionForPage(project, value.baseline, value.page)?.id || 'source';
    const page = revision?.pages.find(item => item.id === value.page);
    if (!page?.variants.some(item => item.url === value.variant)) value.variant = '';
    value.split = Math.max(0, Math.min(100, Number(value.split) || 0));
  }
  function emit() { normalize(); for (const listener of listeners) listener(selection()); }
  return {
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    select(patch) { value = { ...value, ...patch }; emit(); },
    update(next) { catalog = next; emit(); },
    current: selection,
  };
}
