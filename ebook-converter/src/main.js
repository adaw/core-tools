// ═══════════════════════════════════════════════════════════
// eBook Converter — CORE Tools #11
// Frontend Logic
// ═══════════════════════════════════════════════════════════

const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
const { open: dialogOpen, save: dialogSave } = window.__TAURI__.dialog;

// ── State ────────────────────────────────────────────
let books = []; // { id, path, name, format, coverBase64, selected }
let selectedBookPath = null;
let currentTab = 'convert';

// ── Init ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  // Check Calibre
  try {
    const ok = await invoke('check_calibre');
    const dot = document.getElementById('calibre-status');
    dot.classList.toggle('ok', ok);
    dot.title = ok ? 'Calibre detected' : 'Calibre not found — install calibre first';
  } catch { }

  // Tab buttons
  document.querySelectorAll('.header-actions .btn-ghost').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.textContent.trim().toLowerCase();
      showTab(tab);
    });
  });

  // Add files
  document.getElementById('btn-add-files').addEventListener('click', addFiles);
  document.getElementById('btn-pick-dir').addEventListener('click', pickOutputDir);
  document.getElementById('btn-convert').addEventListener('click', convertAll);
  document.getElementById('btn-save-meta').addEventListener('click', saveMetadata);
  document.getElementById('btn-extract-cover').addEventListener('click', extractCover);
  document.getElementById('btn-replace-cover').addEventListener('click', replaceCover);

  // Drag & drop
  setupDragDrop();

  // Listen for conversion progress
  await listen('conversion-progress', (event) => {
    updateProgress(event.payload);
  });
});

// ── Tabs ─────────────────────────────────────────────
function showTab(name) {
  currentTab = name;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.header-actions .btn-ghost').forEach(b => b.classList.remove('active'));

  const tabMap = { convert: 'tab-convert', metadata: 'tab-metadata', settings: 'tab-settings' };
  const el = document.getElementById(tabMap[name]);
  if (el) el.classList.add('active');

  document.querySelectorAll('.header-actions .btn-ghost').forEach(b => {
    if (b.textContent.trim().toLowerCase() === name) b.classList.add('active');
  });

  if (name === 'metadata' && selectedBookPath) {
    loadMetadata(selectedBookPath);
  }
}

// ── File Management ──────────────────────────────────
async function addFiles() {
  try {
    const files = await dialogOpen({
      multiple: true,
      filters: [{
        name: 'eBooks',
        extensions: ['epub', 'mobi', 'pdf', 'azw3', 'fb2', 'txt', 'html', 'htm', 'docx', 'rtf', 'odt']
      }]
    });
    if (files) {
      const paths = Array.isArray(files) ? files : [files];
      for (const p of paths) {
        await addBook(p);
      }
    }
  } catch (e) {
    console.error('Failed to open files:', e);
  }
}

async function addBook(filePath) {
  const name = filePath.split('/').pop().split('\\').pop();
  const ext = name.split('.').pop().toLowerCase();
  const id = crypto.randomUUID();

  let coverBase64 = null;
  try {
    coverBase64 = await invoke('get_cover_base64', { filePath });
  } catch { }

  books.push({ id, path: filePath, name, format: ext, coverBase64, selected: false });
  renderBooks();
}

function removeBook(id) {
  books = books.filter(b => b.id !== id);
  renderBooks();
}

function selectBook(id) {
  selectedBookPath = books.find(b => b.id === id)?.path || null;
  books.forEach(b => b.selected = b.id === id);
  renderBooks();
}

function renderBooks() {
  const grid = document.getElementById('book-grid');
  const empty = document.getElementById('empty-state');

  if (books.length === 0) {
    grid.innerHTML = '';
    grid.appendChild(createEmptyState());
    return;
  }

  grid.innerHTML = books.map(b => `
    <div class="book-card ${b.selected ? 'selected' : ''}" onclick="selectBook('${b.id}')" data-id="${b.id}">
      <button class="book-remove" onclick="event.stopPropagation(); removeBook('${b.id}')">×</button>
      <div class="book-cover">
        ${b.coverBase64
          ? `<img src="data:image/jpeg;base64,${b.coverBase64}" alt="Cover" />`
          : `📖`}
      </div>
      <div class="book-info">
        <div class="book-title" title="${b.name}">${b.name}</div>
        <div class="book-format">${b.format}</div>
      </div>
    </div>
  `).join('');
}

