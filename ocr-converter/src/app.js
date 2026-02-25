// ─── CORE OCR Converter — Frontend ──────────────────────────────────────────
const { invoke } = window.__TAURI__.core;
const { open, save } = window.__TAURI__.dialog;

// ─── State ───────────────────────────────────────────────────────────────────
let files = [];
let currentMode = 'ocr';
let isProcessing = false;

// ─── DOM Elements ────────────────────────────────────────────────────────────
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const dropZone = $('#dropZone');
const fileList = $('#fileList');
const fileCount = $('#fileCount');
const emptyState = $('#emptyState');
const btnConvert = $('#btnConvert');
const btnConvertLabel = $('#btnConvertLabel');
const progressContainer = $('#progressContainer');
const progressFill = $('#progressFill');
const progressText = $('#progressText');
const statusText = $('#statusText');
const statusRight = $('#statusRight');
const resultContainer = $('#resultContainer');

// ─── Init ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  checkDependencies();
  setupEventListeners();
  updateUI();
});

async function checkDependencies() {
  try {
    const deps = await invoke('check_dependencies');
    const depDot = $('#depDot');
    const depLabel = $('#depLabel');
    
    const allOk = deps.tesseract && deps.poppler && deps.libreoffice;
    const partial = deps.tesseract || deps.poppler;
    
    if (allOk) {
      depDot.className = 'dep-dot ok';
      depLabel.textContent = 'All tools ready';
    } else if (partial) {
      depDot.className = 'dep-dot ok';
      const missing = [];
      if (!deps.tesseract) missing.push('tesseract');
      if (!deps.poppler) missing.push('poppler');
      if (!deps.libreoffice) missing.push('libreoffice');
      depLabel.textContent = `Missing: ${missing.join(', ')}`;
    } else {
      depDot.className = 'dep-dot err';
      depLabel.textContent = 'No tools found';
    }

    // Load available tesseract languages
    if (deps.tesseract) {
      try {
        const langs = await invoke('get_tesseract_languages');
        const select = $('#ocrLang');
        select.innerHTML = '';
        
        const commonLangs = {
          'eng': 'English',
          'ces': 'Czech (Čeština)',
          'deu': 'German (Deutsch)',
          'fra': 'French',
          'spa': 'Spanish',
          'ita': 'Italian',
          'pol': 'Polish',
          'rus': 'Russian',
        };
        
        // Add available common langs first
        for (const [code, name] of Object.entries(commonLangs)) {
          if (langs.includes(code)) {
            const opt = document.createElement('option');
            opt.value = code;
            opt.textContent = name;
            select.appendChild(opt);
          }
        }

        // Add multi-lang combos
        if (langs.includes('eng') && langs.includes('ces')) {
          const opt = document.createElement('option');
          opt.value = 'eng+ces';
          opt.textContent = 'English + Czech';
          select.appendChild(opt);
        }
        if (langs.includes('eng') && langs.includes('deu')) {
          const opt = document.createElement('option');
          opt.value = 'eng+deu';
          opt.textContent = 'English + German';
          select.appendChild(opt);
        }

        // Add separator and remaining langs
        const remaining = langs.filter(l => !Object.keys(commonLangs).includes(l) && l !== 'osd');
        if (remaining.length > 0) {
          const sep = document.createElement('option');
          sep.disabled = true;
          sep.textContent = '───────────';
          select.appendChild(sep);
          for (const lang of remaining) {
            const opt = document.createElement('option');
            opt.value = lang;
            opt.textContent = lang;
            select.appendChild(opt);
          }
        }
      } catch (e) {
        console.log('Could not list languages:', e);
      }
    }
  } catch (e) {
    console.error('Dependency check failed:', e);
  }
}

