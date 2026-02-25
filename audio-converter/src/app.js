const { invoke } = window.__TAURI__.core;
const { open, save } = window.__TAURI__.dialog;

// ─── State ───────────────────────────────────────────────────────────────────
let currentFile = null;
let fileInfo = null;
let waveformData = null;
let audioContext = null;
let audioBuffer = null;
let sourceNode = null;
let isPlaying = false;
let playStartTime = 0;
let playOffset = 0;
let zoom = 1;
let selStart = null;
let selEnd = null;
let mergeFiles = [];
let batchFiles = [];

// ─── DOM ─────────────────────────────────────────────────────────────────────
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const dropZone = $('#dropZone');
const fileInfoBar = $('#fileInfo');
const fileName = $('#fileName');
const fileDetails = $('#fileDetails');
const waveformContainer = $('#waveformContainer');
const canvas = $('#waveformCanvas');
const ctx = canvas.getContext('2d');
const playhead = $('#playhead');
const selection = $('#selection');
const transport = $('#transport');
const progressBar = $('#progressBar');
const progressFill = $('#progressFill');
const progressText = $('#progressText');
const statusText = $('#statusText');

// ─── Tabs ────────────────────────────────────────────────────────────────────
$$('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    $$('.tab').forEach(t => t.classList.remove('active'));
    $$('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    $(`#panel-${tab.dataset.tab}`).classList.add('active');
  });
});

// ─── File Loading ────────────────────────────────────────────────────────────
async function browseFile() {
  const path = await open({
    filters: [{ name: 'Audio', extensions: ['mp3','wav','flac','aac','ogg','wma','aiff','m4a','opus','wv'] }],
    multiple: false,
  });
  if (path) await loadFile(path);
}

$('#btnBrowse').addEventListener('click', browseFile);

dropZone.addEventListener('click', browseFile);
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', async (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  const files = e.dataTransfer?.files;
  if (files?.length) {
    // Tauri drops give us paths
    const path = files[0].path || files[0].name;
    if (path) await loadFile(path);
  }
});

async function loadFile(path) {
  setStatus('Loading file...');
  try {
    fileInfo = await invoke('probe_file', { path });
    currentFile = path;

    fileName.textContent = fileInfo.name;
    const dur = formatTime(fileInfo.duration);
    const br = fileInfo.bitrate ? `${Math.round(fileInfo.bitrate/1000)}kbps` : '?';
    const sz = formatSize(fileInfo.size);
    fileDetails.textContent = `${fileInfo.format.toUpperCase()} • ${dur} • ${br} • ${fileInfo.sample_rate}Hz • ${fileInfo.channels}ch • ${sz}`;

    dropZone.classList.add('has-file');
    fileInfoBar.classList.remove('hidden');
    waveformContainer.classList.remove('hidden');
    transport.classList.remove('hidden');

    // Enable buttons
    $('#btnConvert').disabled = false;
    $('#btnEdit').disabled = false;
    $('#btnSaveMeta').disabled = false;

    // Fill metadata fields
    $('#metaTitle').value = fileInfo.title || '';
    $('#metaArtist').value = fileInfo.artist || '';
    $('#metaAlbum').value = fileInfo.album || '';
    $('#metaYear').value = fileInfo.year || '';
    $('#metaGenre').value = fileInfo.genre || '';

    // Set edit end time
    $('#editEnd').placeholder = fileInfo.duration.toFixed(1);

    await loadWaveform(path);
    await loadAudioForPlayback(path);
    setStatus('File loaded');
  } catch (err) {
    setStatus(`Error: ${err}`);
  }
}

$('#btnRemoveFile').addEventListener('click', () => {
  stopPlayback();
  currentFile = null;
  fileInfo = null;
  waveformData = null;
  audioBuffer = null;
  dropZone.classList.remove('has-file');
  fileInfoBar.classList.add('hidden');
  waveformContainer.classList.add('hidden');
  transport.classList.add('hidden');
  $('#btnConvert').disabled = true;
  $('#btnEdit').disabled = true;
  $('#btnSaveMeta').disabled = true;
  setStatus('Ready');
});

// ─── Waveform ────────────────────────────────────────────────────────────────
async function loadWaveform(path) {
  try {
    waveformData = await invoke('get_waveform_data', { path, numPeaks: 2000 });
    drawWaveform();
  } catch (e) {
    console.error('Waveform error:', e);
  }
}

