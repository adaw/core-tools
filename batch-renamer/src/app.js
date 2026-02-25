// ═══════════════════════════════════════════════════════════════════════════
// CORE Batch Renamer — Frontend Logic
// © CORE SYSTEMS
// ═══════════════════════════════════════════════════════════════════════════

const { invoke } = window.__TAURI__.core;
const { open } = window.__TAURI__.dialog;

// ─── State ───────────────────────────────────────────────────────────────────

let files = [];          // Array of {path, name}
let currentMode = 'find_replace';
let undoStack = [];      // Array of [{oldPath, newPath}]
let previewDebounce = null;

// ─── DOM Refs ────────────────────────────────────────────────────────────────

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dropZone = $('#dropZone');
const previewList = $('#previewList');
const emptyState = $('#emptyState');
const fileCount = $('#fileCount');
const previewStats = $('#previewStats');
const statusText = $('#statusText');
const btnRename = $('#btnRename');
const btnUndo = $('#btnUndo');
const btnAddFiles = $('#btnAddFiles');
const btnAddFolder = $('#btnAddFolder');
const btnClear = $('#btnClear');
const dialogOverlay = $('#dialogOverlay');
const progressOverlay = $('#progressOverlay');

// ─── Mode Switching ──────────────────────────────────────────────────────────

$$('.mode-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    $$('.mode-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    currentMode = tab.dataset.mode;

    $$('.mode-panel').forEach(p => p.classList.remove('active'));
    $(`.mode-panel[data-panel="${currentMode}"]`).classList.add('active');

    schedulePreview();
  });
});

// ─── File Management ─────────────────────────────────────────────────────────

function addFiles(newFiles) {
  const existingPaths = new Set(files.map(f => f.path));
  const unique = newFiles.filter(f => !existingPaths.has(f.path));
  files = [...files, ...unique];
  updateUI();
  schedulePreview();
}

function removeFile(index) {
  files.splice(index, 1);
  updateUI();
  schedulePreview();
}

function clearFiles() {
  files = [];
  updateUI();
  previewList.innerHTML = '';
  previewList.appendChild(emptyState);
  emptyState.style.display = '';
  previewStats.textContent = '';
  setStatus('Cleared all files');
}

function updateUI() {
  const n = files.length;
  fileCount.textContent = `${n} file${n !== 1 ? 's' : ''}`;
  fileCount.classList.toggle('has-files', n > 0);
  btnUndo.disabled = undoStack.length === 0;
}

function setStatus(text) {
  statusText.textContent = text;
}

// ─── Build Rename Mode Object ────────────────────────────────────────────────

function buildMode() {
  switch (currentMode) {
    case 'find_replace':
      return {
        mode: 'find_replace',
        find: $('#frFind').value,
        replace: $('#frReplace').value,
        use_regex: $('#frRegex').checked,
      };
    case 'numbering':
      return {
        mode: 'numbering',
        prefix: $('#numPrefix').value,
        suffix: $('#numSuffix').value,
        start: parseInt($('#numStart').value) || 1,
        padding: parseInt($('#numPadding').value) || 3,
      };
    case 'date_stamp':
      return {
        mode: 'date_stamp',
        format: $('#dateFormat').value || '%Y-%m-%d',
        position: document.querySelector('input[name="datePos"]:checked')?.value || 'prefix',
        separator: $('#dateSep').value || '_',
      };
    case 'extension':
      return {
        mode: 'extension',
        new_ext: $('#extNew').value,
      };
    case 'case_change':
      return {
        mode: 'case_change',
        case_type: document.querySelector('input[name="caseType"]:checked')?.value || 'lower',
      };
    case 'regex':
      return {
        mode: 'regex',
        pattern: $('#regPattern').value,
        replacement: $('#regReplace').value,
        apply_to: document.querySelector('input[name="regScope"]:checked')?.value || 'name',
      };
  }
}

// ─── Preview ─────────────────────────────────────────────────────────────────

function schedulePreview() {
  clearTimeout(previewDebounce);
  previewDebounce = setTimeout(doPreview, 80);
}

