const { invoke } = window.__TAURI__.core;

// ── State ──────────────────────────────────────────────────
let currentDir = '';
let files = [];
let currentMode = 'find_replace';

// ── DOM ────────────────────────────────────────────────────
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const dirInput = $('#dirInput');
const loadBtn = $('#loadBtn');
const fileCount = $('#fileCount');
const previewBtn = $('#previewBtn');
const renameBtn = $('#renameBtn');
const undoBtn = $('#undoBtn');
const undoCount = $('#undoCount');
const previewSection = $('#previewSection');
const previewBody = $('#previewTable tbody');
const progressBar = $('#progressBar');
const progressFill = $('#progressFill');
const statusEl = $('#status');

// ── Mode tabs ──────────────────────────────────────────────
$$('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    $$('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    currentMode = tab.dataset.mode;
    $$('.panel').forEach(p => p.classList.remove('active'));
    $(`.panel[data-panel="${currentMode}"]`).classList.add('active');
    if (files.length > 0) doPreview();
  });
});

// ── Build mode JSON ────────────────────────────────────────
function getModeJson() {
  switch (currentMode) {
    case 'find_replace':
      return JSON.stringify({ mode: 'find_replace', find: $('#findText').value, replace: $('#replaceText').value });
    case 'numbering':
      return JSON.stringify({ mode: 'numbering', prefix: $('#numPrefix').value, start: parseInt($('#numStart').value) || 1, padding: parseInt($('#numPadding').value) || 3 });
    case 'date':
      return JSON.stringify({ mode: 'date', format: $('#dateFormat').value, position: $('#datePosition').value });
    case 'extension':
      return JSON.stringify({ mode: 'extension', new_ext: $('#newExt').value });
    case 'case':
      return JSON.stringify({ mode: 'case', case_type: $('#caseType').value });
    case 'regex':
      return JSON.stringify({ mode: 'regex', pattern: $('#regexPattern').value, replacement: $('#regexReplace').value });
  }
}

// ── Load files ─────────────────────────────────────────────
loadBtn.addEventListener('click', async () => {
  const dir = dirInput.value.trim();
  if (!dir) return;
  try {
    files = await invoke('list_files', { directory: dir });
    currentDir = dir;
    fileCount.textContent = `${files.length} file${files.length !== 1 ? 's' : ''} found`;
    previewBtn.disabled = false;
    renameBtn.disabled = true;
    previewSection.classList.add('hidden');
    showStatus('');
    doPreview();
  } catch (e) {
    showStatus(e, 'error');
    files = [];
    fileCount.textContent = '';
    previewBtn.disabled = true;
  }
});

dirInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') loadBtn.click(); });

// ── Live preview on input change ───────────────────────────
document.addEventListener('input', (e) => {
  if (e.target.closest('.panel') && files.length > 0) {
    clearTimeout(window._previewTimer);
    window._previewTimer = setTimeout(doPreview, 150);
  }
});

// ── Preview ────────────────────────────────────────────────
previewBtn.addEventListener('click', doPreview);

async function doPreview() {
  if (files.length === 0) return;
  try {
    const items = await invoke('preview_rename', { files, modeJson: getModeJson() });
    previewBody.innerHTML = '';
    items.forEach((item, i) => {
      const tr = document.createElement('tr');
      tr.className = item.changed ? 'changed' : 'unchanged';
      tr.style.setProperty('--i', i);
      tr.innerHTML = `<td>${esc(item.original)}</td><td>${item.changed ? '→' : '='}</td><td>${esc(item.renamed)}</td>`;
      previewBody.appendChild(tr);
    });
    previewSection.classList.remove('hidden');
    renameBtn.disabled = !items.some(i => i.changed);
  } catch (e) {
    showStatus(e, 'error');
  }
}

// ── Rename ─────────────────────────────────────────────────
renameBtn.addEventListener('click', async () => {
  if (!currentDir || files.length === 0) return;
  renameBtn.disabled = true;
  progressBar.classList.remove('hidden');
  progressFill.style.width = '30%';

  try {
    progressFill.style.width = '70%';
    const result = await invoke('execute_rename', { directory: currentDir, files, modeJson: getModeJson() });
    progressFill.style.width = '100%';

    let msg = `✓ Renamed ${result.success} file${result.success !== 1 ? 's' : ''}`;
    if (result.failed > 0) msg += `, ${result.failed} failed`;
    showStatus(msg, result.failed > 0 ? 'error' : 'success');

    // Reload
    setTimeout(async () => {
      progressBar.classList.add('hidden');
      progressFill.style.width = '0%';
      files = await invoke('list_files', { directory: currentDir });
      fileCount.textContent = `${files.length} file${files.length !== 1 ? 's' : ''} found`;
      doPreview();
      updateUndoCount();
    }, 400);
  } catch (e) {
    showStatus(e, 'error');
    progressBar.classList.add('hidden');
    renameBtn.disabled = false;
  }
});

// ── Undo ───────────────────────────────────────────────────
undoBtn.addEventListener('click', async () => {
  try {
    const count = await invoke('undo_rename');
    showStatus(`↩ Undone ${count} rename${count !== 1 ? 's' : ''}`, 'success');
    files = await invoke('list_files', { directory: currentDir });
    fileCount.textContent = `${files.length} file${files.length !== 1 ? 's' : ''} found`;
    doPreview();
    updateUndoCount();
  } catch (e) {
    showStatus(e, 'error');
  }
});

async function updateUndoCount() {
  try {
    const count = await invoke('get_undo_count');
    undoCount.textContent = count;
    undoBtn.disabled = count === 0;
  } catch (_) {}
}

// ── Helpers ────────────────────────────────────────────────
function showStatus(msg, type) {
  if (!msg) { statusEl.classList.add('hidden'); return; }
  statusEl.textContent = msg;
  statusEl.className = `status ${type || ''}`;
  statusEl.classList.remove('hidden');
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// Init
updateUndoCount();