function drawWaveform() {
  if (!waveformData) return;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const w = rect.width;
  const h = rect.height;
  const peaks = waveformData.peaks;
  const visiblePeaks = Math.floor(peaks.length / zoom);
  const barW = w / visiblePeaks;

  ctx.clearRect(0, 0, w, h);

  // Center line
  ctx.strokeStyle = '#2a2a3a';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, h / 2);
  ctx.lineTo(w, h / 2);
  ctx.stroke();

  // Bars
  const gradient = ctx.createLinearGradient(0, 0, 0, h);
  gradient.addColorStop(0, '#00ff88');
  gradient.addColorStop(0.5, '#00cc6e');
  gradient.addColorStop(1, '#00ff88');

  for (let i = 0; i < visiblePeaks; i++) {
    const peak = peaks[i] || 0;
    const barH = peak * (h * 0.85);
    const x = i * barW;
    ctx.fillStyle = gradient;
    ctx.fillRect(x, (h - barH) / 2, Math.max(barW - 1, 1), barH || 1);
  }

  // Time labels
  $('#timeStart').textContent = '0:00';
  $('#timeEnd').textContent = formatTime(waveformData.duration);
}

window.addEventListener('resize', drawWaveform);

// Zoom
$('#zoomIn').addEventListener('click', () => { zoom = Math.min(zoom * 2, 32); $('#zoomLevel').textContent = `${zoom}x`; drawWaveform(); });
$('#zoomOut').addEventListener('click', () => { zoom = Math.max(zoom / 2, 1); $('#zoomLevel').textContent = `${zoom}x`; drawWaveform(); });

// Waveform click = seek
canvas.addEventListener('click', (e) => {
  if (!waveformData || !audioBuffer) return;
  const rect = canvas.getBoundingClientRect();
  const x = (e.clientX - rect.left) / rect.width;
  const time = x * waveformData.duration;
  if (isPlaying) {
    stopPlayback();
    startPlayback(time);
  } else {
    playOffset = time;
    updatePlayhead(time);
  }
});

// Selection on waveform
let isDragging = false;
canvas.addEventListener('mousedown', (e) => {
  if (!waveformData) return;
  isDragging = true;
  const rect = canvas.getBoundingClientRect();
  selStart = ((e.clientX - rect.left) / rect.width) * waveformData.duration;
  selEnd = selStart;
  selection.classList.remove('hidden');
});

canvas.addEventListener('mousemove', (e) => {
  if (!isDragging || !waveformData) return;
  const rect = canvas.getBoundingClientRect();
  selEnd = ((e.clientX - rect.left) / rect.width) * waveformData.duration;
  const left = Math.min(selStart, selEnd) / waveformData.duration * 100;
  const right = (1 - Math.max(selStart, selEnd) / waveformData.duration) * 100;
  selection.style.left = `${left}%`;
  selection.style.right = `${right}%`;
  // Update edit fields
  $('#editStart').value = Math.min(selStart, selEnd).toFixed(1);
  $('#editEnd').value = Math.max(selStart, selEnd).toFixed(1);
});

canvas.addEventListener('mouseup', () => { isDragging = false; });

// ─── Playback (Web Audio API) ────────────────────────────────────────────────
async function loadAudioForPlayback(path) {
  try {
    if (!audioContext) audioContext = new AudioContext();
    const response = await fetch(`asset://localhost/${path}`);
    const arrayBuffer = await response.arrayBuffer();
    audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
  } catch (e) {
    console.warn('Web Audio playback not available, using fallback');
    // Fallback: try convertFilePath
    audioBuffer = null;
  }
}

function startPlayback(offset = 0) {
  if (!audioBuffer || !audioContext) return;
  stopPlayback();
  sourceNode = audioContext.createBufferSource();
  sourceNode.buffer = audioBuffer;
  const gainNode = audioContext.createGain();
  gainNode.gain.value = parseFloat($('#volume').value);
  sourceNode.connect(gainNode);
  gainNode.connect(audioContext.destination);
  sourceNode.start(0, offset);
  playStartTime = audioContext.currentTime - offset;
  isPlaying = true;
  requestAnimationFrame(updatePlaybackPosition);
  sourceNode.onended = () => { isPlaying = false; };
}

function stopPlayback() {
  if (sourceNode) {
    try { sourceNode.stop(); } catch {}
    sourceNode = null;
  }
  isPlaying = false;
  playOffset = 0;
  updatePlayhead(0);
}

function pausePlayback() {
  if (!isPlaying) return;
  playOffset = audioContext.currentTime - playStartTime;
  if (sourceNode) {
    try { sourceNode.stop(); } catch {}
    sourceNode = null;
  }
  isPlaying = false;
}

