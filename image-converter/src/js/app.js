// ══════════════════════════════════════════════════════════════════════
// CORE Image Converter — Frontend Application
// ══════════════════════════════════════════════════════════════════════

const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
const { open: dialogOpen } = window.__TAURI__.dialog;

// ── State ──────────────────────────────────────────────────────────────

let images = [];
let selectedFormat = 'PNG';
let outputDir = '';
let estimateTimer = null;
let selectedImageIndex = null;

// ── DOM ────────────────────────────────────────────────────────────────

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dropZone = $('#dropZone');
const imageGrid = $('#imageGrid');
const fileInput = $('#fileInput');
const formatGrid = $('#formatGrid');
const qualitySlider = $('#qualitySlider');
const qualityValue = $('#qualityValue');
const sizeEstimate = $('#sizeEstimate');
const resizeMode = $('#resizeMode');
const resizeInputs = $('#resizeInputs');
const resizePercent = $('#resizePercent');
const resizePixels = $('#resizePixels');
const stripMeta = $('#stripMeta');
const outputFolder = $('#outputFolder');
const folderPath = $('#folderPath');
const filenameTemplate = $('#filenameTemplate');
const convertBtn = $('#convertBtn');
const progressBar = $('#progressBar');
const progressFill = $('#progressFill');
const progressText = $('#progressText');
const results = $('#results');
const resultsSummary = $('#resultsSummary');
const resultsList = $('#resultsList');
const headerStats = $('#headerStats');
const previewOverlay = $('#previewOverlay');

// ── Format Selection ───────────────────────────────────────────────────

formatGrid.addEventListener('click', (e) => {
  const btn = e.target.closest('.format-btn');
  if (!btn) return;
  $$('.format-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  selectedFormat = btn.dataset.format;
  scheduleEstimate();
});

// ── Quality Slider ─────────────────────────────────────────────────────

qualitySlider.addEventListener('input', () => {
  qualityValue.textContent = qualitySlider.value;
  scheduleEstimate();
});

// ── Resize Mode ────────────────────────────────────────────────────────

resizeMode.addEventListener('change', () => {
  const mode = resizeMode.value;
  resizeInputs.classList.toggle('hidden', mode === 'none');
  resizePercent.classList.toggle('hidden', mode !== 'percent');
  resizePixels.classList.toggle('hidden', mode !== 'pixels' && mode !== 'fit');
});

// ── Output Folder ──────────────────────────────────────────────────────

outputFolder.addEventListener('click', async () => {
  try {
    const dir = await dialogOpen({ directory: true, title: 'Select Output Folder' });
    if (dir) {
      outputDir = dir;
      folderPath.textContent = dir.split('/').slice(-2).join('/');
      folderPath.style.color = 'var(--fg)';
      updateConvertBtn();
    }
  } catch (e) {
    console.error('Folder pick error:', e);
  }
});

// ── Drop Zone ──────────────────────────────────────────────────────────

dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => {
  dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
  if (files.length) loadFiles(files);
});

fileInput.addEventListener('change', () => {
  if (fileInput.files.length) loadFiles(Array.from(fileInput.files));
  fileInput.value = '';
});

// ── File Loading ───────────────────────────────────────────────────────

async function loadFiles(files) {
  const paths = files.map(f => f.path || f.name);
  // Filter valid paths
  const validPaths = paths.filter(p => p && p.startsWith('/'));
  if (!validPaths.length) return;

  dropZone.classList.add('hidden');
  imageGrid.classList.remove('hidden');
  imageGrid.innerHTML = '<div class="loading" style="text-align:center;padding:40px;color:var(--fg-dim)">Loading images…</div>';

  try {
    const newImages = await invoke('load_images', { paths: validPaths });
    images = [...images, ...newImages];
    renderGrid();
    updateStats();
    updateConvertBtn();
  } catch (e) {
    console.error('Load error:', e);
    if (!images.length) {
      dropZone.classList.remove('hidden');
      imageGrid.classList.add('hidden');
    }
  }
}

// ── Grid Rendering ─────────────────────────────────────────────────────

