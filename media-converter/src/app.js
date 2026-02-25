// ============================================
// CORE Media Converter — Frontend Logic
// ============================================

const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
const { open } = window.__TAURI__.dialog;

// ---- State ----
let files = []; // { path, name, size, duration, format, isVideo, codec, resolution, bitrate, thumbnail }
let selectedFormat = 'mp4';
let selectedQuality = 'medium';
let formatType = 'video'; // 'video' | 'audio'
let outputDir = '';
let activeJobs = {}; // jobId -> { fileName, progress, status }

const VIDEO_FORMATS = [
  { name: 'MP4', ext: 'mp4', desc: 'H.264/AAC' },
  { name: 'MKV', ext: 'mkv', desc: 'Matroska' },
  { name: 'AVI', ext: 'avi', desc: 'Legacy' },
  { name: 'MOV', ext: 'mov', desc: 'QuickTime' },
  { name: 'WebM', ext: 'webm', desc: 'VP9/Opus' },
];
const AUDIO_FORMATS = [
  { name: 'MP3', ext: 'mp3', desc: 'MPEG Audio' },
  { name: 'WAV', ext: 'wav', desc: 'Lossless' },
  { name: 'FLAC', ext: 'flac', desc: 'Lossless' },
  { name: 'AAC', ext: 'aac', desc: 'Advanced' },
  { name: 'OGG', ext: 'ogg', desc: 'Vorbis' },
];

// ---- Init ----
document.addEventListener('DOMContentLoaded', async () => {
  // Set default output dir
  outputDir = await getDesktopPath();
  document.getElementById('output-path').textContent = shortenPath(outputDir);

  // Check FFmpeg
  try {
    const ver = await invoke('check_ffmpeg');
    const statusEl = document.getElementById('ffmpeg-status');
    statusEl.querySelector('.status-dot').classList.add('ok');
    statusEl.querySelector('.status-text').textContent = ver.split(' ').slice(0, 3).join(' ');
  } catch (e) {
    const statusEl = document.getElementById('ffmpeg-status');
    statusEl.querySelector('.status-dot').classList.add('err');
    statusEl.querySelector('.status-text').textContent = 'FFmpeg not found';
    document.getElementById('ffmpeg-warning').classList.remove('hidden');
  }

  renderFormats();
  setupEventListeners();
  setupProgressListener();
});

async function getDesktopPath() {
  // Simple heuristic
  const home = await getHomePath();
  return home + '/Desktop';
}

async function getHomePath() {
  // Use a Tauri env approach or fallback
  try {
    // Tauri 2 doesn't expose path directly without plugin, use a simple approach
    return '/Users/' + (await getUserName());
  } catch {
    return '~';
  }
}

async function getUserName() {
  // We'll just parse from file paths or use a default
  if (files.length > 0) {
    const parts = files[0].path.split('/');
    if (parts[1] === 'Users' && parts.length > 2) return parts[2];
  }
  return 'user';
}

function shortenPath(p) {
  if (!p) return '~/Desktop';
  const home = p.match(/^\/Users\/[^/]+/);
  if (home) return p.replace(home[0], '~');
  return p;
}

// ---- Event Listeners ----
function setupEventListeners() {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');

  // Drag & Drop
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
    const droppedFiles = Array.from(e.dataTransfer.files);
    for (const f of droppedFiles) {
      await addFile(f.path || f.name);
    }
  });

  // File input
  fileInput.addEventListener('change', async (e) => {
    for (const f of e.target.files) {
      await addFile(f.path || f.name);
    }
    fileInput.value = '';
  });

  // Format tabs
  document.querySelectorAll('.format-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.format-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      formatType = tab.dataset.type;
      renderFormats();
    });
  });

  // Quality presets
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedQuality = btn.dataset.quality;
      const customOpts = document.getElementById('custom-options');
      if (selectedQuality === 'custom') {
        customOpts.classList.remove('hidden');
      } else {
        customOpts.classList.add('hidden');
      }
    });
  });

  // Output dir
  document.getElementById('choose-dir-btn').addEventListener('click', chooseOutputDir);
  document.getElementById('output-path').addEventListener('click', chooseOutputDir);

  // Convert
  document.getElementById('convert-btn').addEventListener('click', startConversion);

  // Clear all
  document.getElementById('clear-all-btn').addEventListener('click', () => {
    files = [];
    renderFileList();
    updateConvertButton();
  });

  // Cancel all
  document.getElementById('cancel-all-btn').addEventListener('click', cancelAll);

  // Done
  document.getElementById('done-btn').addEventListener('click', () => {
    document.getElementById('progress-overlay').classList.add('hidden');
    activeJobs = {};
  });
}

// ---- Files ----
async function addFile(path) {
  if (!path || files.some(f => f.path === path)) return;
  try {
    const info = await invoke('probe_file', { path });
    let thumbnail = null;
    if (info.is_video) {
      try {
        thumbnail = await invoke('get_thumbnail', { path });
      } catch {}
    }
    files.push({ ...info, thumbnail });
    renderFileList();
    updateConvertButton();
  } catch (e) {
    console.error('Failed to probe file:', e);
  }
}

function removeFile(index) {
  files.splice(index, 1);
  renderFileList();
  updateConvertButton();
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
  return (bytes / 1073741824).toFixed(2) + ' GB';
}