function createEmptyState() {
  const div = document.createElement('div');
  div.className = 'empty-state';
  div.id = 'empty-state';
  div.innerHTML = `
    <div class="empty-icon">📂</div>
    <p>Drag & drop eBooks here</p>
    <p class="subtle">or click "Add Files"</p>
  `;
  return div;
}

// ── Drag & Drop ──────────────────────────────────────
function setupDragDrop() {
  const overlay = document.getElementById('drop-overlay');
  let dragCounter = 0;

  document.addEventListener('dragenter', (e) => {
    e.preventDefault();
    dragCounter++;
    overlay.classList.remove('hidden');
  });

  document.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dragCounter--;
    if (dragCounter <= 0) {
      dragCounter = 0;
      overlay.classList.add('hidden');
    }
  });

  document.addEventListener('dragover', (e) => {
    e.preventDefault();
  });

  document.addEventListener('drop', async (e) => {
    e.preventDefault();
    dragCounter = 0;
    overlay.classList.add('hidden');

    // Tauri 2 drag-drop delivers file paths via tauri event, not browser event
    // For browser-based drops, files won't have paths. Show hint.
    if (e.dataTransfer?.files?.length) {
      // In Tauri webview, dropped files might not have full paths
      // Use the dialog as fallback
      console.log('Drop detected — use Add Files button for file access');
    }
  });

  // Listen for Tauri file drop events
  if (window.__TAURI__?.event) {
    listen('tauri://drag-drop', async (event) => {
      overlay.classList.add('hidden');
      const paths = event.payload?.paths || [];
      for (const p of paths) {
        await addBook(p);
      }
    });

    listen('tauri://drag-enter', () => {
      overlay.classList.remove('hidden');
    });

    listen('tauri://drag-leave', () => {
      overlay.classList.add('hidden');
    });
  }
}

// ── Output Dir ───────────────────────────────────────
async function pickOutputDir() {
  try {
    const dir = await dialogOpen({ directory: true });
    if (dir) {
      document.getElementById('output-dir').value = dir;
    }
  } catch { }
}

// ── Conversion ───────────────────────────────────────
async function convertAll() {
  if (books.length === 0) return;

  const format = document.getElementById('output-format').value;
  const outputDir = document.getElementById('output-dir').value;
  const area = document.getElementById('progress-area');
  area.classList.remove('hidden');
  area.innerHTML = '';

  const options = {
    margin_top: numVal('opt-margin-top'),
    margin_bottom: numVal('opt-margin-bottom'),
    margin_left: numVal('opt-margin-left'),
    margin_right: numVal('opt-margin-right'),
    font_size: numVal('opt-font-size'),
    line_height: numVal('opt-line-height'),
    page_size: strVal('opt-page-size'),
    embed_font_family: null,
    no_images: document.getElementById('opt-no-images').checked || null,
  };

  for (const book of books) {
    if (book.format === format) continue; // Skip same format

    const jobId = crypto.randomUUID();
    const outDir = outputDir || book.path.substring(0, book.path.lastIndexOf('/'));

    // Add progress item
    area.innerHTML += `
      <div class="progress-item" id="prog-${jobId}">
        <div class="progress-item-header">
          <span class="progress-name">${book.name} → .${format}</span>
          <span class="progress-pct" id="pct-${jobId}">0%</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" id="fill-${jobId}" style="width: 0%"></div>
        </div>
      </div>
    `;

    try {
      await invoke('convert_ebook', {
        job: {
          id: jobId,
          input_path: book.path,
          output_format: format,
          output_dir: outDir,
          options,
        }
      });
    } catch (e) {
      const item = document.getElementById(`prog-${jobId}`);
      if (item) {
        item.classList.add('error');
        document.getElementById(`pct-${jobId}`).textContent = 'Error';
      }
    }
  }
}

function updateProgress(p) {
  const item = document.getElementById(`prog-${p.job_id}`);
  if (!item) return;

  const fill = document.getElementById(`fill-${p.job_id}`);
  const pct = document.getElementById(`pct-${p.job_id}`);

  if (p.status === 'done') {
    item.classList.add('done');
    fill.style.width = '100%';
    pct.textContent = '✓ Done';
  } else if (p.status === 'error') {
    item.classList.add('error');
    pct.textContent = 'Error';
  } else {
    fill.style.width = `${p.progress}%`;
    pct.textContent = `${Math.round(p.progress)}%`;
  }
}