// ─── Event Listeners ─────────────────────────────────────────────────────────
function setupEventListeners() {
  // Drop zone
  dropZone.addEventListener('click', addFiles);
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('drag-over');
  });
  dropZone.addEventListener('drop', async (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const droppedFiles = Array.from(e.dataTransfer.files).map(f => f.path || f.name);
    if (droppedFiles.length) {
      const validated = await invoke('validate_files', { paths: droppedFiles });
      files = [...files, ...validated];
      updateUI();
    }
  });

  // Buttons
  $('#btnAddFiles').addEventListener('click', addFiles);
  $('#btnClear').addEventListener('click', () => { files = []; updateUI(); setStatus('Cleared'); });
  btnConvert.addEventListener('click', runConversion);

  // Mode tabs
  $$('.mode-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      currentMode = tab.dataset.mode;
      $$('.mode-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      
      // Show correct options panel
      $$('.mode-options').forEach(o => o.classList.add('hidden'));
      const optId = {
        'ocr': 'optOcr',
        'pdf2docx': 'optPdf2docx',
        'docx2pdf': 'optDocx2pdf',
        'pdf2text': 'optPdf2text',
        'img2pdf': 'optImg2pdf',
      }[currentMode];
      if (optId) $(`#${optId}`).classList.remove('hidden');
      
      updateConvertButton();
    });
  });

  // Preview tabs
  $$('.preview-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      $$('.preview-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      
      if (tab.dataset.preview === 'files') {
        $('#previewFiles').classList.remove('hidden');
        $('#previewResult').classList.add('hidden');
      } else {
        $('#previewFiles').classList.add('hidden');
        $('#previewResult').classList.remove('hidden');
      }
    });
  });
}