async function doPreview() {
  if (files.length === 0) {
    previewList.innerHTML = '';
    previewList.appendChild(emptyState);
    emptyState.style.display = '';
    previewStats.textContent = '';
    return;
  }

  try {
    const mode = buildMode();
    const items = await invoke('preview_rename', { files, mode });

    emptyState.style.display = 'none';

    // Build preview HTML
    let html = '';
    let changedCount = 0;

    items.forEach((item, i) => {
      const cls = item.changed ? 'changed' : 'unchanged';
      if (item.changed) changedCount++;

      html += `
        <div class="preview-item ${cls}" style="animation-delay:${Math.min(i * 15, 300)}ms">
          <span class="preview-index">${i + 1}</span>
          <div class="preview-names">
            <div class="preview-old">${escHtml(item.old_name)}</div>
            <div class="preview-new">${escHtml(item.new_name)}</div>
          </div>
          <span class="preview-arrow">→</span>
          <button class="preview-remove" onclick="removeFile(${i})" title="Remove">✕</button>
        </div>
      `;
    });

    previewList.innerHTML = html;
    previewStats.textContent = `${changedCount} of ${items.length} will change`;
    setStatus(`Preview: ${changedCount} file${changedCount !== 1 ? 's' : ''} will be renamed`);
  } catch (err) {
    console.error('Preview error:', err);
    setStatus(`Preview error: ${err}`);
  }
}

function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// ─── Rename Execution ────────────────────────────────────────────────────────

async function doRename() {
  if (files.length === 0) return;

  const mode = buildMode();
  const items = await invoke('preview_rename', { files, mode });
  const changedCount = items.filter(i => i.changed).length;

  if (changedCount === 0) {
    showToast('No files would be renamed with current settings', true);
    return;
  }

  // Show confirmation
  const confirmed = await showConfirmDialog(
    'Confirm Rename',
    `Rename ${changedCount} file${changedCount !== 1 ? 's' : ''}? This can be undone.`
  );
  if (!confirmed) return;

  // Show progress
  showProgress(true);

  try {
    const result = await invoke('execute_rename', { files, mode });

    // Build undo data
    const undoBatch = [];
    items.forEach(item => {
      if (item.changed) {
        const dir = item.path.substring(0, item.path.lastIndexOf('/') + 1) ||
                    item.path.substring(0, item.path.lastIndexOf('\\') + 1);
        undoBatch.push([dir + item.new_name, item.path]);
      }
    });
    if (undoBatch.length > 0) {
      undoStack.push(undoBatch);
    }

    // Update file list with new names
    files = files.map((f, i) => {
      const item = items[i];
      if (item && item.changed) {
        const dir = f.path.substring(0, f.path.lastIndexOf('/') + 1) ||
                    f.path.substring(0, f.path.lastIndexOf('\\') + 1);
        return { path: dir + item.new_name, name: item.new_name };
      }
      return f;
    });

    showProgress(false);
    updateUI();
    schedulePreview();

    if (result.errors.length > 0) {
      showToast(`Renamed ${result.renamed} files. ${result.errors.length} error(s).`, true);
    } else {
      showToast(`✓ Renamed ${result.renamed} files successfully`);
    }

    setStatus(`✓ Renamed ${result.renamed} files`);
  } catch (err) {
    showProgress(false);
    showToast(`Error: ${err}`, true);
    setStatus(`Error: ${err}`);
  }
}

// ─── Undo ────────────────────────────────────────────────────────────────────

async function doUndo() {
  if (undoStack.length === 0) {
    showToast('Nothing to undo', true);
    return;
  }

  const batch = undoStack.pop();

  try {
    const result = await invoke('undo_rename', { operations: batch });

    // Restore file list
    batch.forEach(([newPath, oldPath]) => {
      const idx = files.findIndex(f => f.path === newPath);
      if (idx >= 0) {
        const name = oldPath.split('/').pop() || oldPath.split('\\').pop();
        files[idx] = { path: oldPath, name };
      }
    });

    updateUI();
    schedulePreview();
    showToast(`↩ Undone ${result.renamed} renames`);
    setStatus(`↩ Undone ${result.renamed} renames`);
  } catch (err) {
    showToast(`Undo error: ${err}`, true);
  }
}

// ─── File Dialog ─────────────────────────────────────────────────────────────