function formatDuration(secs) {
  if (!secs || secs <= 0) return '';
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  if (m > 60) {
    const h = Math.floor(m / 60);
    return `${h}:${(m % 60).toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function renderFileList() {
  const container = document.getElementById('file-items');
  const count = document.getElementById('file-count');
  count.textContent = files.length;

  if (files.length === 0) {
    container.innerHTML = '';
    return;
  }

  container.innerHTML = files.map((f, i) => `
    <div class="file-item">
      <div class="file-thumb">
        ${f.thumbnail
          ? `<img src="${f.thumbnail}" alt="" />`
          : f.is_video ? '🎬' : '🎵'
        }
      </div>
      <div class="file-info">
        <div class="file-name" title="${f.name}">${f.name}</div>
        <div class="file-meta">
          ${formatSize(f.size)}
          ${f.duration ? ' · ' + formatDuration(f.duration) : ''}
          ${f.resolution ? ' · ' + f.resolution : ''}
          ${f.codec ? ' · ' + f.codec : ''}
        </div>
      </div>
      <button class="file-remove" onclick="removeFile(${i})" title="Remove">✕</button>
    </div>
  `).join('');
}

// ---- Formats ----
function renderFormats() {
  const grid = document.getElementById('format-grid');
  const formats = formatType === 'video' ? VIDEO_FORMATS : AUDIO_FORMATS;

  // Auto-select first if current selection doesn't match type
  const currentFormats = formats.map(f => f.ext);
  if (!currentFormats.includes(selectedFormat)) {
    selectedFormat = formats[0].ext;
  }

  grid.innerHTML = formats.map(f => `
    <div class="format-card ${f.ext === selectedFormat ? 'active' : ''}"
         onclick="selectFormat('${f.ext}')">
      <div class="fmt-name">${f.name}</div>
      <div class="fmt-ext">${f.desc}</div>
    </div>
  `).join('');
}

function selectFormat(ext) {
  selectedFormat = ext;
  renderFormats();
  updateConvertButton();
}

// ---- Output Dir ----
async function chooseOutputDir() {
  try {
    const selected = await open({ directory: true, multiple: false });
    if (selected) {
      outputDir = selected;
      document.getElementById('output-path').textContent = shortenPath(outputDir);
    }
  } catch (e) {
    console.error('Dir selection error:', e);
  }
}

// ---- Convert ----
function updateConvertButton() {
  const btn = document.getElementById('convert-btn');
  btn.disabled = files.length === 0;
  btn.querySelector('.btn-convert-text').textContent =
    files.length > 1 ? `Convert ${files.length} Files` : 'Convert';
}

async function startConversion() {
  if (files.length === 0) return;

  // Ensure output dir
  if (!outputDir) {
    outputDir = files[0].path.substring(0, files[0].path.lastIndexOf('/'));
  }

  activeJobs = {};
  const overlay = document.getElementById('progress-overlay');
  overlay.classList.remove('hidden');
  document.getElementById('done-btn').classList.add('hidden');
  document.getElementById('cancel-all-btn').classList.remove('hidden');

  const progressItems = document.getElementById('progress-items');
  progressItems.innerHTML = '';

  for (const file of files) {
    const request = {
      file_path: file.path,
      output_dir: outputDir,
      format: selectedFormat,
      quality: selectedQuality,
      codec: document.getElementById('opt-codec')?.value || null,
      bitrate: document.getElementById('opt-bitrate')?.value || null,
      resolution: document.getElementById('opt-resolution')?.value || null,
      sample_rate: document.getElementById('opt-samplerate')?.value || null,
    };

    try {
      const jobId = await invoke('convert_file', { request });
      activeJobs[jobId] = { fileName: file.name, progress: 0, status: 'converting' };

      progressItems.innerHTML += `
        <div class="progress-item" id="job-${jobId}">
          <div class="progress-item-header">
            <span class="progress-item-name" title="${file.name}">${file.name}</span>
            <span class="progress-item-status" id="status-${jobId}">Starting...</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" id="fill-${jobId}" style="width: 0%"></div>
          </div>
        </div>
      `;
    } catch (e) {
      console.error('Failed to start conversion:', e);
    }
  }

  updateOverallProgress();
}

async function cancelAll() {
  for (const jobId of Object.keys(activeJobs)) {
    if (activeJobs[jobId].status === 'converting') {
      try {
        await invoke('cancel_job', { jobId });
      } catch {}
    }
  }
}

// ---- Progress Listener ----
function setupProgressListener() {
  listen('conversion-progress', (event) => {
    const { job_id, file_name, progress, status, message } = event.payload;

    if (activeJobs[job_id]) {
      activeJobs[job_id].progress = progress;
      activeJobs[job_id].status = status;
    }

    // Update individual progress
    const fill = document.getElementById(`fill-${job_id}`);
    const statusEl = document.getElementById(`status-${job_id}`);
    if (fill) {
      fill.style.width = `${progress}%`;
      if (status === 'done') fill.classList.add('done');
      if (status === 'error') fill.classList.add('error');
    }
    if (statusEl) {
      statusEl.textContent = message;
      statusEl.className = 'progress-item-status';
      if (status === 'done' || status === 'error' || status === 'cancelled') {
        statusEl.classList.add(status);
      }
    }

    updateOverallProgress();
  });
}

function updateOverallProgress() {
  const jobs = Object.values(activeJobs);
  if (jobs.length === 0) return;

  const totalProgress = jobs.reduce((sum, j) => sum + j.progress, 0) / jobs.length;
  document.getElementById('overall-fill').style.width = `${totalProgress}%`;
  document.getElementById('overall-text').textContent = `${Math.round(totalProgress)}%`;

  // Check if all done
  const allDone = jobs.every(j => j.status === 'done' || j.status === 'error' || j.status === 'cancelled');
  if (allDone) {
    document.getElementById('done-btn').classList.remove('hidden');
    document.getElementById('cancel-all-btn').classList.add('hidden');
    document.getElementById('progress-header').querySelector('h2').textContent = 'Complete!';
  }
}