// ── Metadata ─────────────────────────────────────────
async function loadMetadata(filePath) {
  document.getElementById('meta-file-label').textContent = filePath.split('/').pop();

  try {
    const meta = await invoke('get_metadata', { filePath });
    document.getElementById('meta-title').value = meta.title || '';
    document.getElementById('meta-author').value = meta.author || '';
    document.getElementById('meta-language').value = meta.language || '';
    document.getElementById('meta-publisher').value = meta.publisher || '';
    document.getElementById('meta-tags').value = meta.tags || '';
    document.getElementById('meta-series').value = meta.series || '';
    document.getElementById('meta-series-index').value = meta.series_index || '';
    document.getElementById('meta-description').value = meta.description || '';
    document.getElementById('meta-isbn').value = meta.isbn || '';
  } catch (e) {
    console.error('Failed to load metadata:', e);
  }

  // Load cover
  try {
    const b64 = await invoke('get_cover_base64', { filePath });
    const coverEl = document.getElementById('meta-cover');
    if (b64) {
      coverEl.innerHTML = `<img src="data:image/jpeg;base64,${b64}" alt="Cover" />`;
    } else {
      coverEl.innerHTML = '<div class="meta-cover-placeholder">No cover</div>';
    }
  } catch { }

  // Load TOC
  try {
    const toc = await invoke('get_toc', { filePath });
    document.getElementById('toc-preview').textContent = toc || 'No TOC data available';
  } catch {
    document.getElementById('toc-preview').textContent = 'Could not extract TOC';
  }
}

async function saveMetadata() {
  if (!selectedBookPath) {
    showMetaStatus('Select a book first', true);
    return;
  }

  const metadata = {
    title: strField('meta-title'),
    author: strField('meta-author'),
    language: strField('meta-language'),
    publisher: strField('meta-publisher'),
    description: strField('meta-description'),
    isbn: strField('meta-isbn'),
    tags: strField('meta-tags'),
    series: strField('meta-series'),
    series_index: strField('meta-series-index'),
    cover_path: null,
  };

  try {
    await invoke('set_metadata', { filePath: selectedBookPath, metadata });
    showMetaStatus('✓ Metadata saved');
  } catch (e) {
    showMetaStatus('Error: ' + e, true);
  }
}

async function extractCover() {
  if (!selectedBookPath) return;
  try {
    const savePath = await dialogSave({
      defaultPath: 'cover.jpg',
      filters: [{ name: 'Images', extensions: ['jpg', 'png'] }]
    });
    if (savePath) {
      await invoke('extract_cover', { filePath: selectedBookPath, outputPath: savePath });
      showMetaStatus('✓ Cover extracted to ' + savePath.split('/').pop());
    }
  } catch (e) {
    showMetaStatus('Error: ' + e, true);
  }
}

async function replaceCover() {
  if (!selectedBookPath) return;
  try {
    const file = await dialogOpen({
      filters: [{ name: 'Images', extensions: ['jpg', 'jpeg', 'png'] }]
    });
    if (file) {
      const meta = { title: null, author: null, language: null, publisher: null, description: null, isbn: null, tags: null, series: null, series_index: null, cover_path: file };
      await invoke('set_metadata', { filePath: selectedBookPath, metadata: meta });
      showMetaStatus('✓ Cover replaced');
      loadMetadata(selectedBookPath);
    }
  } catch (e) {
    showMetaStatus('Error: ' + e, true);
  }
}

function showMetaStatus(msg, isError = false) {
  const el = document.getElementById('meta-status');
  el.textContent = msg;
  el.style.color = isError ? 'var(--danger)' : 'var(--accent)';
  setTimeout(() => { el.textContent = ''; }, 4000);
}

// ── Helpers ──────────────────────────────────────────
function numVal(id) {
  const v = document.getElementById(id)?.value;
  return v ? parseFloat(v) : null;
}

function strVal(id) {
  const v = document.getElementById(id)?.value;
  return v || null;
}

function strField(id) {
  const v = document.getElementById(id)?.value?.trim();
  return v || null;
}