function updatePlaybackPosition() {
  if (!isPlaying || !audioContext) return;
  const currentTime = audioContext.currentTime - playStartTime;
  updatePlayhead(currentTime);
  $('#timeCurrent').textContent = formatTime(currentTime);
  if (currentTime < (waveformData?.duration || Infinity)) {
    requestAnimationFrame(updatePlaybackPosition);
  }
}

function updatePlayhead(time) {
  if (!waveformData) return;
  const pct = (time / waveformData.duration) * 100;
  playhead.style.left = `${Math.min(pct, 100)}%`;
}

$('#btnPlay').addEventListener('click', () => startPlayback(playOffset));
$('#btnPause').addEventListener('click', pausePlayback);
$('#btnStop').addEventListener('click', stopPlayback);
$('#volume').addEventListener('input', (e) => {
  // Volume change during playback requires restart
});

// ─── Convert ─────────────────────────────────────────────────────────────────
$('#btnConvert').addEventListener('click', async () => {
  if (!currentFile) return;
  const fmt = $('#convertFormat').value;
  const outputPath = await save({
    defaultPath: currentFile.replace(/\.[^.]+$/, `.${fmt}`),
    filters: [{ name: fmt.toUpperCase(), extensions: [fmt] }],
  });
  if (!outputPath) return;

  showProgress(true);
  setStatus('Converting...');

  try {
    const result = await invoke('convert_audio', {
      opts: {
        input_path: currentFile,
        output_path: outputPath,
        format: fmt,
        bitrate: $('#convertBitrate').value || null,
        sample_rate: $('#convertSampleRate').value ? parseInt($('#convertSampleRate').value) : null,
        channels: $('#convertChannels').value ? parseInt($('#convertChannels').value) : null,
      }
    });
    setProgress(100);
    setStatus(result.success ? `Converted → ${outputPath}` : `Error: ${result.message}`);
  } catch (e) {
    setStatus(`Error: ${e}`);
  }
  setTimeout(() => showProgress(false), 2000);
});

// ─── Edit ────────────────────────────────────────────────────────────────────
// Show/hide fields based on operation
$('#editOp').addEventListener('change', () => {
  const op = $('#editOp').value;
  $('#trimStartGroup').style.display = ['trim','fade_out'].includes(op) ? '' : 'none';
  $('#trimEndGroup').style.display = op === 'trim' ? '' : 'none';
  $('#fadeDurGroup').style.display = ['fade_in','fade_out'].includes(op) ? '' : 'none';
});

$('#btnEdit').addEventListener('click', async () => {
  if (!currentFile) return;
  const op = $('#editOp').value;
  const ext = currentFile.split('.').pop();
  const outputPath = await save({
    defaultPath: currentFile.replace(/\.[^.]+$/, `_${op}.${ext}`),
    filters: [{ name: 'Audio', extensions: [ext] }],
  });
  if (!outputPath) return;

  showProgress(true);
  setStatus(`Applying ${op}...`);

  try {
    const result = await invoke('edit_audio', {
      opts: {
        input_path: currentFile,
        output_path: outputPath,
        operation: op,
        start_time: $('#editStart').value ? parseFloat($('#editStart').value) : null,
        end_time: $('#editEnd').value ? parseFloat($('#editEnd').value) : null,
        fade_duration: $('#fadeDur').value ? parseFloat($('#fadeDur').value) : null,
      }
    });
    setProgress(100);
    setStatus(result.success ? `Edit complete → ${outputPath}` : `Error: ${result.message}`);
  } catch (e) {
    setStatus(`Error: ${e}`);
  }
  setTimeout(() => showProgress(false), 2000);
});

// ─── Merge ───────────────────────────────────────────────────────────────────
$('#btnMergeAdd').addEventListener('click', async () => {
  const paths = await open({
    filters: [{ name: 'Audio', extensions: ['mp3','wav','flac','aac','ogg','wma','aiff','m4a'] }],
    multiple: true,
  });
  if (!paths) return;
  const arr = Array.isArray(paths) ? paths : [paths];
  mergeFiles.push(...arr);
  renderMergeList();
});

function renderMergeList() {
  const list = $('#mergeList');
  if (mergeFiles.length === 0) {
    list.innerHTML = '<p class="placeholder">Add files to merge...</p>';
    $('#btnMerge').disabled = true;
    return;
  }
  list.innerHTML = mergeFiles.map((f, i) =>
    `<div class="merge-item"><span>${f.split('/').pop()}</span><button class="icon-btn" onclick="removeMerge(${i})">✕</button></div>`
  ).join('');
  $('#btnMerge').disabled = mergeFiles.length < 2;
}
window.removeMerge = (i) => { mergeFiles.splice(i, 1); renderMergeList(); };