async function openFileDialog() {
  try {
    const selected = await open({
      multiple: true,
      title: 'Select files to rename',
    });
    if (!selected) return;

    const paths = Array.isArray(selected) ? selected : [selected];
    const entries = await invoke('validate_paths', { paths });
    if (entries.length > 0) {
      addFiles(entries);
      setStatus(`Added ${entries.length} file(s)`);
    }
  } catch (err) {
    setStatus(`Error: ${err}`);
  }
}

async function openFolderDialog() {
  try {
    const selected = await open({
      directory: true,
      title: 'Select folder',
    });
    if (!selected) return;

    const entries = await invoke('list_directory', { path: selected });
    if (entries.length > 0) {
      addFiles(entries);
      setStatus(`Added ${entries.length} file(s) from folder`);
    }
  } catch (err) {
    setStatus(`Error: ${err}`);
  }
}

// ─── Drag & Drop ─────────────────────────────────────────────────────────────

document.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

document.addEventListener('dragleave', (e) => {
  if (!e.relatedTarget || e.relatedTarget === document.documentElement) {
    dropZone.classList.remove('drag-over');
  }
});

document.addEventListener('drop', async (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');

  const droppedFiles = e.dataTransfer?.files;
  if (!droppedFiles || droppedFiles.length === 0) return;

  const paths = [];
  for (let i = 0; i < droppedFiles.length; i++) {
    if (droppedFiles[i].path) {
      paths.push(droppedFiles[i].path);
    }
  }

  if (paths.length === 0) return;

  // Check if any are directories
  const allEntries = [];
  for (const p of paths) {
    try {
      const dirEntries = await invoke('list_directory', { path: p });
      allEntries.push(...dirEntries);
    } catch {
      // Not a directory, treat as file
      const validated = await invoke('validate_paths', { paths: [p] });
      allEntries.push(...validated);
    }
  }

  if (allEntries.length > 0) {
    addFiles(allEntries);
    setStatus(`Dropped ${allEntries.length} file(s)`);
  }
});

dropZone.addEventListener('click', openFileDialog);

// ─── UI Helpers ──────────────────────────────────────────────────────────────

function showConfirmDialog(title, message) {
  return new Promise((resolve) => {
    $('#dialogTitle').textContent = title;
    $('#dialogMessage').textContent = message;
    dialogOverlay.classList.add('visible');

    const onConfirm = () => {
      cleanup();
      resolve(true);
    };
    const onCancel = () => {
      cleanup();
      resolve(false);
    };
    const cleanup = () => {
      dialogOverlay.classList.remove('visible');
      $('#dialogConfirm').removeEventListener('click', onConfirm);
      $('#dialogCancel').removeEventListener('click', onCancel);
    };

    $('#dialogConfirm').addEventListener('click', onConfirm);
    $('#dialogCancel').addEventListener('click', onCancel);
  });
}

function showProgress(show) {
  if (show) {
    progressOverlay.classList.add('visible');
    $('#progressFill').style.width = '70%';
  } else {
    $('#progressFill').style.width = '100%';
    setTimeout(() => progressOverlay.classList.remove('visible'), 300);
  }
}

function showToast(message, isError = false) {
  const toast = document.createElement('div');
  toast.className = isError ? 'error-flash' : 'success-flash';
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3200);
}

// ─── Event Listeners ─────────────────────────────────────────────────────────

btnAddFiles.addEventListener('click', openFileDialog);
btnAddFolder.addEventListener('click', openFolderDialog);
btnClear.addEventListener('click', clearFiles);
btnRename.addEventListener('click', doRename);
btnUndo.addEventListener('click', doUndo);

// Live preview on input changes
document.querySelectorAll('input[type="text"], input[type="number"]').forEach(el => {
  el.addEventListener('input', schedulePreview);
});
document.querySelectorAll('input[type="checkbox"], input[type="radio"]').forEach(el => {
  el.addEventListener('change', schedulePreview);
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey) {
    if (e.key === 'z') {
      e.preventDefault();
      doUndo();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      doRename();
    }
  }
  if (e.key === 'Delete' && !e.target.matches('input')) {
    clearFiles();
  }
});

// ─── Init ────────────────────────────────────────────────────────────────────

updateUI();
setStatus('Ready — drop files or click Add Files');
