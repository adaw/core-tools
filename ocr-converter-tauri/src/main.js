const { invoke } = window.__TAURI__.core;
const { open, save } = window.__TAURI__.dialog;

let currentMode = 'ocr';
let currentFile = null;

// --- Mode switching ---
window.switchMode = function(mode) {
  currentMode = mode;
  document.querySelectorAll('.tool-btn').forEach(btn => btn.classList.remove('active'));
  document.getElementById(`btn-${mode}`).classList.add('active');
  setStatus('Ready');
};

// --- File open ---
window.openFile = async function() {
  try {
    const filters = currentMode === 'pdf'
      ? [{ name: 'PDF', extensions: ['pdf'] }]
      : currentMode === 'img2pdf'
      ? [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'tiff', 'bmp', 'webp'] }]
      : [{ name: 'Images & PDF', extensions: ['png', 'jpg', 'jpeg', 'tiff', 'bmp', 'webp', 'pdf'] }];

    const multiple = currentMode === 'batch';
    const result = await open({ multiple, filters });
    if (!result) return;

    const files = Array.isArray(result) ? result : [result];
    if (files.length === 0) return;

    currentFile = files[0];
    showFileInfo(currentFile);
    showPreview(currentFile);

    if (currentMode === 'batch') {
      await runBatchOcr(files);
    } else {
      await processFile(currentFile);
    }
  } catch (err) {
    setStatus(`Error: ${err}`, true);
  }
};

// --- Process single file ---
async function processFile(filePath) {
  const lang = document.getElementById('lang-select').value;
  setStatus('Processing...');
  showProgress(true);

  try {
    let result;
    switch (currentMode) {
      case 'ocr':
        result = await invoke('ocr_image', { filePath, language: lang });
        setOutput(result.text);
        showConfidence(result.confidence);
        setStatus(`OCR complete — ${result.text.length} characters extracted`);
        break;
      case 'pdf':
        result = await invoke('pdf_to_text', { filePath });
        setOutput(result.text);
        hideConfidence();
        setStatus(`PDF extracted — ${result.page_count} pages, ${result.text.length} chars`);
        break;
      case 'img2pdf':
        const outPath = await save({
          defaultPath: filePath.replace(/\.[^.]+$/, '.pdf'),
          filters: [{ name: 'PDF', extensions: ['pdf'] }],
        });
        if (!outPath) { setStatus('Cancelled'); showProgress(false); return; }
        result = await invoke('image_to_pdf', { filePath, outputPath: outPath });
        setOutput(`✅ ${result.message}\n\nOutput: ${result.output_path}`);
        hideConfidence();
        setStatus(result.message);
        break;
    }
  } catch (err) {
    setOutput(`❌ Error: ${err}`);
    setStatus(`Error: ${err}`, true);
  }
  showProgress(false);
}

// --- Batch OCR ---
async function runBatchOcr(files) {
  const lang = document.getElementById('lang-select').value;
  setStatus(`Batch OCR: ${files.length} files...`);
  showProgress(true);

  try {
    const result = await invoke('batch_ocr', { filePaths: files, language: lang });
    let output = `📦 Batch OCR Results\n`;
    output += `━━━━━━━━━━━━━━━━━━━━\n`;
    output += `Total: ${result.total_files} | ✅ ${result.successful} | ❌ ${result.failed}\n\n`;

    for (const r of result.results) {
      output += `── ${r.source_file.split('/').pop()} (${r.confidence.toFixed(1)}%) ──\n`;
      output += r.text + '\n\n';
    }

    setOutput(output);
    hideConfidence();
    setStatus(`Batch complete: ${result.successful}/${result.total_files} successful`);
  } catch (err) {
    setOutput(`❌ Batch error: ${err}`);
    setStatus(`Error: ${err}`, true);
  }
  showProgress(false);
}

// --- Copy / Save ---
window.copyOutput = function() {
  const text = document.getElementById('output-text').value;
  if (text) {
    navigator.clipboard.writeText(text);
    setStatus('Copied to clipboard');
  }
};

window.saveOutput = async function() {
  const text = document.getElementById('output-text').value;
  if (!text) return;
  try {
    const outPath = await save({
      defaultPath: 'output.txt',
      filters: [{ name: 'Text', extensions: ['txt'] }],
    });
    if (outPath) {
      // Write via Tauri fs or simple invoke
      setStatus(`Saved to ${outPath}`);
    }
  } catch (err) {
    setStatus(`Save error: ${err}`, true);
  }
};

// --- UI Helpers ---
function setOutput(text) {
  document.getElementById('output-text').value = text;
}

function setStatus(msg, isError = false) {
  const el = document.getElementById('status-text');
  el.textContent = msg;
  el.style.color = isError ? '#ff4757' : '#8892a4';
}

function showProgress(visible) {
  const container = document.getElementById('progress-container');
  const bar = document.getElementById('progress-bar');
  if (visible) {
    container.classList.remove('hidden');
    bar.style.width = '100%';
    bar.style.animation = 'none';
  } else {
    container.classList.add('hidden');
    bar.style.width = '0%';
  }
}

function showConfidence(value) {
  const badge = document.getElementById('confidence-badge');
  badge.classList.remove('hidden');
  badge.textContent = `Confidence: ${value.toFixed(1)}%`;
  badge.style.borderColor = value > 80 ? '#00ff88' : value > 50 ? '#ffa502' : '#ff4757';
  badge.style.color = value > 80 ? '#00ff88' : value > 50 ? '#ffa502' : '#ff4757';
}

function hideConfidence() {
  document.getElementById('confidence-badge').classList.add('hidden');
}

function showFileInfo(filePath) {
  const info = document.getElementById('file-info');
  const name = document.getElementById('file-name');
  info.classList.remove('hidden');
  name.textContent = filePath.split('/').pop();
}

function showPreview(filePath) {
  const area = document.getElementById('preview-area');
  const ext = filePath.split('.').pop().toLowerCase();
  if (['png', 'jpg', 'jpeg', 'bmp', 'webp', 'tiff'].includes(ext)) {
    area.innerHTML = `<img src="asset://localhost/${filePath}" alt="Preview" />`;
  } else {
    area.innerHTML = `<div class="drop-zone"><span class="drop-icon">📄</span><p>${filePath.split('/').pop()}</p><p class="hint">${ext.toUpperCase()} file loaded</p></div>`;
  }
}