function renderGrid() {
  imageGrid.innerHTML = '';
  
  images.forEach((img, idx) => {
    const card = document.createElement('div');
    card.className = 'image-card';
    card.innerHTML = `
      <div class="thumb-container">
        <img src="${img.thumbnail}" alt="${img.name}" loading="lazy" />
        <button class="remove-btn" data-idx="${idx}" title="Remove">✕</button>
      </div>
      <div class="card-info">
        <div class="card-name" title="${img.name}">${img.name}</div>
        <div class="card-meta">
          <span>${img.width}×${img.height}</span>
          <span>${humanSize(img.size_bytes)}</span>
        </div>
      </div>
    `;
    
    card.addEventListener('click', (e) => {
      if (e.target.closest('.remove-btn')) return;
      showPreview(idx);
    });
    
    card.querySelector('.remove-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      images.splice(idx, 1);
      renderGrid();
      updateStats();
      updateConvertBtn();
      if (!images.length) {
        dropZone.classList.remove('hidden');
        imageGrid.classList.add('hidden');
      }
    });
    
    imageGrid.appendChild(card);
  });
  
  // Add more button
  const addCard = document.createElement('div');
  addCard.className = 'add-more-card';
  addCard.innerHTML = '<span class="plus">+</span><span>Add More</span>';
  addCard.addEventListener('click', () => fileInput.click());
  imageGrid.appendChild(addCard);
}

// ── Preview ────────────────────────────────────────────────────────────

async function showPreview(idx) {
  const img = images[idx];
  selectedImageIndex = idx;
  
  $('#previewTitle').textContent = img.name;
  $('#previewOriginal').src = img.thumbnail;
  $('#previewOrigInfo').textContent = `${img.width}×${img.height} • ${humanSize(img.size_bytes)} • ${img.format}`;
  
  // Load converted preview
  $('#previewConverted').src = '';
  $('#previewConvInfo').textContent = 'Generating preview…';
  
  previewOverlay.classList.remove('hidden');
  
  try {
    const quality = parseInt(qualitySlider.value);
    const preview = await invoke('get_preview', {
      path: img.path,
      format: selectedFormat,
      quality,
      maxSize: 600
    });
    
    const estimate = await invoke('estimate_size', {
      path: img.path,
      format: selectedFormat,
      quality
    });
    
    $('#previewConverted').src = preview;
    const savings = ((1 - estimate.estimated_bytes / img.size_bytes) * 100).toFixed(1);
    const savingsClass = savings > 0 ? 'positive' : 'negative';
    $('#previewConvInfo').innerHTML = `${selectedFormat} • ${humanSize(estimate.estimated_bytes)} • <span class="${savingsClass}">${savings > 0 ? '-' : '+'}${Math.abs(savings)}%</span>`;
  } catch (e) {
    $('#previewConvInfo').textContent = 'Preview failed: ' + e;
  }
}

$('#previewClose').addEventListener('click', () => {
  previewOverlay.classList.add('hidden');
});

previewOverlay.addEventListener('click', (e) => {
  if (e.target === previewOverlay) previewOverlay.classList.add('hidden');
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') previewOverlay.classList.add('hidden');
});

// ── Size Estimate ──────────────────────────────────────────────────────

function scheduleEstimate() {
  clearTimeout(estimateTimer);
  estimateTimer = setTimeout(doEstimate, 300);
}

async function doEstimate() {
  if (!images.length) return;
  
  // Estimate from first image
  const img = images[selectedImageIndex ?? 0] || images[0];
  sizeEstimate.textContent = 'Estimating…';
  sizeEstimate.classList.add('loading');
  
  try {
    const est = await invoke('estimate_size', {
      path: img.path,
      format: selectedFormat,
      quality: parseInt(qualitySlider.value)
    });
    
    const savings = ((1 - est.estimated_bytes / img.size_bytes) * 100).toFixed(1);
    sizeEstimate.classList.remove('loading');
    sizeEstimate.innerHTML = `≈ ${humanSize(est.estimated_bytes)} <span style="color:${savings > 0 ? 'var(--success)' : 'var(--warning)'}">(${savings > 0 ? '-' : '+'}${Math.abs(savings)}%)</span>`;
  } catch (e) {
    sizeEstimate.classList.remove('loading');
    sizeEstimate.textContent = 'Estimate failed';
  }
}

// ── Convert ────────────────────────────────────────────────────────────

convertBtn.addEventListener('click', startConversion);