async function addFiles() {
  try {
    const selected = await open({
      multiple: true,
      filters: [
        { name: 'All Supported', extensions: ['pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'tiff', 'tif', 'bmp', 'gif', 'webp', 'txt'] },
        { name: 'PDF', extensions: ['pdf'] },
        { name: 'Word', extensions: ['doc', 'docx'] },
        { name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'tiff', 'tif', 'bmp', 'gif', 'webp'] },
      ]
    });
    
    if (selected) {
      const paths = Array.isArray(selected) ? selected : [selected];
      const validated = await invoke('validate_files', { paths });
      files = [...files, ...validated];
      updateUI();
    }
  } catch (e) {
    console.error('File selection error:', e);
  }
}

// ─── UI Updates ──────────────────────────────────────────────────────────────
function updateUI() {
  fileCount.textContent = `${files.length} file${files.length !== 1 ? 's' : ''}`;
  
  if (files.length === 0) {
    emptyState.classList.remove('hidden');
    fileList.innerHTML = '';
  } else {
    emptyState.classList.add('hidden');
    renderFileList();
  }
  
  updateConvertButton();
}

function renderFileList() {
  fileList.innerHTML = files.map((f, i) => `
    <div class="file-item" data-index="${i}">
      <span class="file-type-badge ${f.file_type}">${f.file_type}</span>
      <span class="file-name" title="${f.path}">${f.name}</span>
      <span class="file-size">${formatSize(f.size)}</span>
      <button class="file-remove" onclick="removeFile(${i})" title="Remove">✕</button>
    </div>
  `).join('');
}

function updateConvertButton() {
  const labels = {
    'ocr': '🔍 Run OCR',
    'pdf2docx': '📝 Convert to Word',
    'docx2pdf': '📄 Convert to PDF',
    'pdf2text': '📋 Extract Text',
    'img2pdf': '🖼 Create PDF',
  };
  btnConvertLabel.textContent = labels[currentMode] || 'Convert';
  btnConvert.disabled = files.length === 0 || isProcessing;
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function setStatus(text, right = '') {
  statusText.textContent = text;
  statusRight.textContent = right;
}

function showProgress(current, total, text) {
  progressContainer.classList.remove('hidden');
  progressFill.style.width = `${(current / total) * 100}%`;
  progressText.textContent = text;
}

function hideProgress() {
  progressContainer.classList.add('hidden');
  progressFill.style.width = '0%';
}

// Make removeFile global
window.removeFile = function(index) {
  files.splice(index, 1);
  updateUI();
};

// ─── Conversion Logic ────────────────────────────────────────────────────────
async function runConversion() {
  if (isProcessing || files.length === 0) return;
  
  isProcessing = true;
  updateConvertButton();
  
  // Switch to result tab
  $$('.preview-tab').forEach(t => t.classList.remove('active'));
  $$('.preview-tab')[1].classList.add('active');
  $('#previewFiles').classList.add('hidden');
  $('#previewResult').classList.remove('hidden');
  resultContainer.innerHTML = '';

  try {
    switch (currentMode) {
      case 'ocr': await runOCR(); break;
      case 'pdf2docx': await runPdf2Docx(); break;
      case 'docx2pdf': await runDocx2Pdf(); break;
      case 'pdf2text': await runPdf2Text(); break;
      case 'img2pdf': await runImg2Pdf(); break;
    }
  } catch (e) {
    resultContainer.innerHTML = `<div class="empty-state"><div class="empty-icon">❌</div><p>Error: ${e}</p></div>`;
    setStatus('Error: ' + e);
  }

  isProcessing = false;
  hideProgress();
  updateConvertButton();
}

async function runOCR() {
  const language = $('#ocrLang').value;
  const imageFiles = files.filter(f => f.file_type === 'image' || f.file_type === 'pdf');
  
  if (imageFiles.length === 0) {
    setStatus('No image or PDF files to OCR');
    return;
  }

  resultContainer.innerHTML = '';
  
  for (let i = 0; i < imageFiles.length; i++) {
    const file = imageFiles[i];
    showProgress(i + 1, imageFiles.length, `OCR: ${file.name}`);
    setStatus(`Processing ${file.name}…`, `${i + 1}/${imageFiles.length}`);

    try {
      let filesToOcr = [];
      
      if (file.file_type === 'pdf') {
        // Convert PDF pages to images first
        const images = await invoke('pdf_to_images', { path: file.path });
        filesToOcr = images.map((img, idx) => ({ path: img, name: `${file.name} (page ${idx + 1})` }));
      } else {
        filesToOcr = [{ path: file.path, name: file.name }];
      }

      for (const f of filesToOcr) {
        const result = await invoke('ocr_image', { path: f.path, language });
        appendOcrResult({ ...result, file: f.name });
      }
    } catch (e) {
      appendErrorResult(file.name, e);
    }
  }
  
  setStatus('OCR complete', `${imageFiles.length} files processed`);
}

async function runPdf2Docx() {
  const pdfFiles = files.filter(f => f.file_type === 'pdf');
  if (pdfFiles.length === 0) { setStatus('No PDF files selected'); return; }

  for (let i = 0; i < pdfFiles.length; i++) {
    const file = pdfFiles[i];
    showProgress(i + 1, pdfFiles.length, `Converting: ${file.name}`);
    setStatus(`Converting ${file.name}…`);

    try {
      const outputPath = file.path.replace(/\.pdf$/i, '.docx');
      const result = await invoke('pdf_to_docx', { pdfPath: file.path, outputPath });
      appendConversionResult(file.name, result);
    } catch (e) {
      appendErrorResult(file.name, e);
    }
  }
  setStatus('Conversion complete');
}

async function runDocx2Pdf() {
  const docxFiles = files.filter(f => f.file_type === 'docx');
  if (docxFiles.length === 0) { setStatus('No DOCX files selected'); return; }

  for (let i = 0; i < docxFiles.length; i++) {
    const file = docxFiles[i];
    showProgress(i + 1, docxFiles.length, `Converting: ${file.name}`);
    setStatus(`Converting ${file.name}…`);

    try {
      const outputPath = file.path.replace(/\.docx?$/i, '.pdf');
      const result = await invoke('docx_to_pdf', { docxPath: file.path, outputPath });
      appendConversionResult(file.name, result);
    } catch (e) {
      appendErrorResult(file.name, e);
    }
  }
  setStatus('Conversion complete');
}

async function runPdf2Text() {
  const pdfFiles = files.filter(f => f.file_type === 'pdf');
  if (pdfFiles.length === 0) { setStatus('No PDF files selected'); return; }

  for (let i = 0; i < pdfFiles.length; i++) {
    const file = pdfFiles[i];
    showProgress(i + 1, pdfFiles.length, `Extracting: ${file.name}`);
    setStatus(`Extracting text from ${file.name}…`);

    try {
      const text = await invoke('pdf_to_text', { path: file.path });
      appendOcrResult({ file: file.name, text, confidence: -1, language: 'N/A' });
    } catch (e) {
      appendErrorResult(file.name, e);
    }
  }
  setStatus('Text extraction complete');
}

async function runImg2Pdf() {
  const imageFiles = files.filter(f => f.file_type === 'image');
  if (imageFiles.length === 0) { setStatus('No image files selected'); return; }

  showProgress(1, 1, 'Creating PDF…');
  setStatus('Creating multi-page PDF…');

  try {
    const outputPath = await save({
      defaultPath: 'combined.pdf',
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });

    if (outputPath) {
      const paths = imageFiles.map(f => f.path);
      const result = await invoke('images_to_pdf', { imagePaths: paths, outputPath });
      appendConversionResult('combined.pdf', result);
      setStatus('PDF created successfully');
    } else {
      setStatus('Cancelled');
    }
  } catch (e) {
    appendErrorResult('Image → PDF', e);
  }
}

// ─── Result Rendering ────────────────────────────────────────────────────────
function appendOcrResult(result) {
  const confClass = result.confidence < 0 ? '' : result.confidence >= 80 ? 'confidence-high' : result.confidence >= 50 ? 'confidence-mid' : 'confidence-low';
  const confText = result.confidence < 0 ? 'N/A' : `${result.confidence.toFixed(1)}%`;
  
  const block = document.createElement('div');
  block.className = 'result-block';
  block.innerHTML = `
    <div class="result-header">
      <span class="result-filename">${result.file}</span>
      ${result.confidence >= 0 ? `<span class="result-confidence ${confClass}">Confidence: ${confText}</span>` : ''}
    </div>
    <div class="result-text">${escapeHtml(result.text)}</div>
    <div class="result-actions">
      <button class="btn" onclick="copyText(this)">📋 Copy</button>
      <button class="btn" onclick="saveText(this)">💾 Save as TXT</button>
    </div>
  `;
  resultContainer.appendChild(block);
}

function appendConversionResult(filename, result) {
  const block = document.createElement('div');
  block.className = 'conversion-success';
  block.innerHTML = `
    <span class="check">✅</span>
    <div class="info">
      <h4>${filename}</h4>
      <p>${result.message}</p>
      <p style="font-family: var(--font-mono); font-size: 11px; color: var(--text-dim); margin-top: 4px;">${result.output_path}</p>
    </div>
  `;
  resultContainer.appendChild(block);
}

function appendErrorResult(filename, error) {
  const block = document.createElement('div');
  block.className = 'conversion-success';
  block.style.borderColor = 'rgba(255, 68, 102, 0.3)';
  block.style.background = 'rgba(255, 68, 102, 0.1)';
  block.innerHTML = `
    <span class="check">❌</span>
    <div class="info">
      <h4 style="color: var(--danger);">${filename}</h4>
      <p>${error}</p>
    </div>
  `;
  resultContainer.appendChild(block);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Global helpers
window.copyText = function(btn) {
  const text = btn.closest('.result-block').querySelector('.result-text').textContent;
  navigator.clipboard.writeText(text);
  btn.textContent = '✅ Copied';
  setTimeout(() => { btn.textContent = '📋 Copy'; }, 1500);
};

window.saveText = async function(btn) {
  const text = btn.closest('.result-block').querySelector('.result-text').textContent;
  try {
    const path = await save({
      defaultPath: 'output.txt',
      filters: [{ name: 'Text', extensions: ['txt'] }],
    });
    if (path) {
      await invoke('save_text_to_file', { text, outputPath: path });
      btn.textContent = '✅ Saved';
      setTimeout(() => { btn.textContent = '💾 Save as TXT'; }, 1500);
    }
  } catch (e) {
    console.error('Save failed:', e);
  }
};