$('#btnMerge').addEventListener('click', async () => {
  if (mergeFiles.length < 2) return;
  const ext = mergeFiles[0].split('.').pop();
  const outputPath = await save({
    defaultPath: `merged.${ext}`,
    filters: [{ name: 'Audio', extensions: [ext] }],
  });
  if (!outputPath) return;
  showProgress(true);
  setStatus('Merging files...');
  try {
    const result = await invoke('merge_audio', { inputPaths: mergeFiles, outputPath });
    setProgress(100);
    setStatus(result.success ? `Merged → ${outputPath}` : `Error: ${result.message}`);
  } catch (e) {
    setStatus(`Error: ${e}`);
  }
  setTimeout(() => showProgress(false), 2000);
});

// ─── Metadata ────────────────────────────────────────────────────────────────
$('#btnSaveMeta').addEventListener('click', async () => {
  if (!currentFile) return;
  setStatus('Saving metadata...');
  try {
    const result = await invoke('update_metadata', {
      meta: {
        path: currentFile,
        title: $('#metaTitle').value || null,
        artist: $('#metaArtist').value || null,
        album: $('#metaAlbum').value || null,
        year: $('#metaYear').value || null,
        genre: $('#metaGenre').value || null,
      }
    });
    setStatus(result.success ? 'Metadata saved' : `Error: ${result.message}`);
  } catch (e) {
    setStatus(`Error: ${e}`);
  }
});

// ─── Batch ───────────────────────────────────────────────────────────────────
$('#btnBatchAdd').addEventListener('click', async () => {
  const paths = await open({
    filters: [{ name: 'Audio', extensions: ['mp3','wav','flac','aac','ogg','wma','aiff','m4a'] }],
    multiple: true,
  });
  if (!paths) return;
  const arr = Array.isArray(paths) ? paths : [paths];
  arr.forEach(p => batchFiles.push({ path: p, status: 'pending' }));
  renderBatchList();
});

function renderBatchList() {
  const list = $('#batchList');
  if (batchFiles.length === 0) {
    list.innerHTML = '<p class="placeholder">No files added for batch conversion.</p>';
    $('#btnBatchConvert').disabled = true;
    return;
  }
  list.innerHTML = batchFiles.map((f, i) =>
    `<div class="batch-item">
      <span>${f.path.split('/').pop()}</span>
      <span class="status ${f.status}">${f.status === 'done' ? '✓' : f.status === 'error' ? '✗' : '⏳'}</span>
      <button class="icon-btn" onclick="removeBatch(${i})">✕</button>
    </div>`
  ).join('');
  $('#btnBatchConvert').disabled = false;
}
window.removeBatch = (i) => { batchFiles.splice(i, 1); renderBatchList(); };

$('#btnBatchConvert').addEventListener('click', async () => {
  if (batchFiles.length === 0) return;
  const fmt = $('#batchFormat').value;
  showProgress(true);

  for (let i = 0; i < batchFiles.length; i++) {
    const f = batchFiles[i];
    const outPath = f.path.replace(/\.[^.]+$/, `.${fmt}`);
    setStatus(`Converting ${i + 1}/${batchFiles.length}: ${f.path.split('/').pop()}`);
    setProgress(Math.round((i / batchFiles.length) * 100));

    try {
      const result = await invoke('convert_audio', {
        opts: {
          input_path: f.path,
          output_path: outPath,
          format: fmt,
          bitrate: null,
          sample_rate: null,
          channels: null,
        }
      });
      f.status = result.success ? 'done' : 'error';
    } catch {
      f.status = 'error';
    }
    renderBatchList();
  }
  setProgress(100);
  setStatus('Batch conversion complete');
  setTimeout(() => showProgress(false), 2000);
});

// ─── Helpers ─────────────────────────────────────────────────────────────────
function formatTime(s) {
  if (!s || isNaN(s)) return '0:00';
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, '0')}`;
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

function setStatus(msg) { statusText.textContent = msg; }
function showProgress(show) { progressBar.classList.toggle('hidden', !show); }
function setProgress(pct) {
  progressFill.style.width = `${pct}%`;
  progressText.textContent = `${pct}%`;
}

// Init edit field visibility
$('#editOp').dispatchEvent(new Event('change'));