async function startConversion() {
  if (!images.length || !outputDir) return;
  
  const mode = resizeMode.value;
  const options = {
    output_format: selectedFormat,
    quality: parseInt(qualitySlider.value),
    resize_mode: mode,
    resize_width: mode === 'pixels' || mode === 'fit' ? parseInt($('#resizeW').value) || null : null,
    resize_height: mode === 'pixels' || mode === 'fit' ? parseInt($('#resizeH').value) || null : null,
    resize_percent: mode === 'percent' ? parseFloat($('#resizePct').value) || null : null,
    strip_metadata: stripMeta.checked,
    output_dir: outputDir,
    filename_template: filenameTemplate.value || '{name}',
  };
  
  // Show progress
  convertBtn.disabled = true;
  convertBtn.innerHTML = '<span class="convert-icon">⏳</span> Converting…';
  progressBar.classList.remove('hidden');
  results.classList.add('hidden');
  progressFill.style.width = '0%';
  progressText.textContent = `0 / ${images.length}`;
  
  try {
    const paths = images.map(i => i.path);
    const convertResults = await invoke('convert_images', { paths, options });
    showResults(convertResults);
  } catch (e) {
    console.error('Convert error:', e);
    progressText.textContent = 'Error: ' + e;
  } finally {
    convertBtn.disabled = false;
    convertBtn.innerHTML = '<span class="convert-icon">⚡</span> Convert All';
    updateConvertBtn();
  }
}

// ── Progress Listener ──────────────────────────────────────────────────

listen('convert-progress', (event) => {
  const { completed, total, current_file } = event.payload;
  const pct = (completed / total * 100).toFixed(1);
  progressFill.style.width = pct + '%';
  progressText.textContent = `${completed} / ${total} — ${current_file}`;
});

// ── Results ────────────────────────────────────────────────────────────

function showResults(convertResults) {
  progressBar.classList.add('hidden');
  results.classList.remove('hidden');
  
  const successes = convertResults.filter(r => r.success);
  const failures = convertResults.filter(r => !r.success);
  const totalOriginal = successes.reduce((a, r) => a + r.original_size, 0);
  const totalNew = successes.reduce((a, r) => a + r.new_size, 0);
  const totalSavings = totalOriginal > 0 ? ((1 - totalNew / totalOriginal) * 100).toFixed(1) : 0;
  
  resultsSummary.innerHTML = `
    <div class="result-stat">
      <div class="stat-value">${successes.length}</div>
      <div class="stat-label">Converted</div>
    </div>
    ${failures.length ? `<div class="result-stat"><div class="stat-value" style="color:var(--error)">${failures.length}</div><div class="stat-label">Failed</div></div>` : ''}
    <div class="result-stat">
      <div class="stat-value">${humanSize(totalNew)}</div>
      <div class="stat-label">Total Size</div>
    </div>
    <div class="result-stat">
      <div class="stat-value" style="color:${totalSavings > 0 ? 'var(--success)' : 'var(--warning)'}">${totalSavings > 0 ? '-' : '+'}${Math.abs(totalSavings)}%</div>
      <div class="stat-label">Size Change</div>
    </div>
  `;
  
  resultsList.innerHTML = convertResults.map(r => {
    const cls = r.success ? 'success' : 'error';
    const icon = r.success ? '✓' : '✗';
    const name = r.source.split('/').pop();
    if (r.success) {
      const savings = ((1 - r.new_size / r.original_size) * 100).toFixed(1);
      const savCls = savings > 0 ? 'positive' : 'negative';
      return `<div class="result-row ${cls}">
        <span class="result-status">${icon}</span>
        <span class="result-name">${name}</span>
        <span class="result-sizes">${humanSize(r.original_size)} → ${humanSize(r.new_size)}</span>
        <span class="result-savings ${savCls}">${savings > 0 ? '-' : '+'}${Math.abs(savings)}%</span>
      </div>`;
    }
    return `<div class="result-row ${cls}">
      <span class="result-status">${icon}</span>
      <span class="result-name">${name}</span>
      <span class="result-sizes" style="color:var(--error)">${r.error}</span>
    </div>`;
  }).join('');
}

// ── Helpers ────────────────────────────────────────────────────────────

function humanSize(bytes) {
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let size = bytes;
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024;
    i++;
  }
  return size.toFixed(i === 0 ? 0 : 1) + ' ' + units[i];
}

function updateStats() {
  if (!images.length) {
    headerStats.textContent = '';
    return;
  }
  const totalSize = images.reduce((a, i) => a + i.size_bytes, 0);
  headerStats.textContent = `${images.length} image${images.length !== 1 ? 's' : ''} • ${humanSize(totalSize)}`;
}

function updateConvertBtn() {
  convertBtn.disabled = !images.length || !outputDir;
}

// ── Drag & Drop from OS (Tauri file drop) ──────────────────────────────

// Tauri 2 uses web standard drag/drop, handled above in drop zone
// Also handle drops anywhere on body as fallback
document.body.addEventListener('dragover', (e) => {
  e.preventDefault();
  if (!dropZone.classList.contains('hidden')) {
    dropZone.classList.add('drag-over');
  }
});

document.body.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
});

// ── Init ───────────────────────────────────────────────────────────────

console.log('CORE Image Converter initialized');
