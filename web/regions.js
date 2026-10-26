// Rectangles use the complete English canvas, independent of browser scaling.
export function pixelBox(start, end, size) {
  const clamp = value => Math.max(0, Math.min(1, value));
  const left = Math.floor(clamp(Math.min(start.x, end.x)) * size[0]);
  const top = Math.floor(clamp(Math.min(start.y, end.y)) * size[1]);
  const right = Math.ceil(clamp(Math.max(start.x, end.x)) * size[0]);
  const bottom = Math.ceil(clamp(Math.max(start.y, end.y)) * size[1]);
  return { x: left, y: top, width: right - left, height: bottom - top };
}

export function createRegionTool({ frame, button, clearButton, status, overlay, label, list, noteButton, references, onSelect, onReference }) {
  let context = { key: '', size: [1, 1], imageState: '', enabled: false };
  let selected = [], saved = false, preview = null, marking = false, pointer = null;
  let previewFrame = null;
  function nextAreaId() {
    const used = new Set(selected.map(box => box.id));
    let number = 1;
    while (used.has(`area-${number}`)) number++;
    return `area-${number}`;
  }

  function draw() {
    button.disabled = !context.enabled;
    button.setAttribute('aria-pressed', String(marking));
    frame.dataset.marking = String(marking);
    frame.setAttribute('aria-label', marking ? 'Draw a box for your page note' : 'Drag horizontally to compare the page');
    overlay.hidden = !selected.length && !preview;
    clearButton.hidden = !selected.length;
    clearButton.disabled = !context.enabled;
    noteButton.hidden = !selected.length || saved;
    noteButton.disabled = !context.enabled;
    label.hidden = !selected.length || saved;
    label.textContent = `· ${selected.length} area${selected.length === 1 ? '' : 's'} attached`;
    status.textContent = saved ? `Showing ${selected.length} saved area${selected.length === 1 ? '' : 's'}.`
      : selected.length ? `${selected.length} area${selected.length === 1 ? '' : 's'} attached.${marking ? ' Draw another or write your note.' : ''}`
        : marking ? 'Drag boxes on the English page. Esc cancels.' : 'Optional areas for your page note.';
    drawOverlay();
    list.replaceChildren(...(saved ? [] : selected.map(box => {
      const remove = document.createElement('button');
      remove.type = 'button'; remove.className = 'area-chip quiet';
      remove.textContent = `Area ${box.id.slice(5)} ×`;
      remove.setAttribute('aria-label', `Remove area ${box.id.slice(5)}`);
      remove.title = `Remove area ${box.id.slice(5)}: x ${box.x}, y ${box.y}, width ${box.width}, height ${box.height} pixels`;
      remove.disabled = !context.enabled;
      remove.addEventListener('click', () => removeArea(box.id));
      return remove;
    })));
    references.hidden = !selected.length || saved;
    references.replaceChildren(...(saved ? [] : selected.map(box => {
      const object = document.createElement('div');
      object.className = 'area-reference-object';
      const reference = document.createElement('button');
      reference.type = 'button'; reference.className = 'area-reference';
      reference.textContent = `Area ${box.id.slice(5)} · x ${box.x}, y ${box.y} · ${box.width} × ${box.height} px`;
      reference.setAttribute('aria-label', `Insert Area ${box.id.slice(5)} reference`);
      reference.title = 'Insert this area’s label into your note';
      reference.disabled = !context.enabled;
      reference.addEventListener('click', () => onReference(box.id));
      const remove = document.createElement('button');
      remove.type = 'button'; remove.className = 'area-reference-remove';
      remove.textContent = '×';
      remove.setAttribute('aria-label', `Remove area ${box.id.slice(5)}`);
      remove.title = `Remove area ${box.id.slice(5)}`;
      remove.disabled = !context.enabled;
      remove.addEventListener('click', () => removeArea(box.id));
      object.append(reference, remove);
      return object;
    })));
  }
  function drawOverlay() {
    overlay.hidden = !selected.length && !preview;
    overlay.replaceChildren(...[...selected, ...(preview ? [{ ...preview, id: nextAreaId() }] : [])].map(box => {
      const node = document.createElement('div');
      node.className = 'note-region';
      node.style.left = `${box.x / context.size[0] * 100}%`;
      node.style.top = `${box.y / context.size[1] * 100}%`;
      node.style.width = `${box.width / context.size[0] * 100}%`;
      node.style.height = `${box.height / context.size[1] * 100}%`;
      const number = document.createElement('span');
      number.className = 'region-number'; number.textContent = box.id.slice(5);
      node.append(number); return node;
    }));
  }
  function removeArea(id) {
    const index = selected.findIndex(box => box.id === id);
    if (index >= 0) selected.splice(index, 1);
    draw();
  }
  function stopDrag() {
    if (previewFrame !== null) cancelAnimationFrame(previewFrame);
    previewFrame = null;
    const previous = pointer;
    pointer = null; preview = null;
    if (previous) {
      if (frame.hasPointerCapture(previous.id)) frame.releasePointerCapture(previous.id);
    }
  }
  function clear() {
    stopDrag(); selected = []; saved = false; marking = false; draw();
  }
  function point(event) {
    const bounds = frame.getBoundingClientRect();
    return { x: (event.clientX - bounds.left) / bounds.width, y: (event.clientY - bounds.top) / bounds.height };
  }
  button.addEventListener('click', () => {
    if (!context.enabled) return;
    stopDrag(); marking = !marking;
    if (marking && saved) { selected = []; saved = false; }
    draw();
    if (marking) frame.focus({ preventScroll: true });
  });
  clearButton.addEventListener('click', clear);
  noteButton.addEventListener('click', onSelect);
  frame.addEventListener('pointerdown', event => {
    if (!marking || !context.enabled || !event.isPrimary || event.button !== 0) return;
    event.preventDefault();
    pointer = { id: event.pointerId, start: point(event), clientX: event.clientX, clientY: event.clientY };
    frame.setPointerCapture(event.pointerId);
  });
  frame.addEventListener('pointermove', event => {
    if (pointer?.id !== event.pointerId) return;
    event.preventDefault();
    preview = pixelBox(pointer.start, point(event), context.size);
    if (previewFrame === null) previewFrame = requestAnimationFrame(() => { previewFrame = null; drawOverlay(); });
  });
  frame.addEventListener('pointerup', event => {
    if (pointer?.id !== event.pointerId) return;
    const moved = Math.abs(event.clientX - pointer.clientX) >= 3 && Math.abs(event.clientY - pointer.clientY) >= 3;
    const box = pixelBox(pointer.start, point(event), context.size);
    if (moved && box.width > 0 && box.height > 0) {
      selected.push({ ...box, id: nextAreaId() }); saved = false;
      selected.sort((left, right) => Number(left.id.slice(5)) - Number(right.id.slice(5)));
      stopDrag(); draw();
    } else { stopDrag(); draw(); }
  });
  for (const name of ['pointercancel', 'lostpointercapture']) {
    frame.addEventListener(name, event => {
      if (pointer?.id === event.pointerId) { stopDrag(); draw(); }
    });
  }
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && (marking || selected.length)) { event.preventDefault(); clear(); }
  });
  return {
    get active() { return marking; },
    clear,
    compare() { if (!pointer && !marking) return; stopDrag(); marking = false; draw(); },
    setPage(key, size, imageState, enabled) {
      if (key === context.key && imageState === context.imageState && enabled === context.enabled
          && size?.join(',') === context.size.join(',')) return;
      if (key !== context.key || imageState !== context.imageState) clear();
      context = { key, size: size || [1, 1], imageState, enabled };
      if (!enabled) { stopDrag(); marking = false; }
      draw();
    },
    draft() {
      if (saved || pointer) return [];
      return selected.map(box => ({ coordinate_space: 'page_pixels', ...box, canvas_size: [...context.size], image_state: context.imageState }));
    },
    show(regions) {
      if (!regions.length || regions.some(region => region.canvas_size?.join(',') !== context.size.join(','))) return false;
      stopDrag(); marking = false;
      selected = regions.map((region, index) => ({ ...region, id: region.id || `area-${index + 1}` })); saved = true; draw();
      overlay.firstElementChild.scrollIntoView({ block: 'center', behavior: 'smooth' });
      return true;
    },
  };
}
