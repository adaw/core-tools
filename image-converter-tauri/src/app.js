const { invoke } = window.__TAURI__.core;

let files = []; // { path, info, thumbnail }
let outputDir = '';

// --- DOM refs ---
const btnAdd = document.getElementById('btn-add');
const btnClear = document.getElementById('btn-clear');
const btnConvert = document.getElementById('btn-convert');
const btnOutput = document.getElementById('btn-output');
const fileCount = document.getElementById('file-count');
const formatSel = document.getElementById('format');
const qualitySlider = document.getElementById('quality');
const qualityVal = document.getElementById('quality-val');
const resizeW = document.getElementById('resize-w');
const resizeH = document.getElementById('resize-h');
const stripMeta = document.getElementById('strip-meta');
const outputPath = document.getElementById('output-path');
const dropZone = document.getElementById('drop-zone');
const imageGrid = document.getElementById('image-grid');
const results = document.getElementById('results');
const resultsList = document.getElementById('results-list');
const previewModal = document.getElementById('preview-modal');

// --- Quality slider ---
qualitySlider.addEventListener('input', () => {
  qualityVal.textContent = qualitySlider.value;
});

// --- Add images ---
btnAdd.addEventListener('click', async () => {
  try {
    const selected = await window.__TAURI__.dialog.open({
      multiple: true,
      filters: [{ name: 'Images', extensions: ['png','jpg','jpeg','webp','bmp','tiff','tif','gif','ico','avif'] }]
    });
    if (selected) {
      const paths = Array.isArray(selected) ? selected : [selected];
      await addFiles(paths);
    }
  } catch (e) { console.error(e); }
});

// --- Output dir ---
btnOutput.addEventListener('click', async () => {
  try {
    const dir = await window.__TAURI__.dialog.open({ directory: true });
    if (dir) {
      outputDir = dir;
      outputPath.textContent = dir;
      updateConvertBtn();
    }
  } catch (e) { console.error(e); }
});

// --- Clear ---
btnClear.addEventListener('click', () => {
  files = [];
  render();
});

// --- Convert ---
btnConvert.addEventListener('click', async () => {
  if (!files.length || !outputDir) return;
  btnConvert.disabled = true;
  btnConvert.textContent = '⏳ Converting…';
  results.classList.add('hidden');

  try {
    const res = await invoke('convert_images', {
      options: {
        paths: files.map(f => f.path),
        output_dir: outputDir,
        format: formatSel.value,
        quality: parseInt(qualitySlider.value),
        resize_width: resizeW.value ? parseInt(resizeW.value) : null,
        resize_height: resizeH.value ? parseInt(resizeH.value) : null,
        strip_metadata: stripMeta.checked,
      }
    });
    showResults(res);
  } catch (e) {
    console.error(e);
    alert('Conversion failed: ' + e);
  }
  btnConvert.disabled = false;
  btnConvert.textContent = '🚀 Convert All';
});

// --- Modal close ---
document.getElementById('modal-close').addEventListener('click', () => {
  previewModal.classList.add('hidden');
});

// --- Drop zone ---
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => { dropZone.classList.remove('drag-over'); });
dropZone.addEventListener('drop', async (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  // Tauri handles file drops via events, basic HTML drop won't give paths
});

// --- Add files logic ---
async function addFiles(paths) {
  const infos = await invoke('get_image_info', { paths });
  for (const info of infos) {
    if (files.find(f => f.path === info.path)) continue;
    const thumb = await invoke('generate_thumbnail', { path: info.path, maxSize: 200 });
    files.push({ path: info.path, info, thumbnail: thumb });
  }
  render();
}

function render() {
  fileCount.textContent = `${files.length} file${files.length !== 1 ? 's' : ''}`;
  dropZone.style.display = files.length ? 'none' : 'block';
  updateConvertBtn();

  imageGrid.innerHTML = files.map((f, i) => `
    <div class="image-card" data-idx="${i}">
      <button class="card-remove" data-remove="${i}">✕</button>
      <img src="${f.thumbnail}" alt="${f.info.filename}">
      <div class="card-info">
        <div class="card-name" title="${f.info.filename}">${f.info.filename}</div>
        <div class="card-meta">${f.info.width}×${f.info.height} · ${formatBytes(f.info.size_bytes)}</div>
      </div>
    </div>
  `).join('');

  // Remove buttons
  imageGrid.querySelectorAll('.card-remove').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      files.splice(parseInt(btn.dataset.remove), 1);
      render();
    });
  });

  // Click to preview
  imageGrid.querySelectorAll('.image-card').forEach(card => {
    card.addEventListener('click', () => {
      const f = files[parseInt(card.dataset.idx)];
      showPreview(f);
    });
  });
}

function showPreview(f) {
  document.getElementById('preview-title').textContent = f.info.filename;
  document.getElementById('preview-before').src = f.thumbnail;
  document.getElementById('preview-before-info').textContent =
    `${f.info.width}×${f.info.height} · ${f.info.format} · ${formatBytes(f.info.size_bytes)}`;
  document.getElementById('preview-after').src = '';
  document.getElementById('preview-after-info').textContent = 'Convert to see result';
  previewModal.classList.remove('hidden');
}

function showResults(res) {
  results.classList.remove('hidden');
  resultsList.innerHTML = res.map(r => {
    const saved = r.success ? ((1 - r.new_size / r.original_size) * 100).toFixed(1) : 0;
    const cls = r.success ? 'success' : 'error';
    const name = r.source.split('/').pop();
    return `<div class="result-item ${cls}">
      <span class="result-name">${name}</span>
      ${r.success
        ? `<span class="result-size">${formatBytes(r.original_size)} → ${formatBytes(r.new_size)}</span>
           <span class="result-saved">${saved > 0 ? '-' + saved + '%' : '+' + Math.abs(saved) + '%'}</span>`
        : `<span style="color:var(--danger)">${r.error}</span>`
      }
    </div>`;
  }).join('');
}

function updateConvertBtn() {
  btnConvert.disabled = !(files.length > 0 && outputDir);
}

function formatBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1024*1024) return (b/1024).toFixed(1) + ' KB';
  return (b/1024/1024).toFixed(1) + ' MB';
}
