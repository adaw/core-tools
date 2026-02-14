const { invoke } = window.__TAURI__ ? window.__TAURI__.core : { invoke: async (cmd, args) => { console.log(`[mock] ${cmd}`, args); return null; } };

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
  });
});

// Source buttons
document.getElementById('btn-caldav').addEventListener('click', () => {
  document.getElementById('caldav-form').classList.toggle('hidden');
});

document.getElementById('btn-ics').addEventListener('click', async () => {
  try {
    const result = await invoke('import_ics_file');
    if (result) refreshSources();
  } catch (e) { console.error(e); }
});

document.getElementById('btn-google').addEventListener('click', async () => {
  try {
    await invoke('add_source', { sourceType: 'google', config: '{}' });
    refreshSources();
  } catch (e) { console.error(e); }
});

document.getElementById('btn-outlook').addEventListener('click', async () => {
  try {
    await invoke('add_source', { sourceType: 'outlook', config: '{}' });
    refreshSources();
  } catch (e) { console.error(e); }
});

// CalDAV connect
document.getElementById('caldav-connect').addEventListener('click', async () => {
  const url = document.getElementById('caldav-url').value;
  const user = document.getElementById('caldav-user').value;
  const pass = document.getElementById('caldav-pass').value;
  try {
    await invoke('add_caldav_source', { url, username: user, password: pass });
    document.getElementById('caldav-form').classList.add('hidden');
    refreshSources();
  } catch (e) { console.error(e); }
});

// Sync
document.getElementById('btn-sync-now').addEventListener('click', async () => {
  const status = document.getElementById('sync-status');
  status.classList.remove('hidden');
  status.textContent = '⏳ Syncing...';
  try {
    const result = await invoke('sync_now', {
      twoWay: document.getElementById('opt-two-way').checked,
      dedup: document.getElementById('opt-dedup').checked,
      conflictStrategy: document.getElementById('conflict-strategy').value,
    });
    status.textContent = result || '✅ Sync complete!';
  } catch (e) {
    status.textContent = `❌ ${e}`;
  }
});

document.getElementById('btn-sync-preview').addEventListener('click', async () => {
  try {
    const changes = await invoke('preview_sync');
    const preview = document.getElementById('sync-preview');
    preview.classList.remove('hidden');
    preview.innerHTML = changes ? changes : '<p class="placeholder">No pending changes.</p>';
  } catch (e) { console.error(e); }
});

// Auto-schedule toggle
document.getElementById('opt-auto').addEventListener('change', (e) => {
  document.getElementById('auto-interval-group').style.display = e.target.checked ? 'flex' : 'none';
});

// Log
document.getElementById('btn-refresh-log').addEventListener('click', refreshLog);
document.getElementById('btn-clear-log').addEventListener('click', async () => {
  try {
    await invoke('clear_log');
    refreshLog();
  } catch (e) { console.error(e); }
});

async function refreshSources() {
  try {
    const sources = await invoke('list_sources');
    const list = document.getElementById('sources-list');
    if (!sources || sources.length === 0) {
      list.innerHTML = '<p class="placeholder">No sources configured yet.</p>';
      return;
    }
    list.innerHTML = sources.map(s =>
      `<div class="log-entry"><span class="action">${s.source_type}</span> — ${s.name || s.url || 'configured'} <span class="timestamp">${s.added_at || ''}</span></div>`
    ).join('');
  } catch (e) { console.error(e); }
}

async function refreshLog() {
  try {
    const entries = await invoke('get_log');
    const list = document.getElementById('log-entries');
    if (!entries || entries.length === 0) {
      list.innerHTML = '<p class="placeholder">No log entries yet.</p>';
      return;
    }
    list.innerHTML = entries.map(e =>
      `<div class="log-entry ${e.level || ''}"><span class="timestamp">${e.timestamp}</span> <span class="action">${e.action}</span> ${e.detail || ''}</div>`
    ).join('');
  } catch (e) { console.error(e); }
}

// Init
refreshSources();
refreshLog();
