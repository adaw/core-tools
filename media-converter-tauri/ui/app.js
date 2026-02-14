const { invoke } = window.__TAURI__.core;

const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const formatSelect = document.getElementById('formatSelect');
const qualitySelect = document.getElementById('qualitySelect');
const clearBtn = document.getElementById('clearBtn');
const jobList = document.getElementById('jobList');

// Drop zone
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
  handleFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', (e) => {
  handleFiles(e.target.files);
  fileInput.value = '';
});

async function handleFiles(files) {
  const format = formatSelect.value;
  const quality = qualitySelect.value;

  for (const file of files) {
    try {
      await invoke('start_conversion', {
        request: {
          input_path: file.path || file.name,
          output_format: format,
          quality: quality,
        }
      });
    } catch (err) {
      console.error('Conversion error:', err);
    }
  }
}

clearBtn.addEventListener('click', async () => {
  await invoke('clear_completed');
});

async function cancelJob(id) {
  await invoke('cancel_job', { jobId: id });
}

function renderJobs(jobs) {
  jobList.innerHTML = jobs.map(job => {
    const name = job.input_path.split('/').pop().split('\\').pop();
    const statusClass = `status-${job.status}`;
    const pct = Math.round(job.progress);
    const statusText = job.status === 'running' ? `${pct}%`
      : job.status === 'done' ? '✓ Done'
      : job.status === 'error' ? '✗ Error'
      : job.status === 'cancelled' ? '⊘ Cancelled'
      : 'Pending';
    const cancelBtn = job.status === 'running'
      ? `<button class="btn-cancel" onclick="cancelJob('${job.id}')">Cancel</button>`
      : '';

    return `
      <div class="job-item">
        <div class="job-info">
          <div class="job-name">${name}</div>
          <div class="job-detail">→ ${job.format.toUpperCase()} · ${job.quality}</div>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" style="width:${pct}%"></div>
        </div>
        <div class="job-status ${statusClass}">${statusText}</div>
        ${cancelBtn}
      </div>
    `;
  }).join('');
}

// Poll jobs
setInterval(async () => {
  try {
    const jobs = await invoke('get_jobs');
    renderJobs(jobs);
  } catch (e) {
    // not ready yet
  }
}, 500);
