const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
const { open: openDialog } = window.__TAURI__.dialog;

let selectedImage = null;
let selectedDrive = null;

// Step navigation
function goToStep(step) {
  document.querySelectorAll('.panel').forEach(p => p.style.display = 'none');
  document.getElementById(`step${step}`).style.display = 'block';

  document.querySelectorAll('.step').forEach(s => {
    const n = parseInt(s.dataset.step);
    s.classList.toggle('active', n === step);
    s.classList.toggle('done', n < step);
  });

  if (step === 2) refreshDrives();
  if (step === 3) updateSummary();
}

// Step 1: Select Image
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');

dropZone.addEventListener('click', async () => {
  const path = await openDialog({
    filters: [{ name: 'Disk Images', extensions: ['iso', 'img', 'dmg', 'zip'] }],
    multiple: false,
  });
  if (path) loadImage(path);
});

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
  dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  if (e.dataTransfer.files.length > 0) {
    loadImage(e.dataTransfer.files[0].path);
  }
});

async function loadImage(path) {
  try {
    selectedImage = await invoke('select_image', { path });
    document.getElementById('imageName').textContent = selectedImage.name;
    document.getElementById('imageSize').textContent = selectedImage.size_human;
    document.getElementById('imageFormat').textContent = selectedImage.format;
    document.getElementById('imageInfo').style.display = 'block';
    document.getElementById('hashResult').textContent = '';
    document.getElementById('btnNext1').disabled = false;
  } catch (e) {
    alert('Error: ' + e);
  }
}

async function computeHash(algo) {
  if (!selectedImage) return;
  document.getElementById('hashResult').textContent = 'Computing...';
  try {
    const hash = await invoke('compute_hash', { path: selectedImage.path, algorithm: algo });
    document.getElementById('hashResult').textContent = `${algo.toUpperCase()}: ${hash}`;
  } catch (e) {
    document.getElementById('hashResult').textContent = 'Error: ' + e;
  }
}

// Step 2: Drives
async function refreshDrives() {
  const list = document.getElementById('driveList');
  list.innerHTML = '<p class="hint">Scanning for USB drives...</p>';
  selectedDrive = null;
  document.getElementById('btnNext2').disabled = true;
  document.getElementById('warningBox').style.display = 'none';

  try {
    const drives = await invoke('list_drives');
    if (drives.length === 0) {
      list.innerHTML = '<p class="hint">No USB drives found. Insert a USB drive and click Refresh.</p>';
      return;
    }

    list.innerHTML = '';
    drives.forEach(drive => {
      const el = document.createElement('div');
      el.className = 'drive-item';
      el.innerHTML = `
        <div class="drive-icon">💾</div>
        <div class="drive-details">
          <div class="drive-name">${drive.name}</div>
          <div class="drive-meta">${drive.device} · ${drive.size_human}</div>
        </div>
      `;
      el.addEventListener('click', () => selectDrive(drive, el));
      list.appendChild(el);
    });
  } catch (e) {
    list.innerHTML = `<p class="hint" style="color:var(--danger)">Error: ${e}</p>`;
  }
}

function selectDrive(drive, el) {
  document.querySelectorAll('.drive-item').forEach(d => d.classList.remove('selected'));
  el.classList.add('selected');
  selectedDrive = drive;
  document.getElementById('warningBox').style.display = 'block';
  document.getElementById('btnNext2').disabled = false;
}

// Step 3: Flash
function updateSummary() {
  document.getElementById('summaryImage').textContent = selectedImage ? selectedImage.name : '—';
  document.getElementById('summaryDrive').textContent = selectedDrive ? `${selectedDrive.name} (${selectedDrive.device})` : '—';
  document.getElementById('summaryVerify').textContent = document.getElementById('verifyCheck').checked ? 'Yes' : 'No';
}

async function startFlash() {
  if (!selectedImage || !selectedDrive) return;

  const ok = confirm(`⚠️ ALL DATA on ${selectedDrive.name} (${selectedDrive.device}) will be PERMANENTLY ERASED!\n\nAre you sure you want to continue?`);
  if (!ok) return;

  document.getElementById('flashButtons').style.display = 'none';
  document.getElementById('cancelBtn').style.display = 'flex';
  document.getElementById('progressContainer').style.display = 'block';

  try {
    await invoke('flash_image', {
      imagePath: selectedImage.path,
      device: selectedDrive.device,
      verify: document.getElementById('verifyCheck').checked,
    });
  } catch (e) {
    alert('Flash error: ' + e);
    resetFlashUI();
  }
}

async function cancelFlash() {
  try {
    await invoke('cancel_flash');
  } catch (_) {}
}

// Listen for progress events
listen('flash-progress', (event) => {
  const p = event.payload;
  const circle = document.getElementById('progressCircle');
  const circumference = 2 * Math.PI * 85; // r=85

  const offset = circumference - (p.percent / 100) * circumference;
  circle.style.strokeDashoffset = offset;

  document.getElementById('progressPercent').textContent = `${Math.round(p.percent)}%`;
  document.getElementById('progressPhase').textContent = p.message;

  if (p.phase === 'writing' || p.phase === 'verifying') {
    document.getElementById('progressSpeed').textContent = `${p.speed_mbps.toFixed(1)} MB/s`;
    if (p.eta_seconds > 0) {
      const min = Math.floor(p.eta_seconds / 60);
      const sec = p.eta_seconds % 60;
      document.getElementById('progressEta').textContent = `ETA: ${min}m ${sec}s`;
    }
  }

  if (p.phase === 'done') {
    document.getElementById('cancelBtn').style.display = 'none';
    document.getElementById('doneMessage').style.display = 'block';
    circle.style.stroke = 'var(--accent)';
  }

  if (p.phase === 'error') {
    alert('Error: ' + p.message);
    resetFlashUI();
  }
});

function resetFlashUI() {
  document.getElementById('flashButtons').style.display = 'flex';
  document.getElementById('cancelBtn').style.display = 'none';
  document.getElementById('progressContainer').style.display = 'none';
  document.getElementById('doneMessage').style.display = 'none';
}

function resetApp() {
  selectedImage = null;
  selectedDrive = null;
  document.getElementById('btnNext1').disabled = true;
  document.getElementById('imageInfo').style.display = 'none';
  resetFlashUI();
  goToStep(1);
}

// Make functions global
window.goToStep = goToStep;
window.computeHash = computeHash;
window.refreshDrives = refreshDrives;
window.startFlash = startFlash;
window.cancelFlash = cancelFlash;
window.resetApp = resetApp;
