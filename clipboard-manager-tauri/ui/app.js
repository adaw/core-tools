const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

let currentCategory = 'all';
let currentQuery = '';
let debounceTimer = null;

// Toast notification
function toast(msg) {
  let el = document.querySelector('.toast');
  if (!el) {
    el = document.createElement('div');
    el.className = 'toast';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2000);
}

// Load entries
async function loadEntries() {
  const pinnedOnly = currentCategory === 'pinned';
  const category = pinnedOnly ? null : (currentCategory === 'all' ? null : currentCategory);

  try {
    const entries = await invoke('get_entries', {
      query: currentQuery || null,
      category,
      pinnedOnly,
      limit: 200,
      offset: 0,
    });
    renderEntries(entries);
  } catch (e) {
    console.error('Failed to load entries:', e);
  }
}

// Load stats
async function loadStats() {
  try {
    const s = await invoke('get_stats');
    document.getElementById('stats').innerHTML =
      `<span>📊 ${s.total}</span>` +
      `<span>📌 ${s.pinned}</span>` +
      `<span>📝 ${s.text}</span>` +
      `<span>🔗 ${s.link}</span>` +
      `<span>💻 ${s.code}</span>`;
  } catch (_) {}
}

// Render
function renderEntries(entries) {
  const container = document.getElementById('entries');
  if (!entries.length) {
    container.innerHTML = `
      <div class="empty-state">
        <p>📋 No clipboard entries found</p>
        <p class="sub">${currentQuery ? 'Try a different search' : 'Copy something to get started!'}</p>
      </div>`;
    return;
  }

  container.innerHTML = entries.map(e => `
    <div class="entry ${e.pinned ? 'pinned' : ''}" data-id="${e.id}">
      <div class="entry-header">
        <div class="entry-meta">
          <span class="category-badge ${e.category}">${e.category}</span>
          <span class="entry-time">${formatTime(e.created_at)}</span>
        </div>
        <div class="entry-actions">
          <button onclick="copyEntry(${e.id}, this)" title="Copy">📋</button>
          <button onclick="pinEntry(${e.id})" class="${e.pinned ? 'pin-active' : ''}" title="Pin">📌</button>
          <button onclick="deleteEntry(${e.id})" title="Delete">🗑️</button>
        </div>
      </div>
      <div class="entry-content ${e.category === 'code' ? 'code-content' : ''}">${escapeHtml(truncate(e.content, 300))}</div>
    </div>
  `).join('');
}

function formatTime(ts) {
  try {
    const d = new Date(ts);
    const now = new Date();
    const diff = now - d;
    if (diff < 60000) return 'just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return d.toLocaleDateString();
  } catch (_) {
    return ts;
  }
}

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function truncate(s, max) {
  return s.length > max ? s.slice(0, max) + '…' : s;
}

// Actions
async function copyEntry(id, btn) {
  try {
    const entries = await invoke('get_entries', { query: null, category: null, pinnedOnly: false, limit: 100000, offset: 0 });
    const entry = entries.find(e => e.id === id);
    if (entry) {
      await invoke('copy_to_clipboard', { content: entry.content });
      toast('Copied!');
    }
  } catch (e) {
    console.error(e);
  }
}

async function pinEntry(id) {
  try {
    await invoke('toggle_pin', { id });
    loadEntries();
    loadStats();
  } catch (e) {
    console.error(e);
  }
}

async function deleteEntry(id) {
  try {
    await invoke('delete_entry', { id });
    loadEntries();
    loadStats();
    toast('Deleted');
  } catch (e) {
    console.error(e);
  }
}

// Search
document.getElementById('search').addEventListener('input', (e) => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    currentQuery = e.target.value;
    loadEntries();
  }, 250);
});

// Filters
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentCategory = btn.dataset.category;
    loadEntries();
  });
});

// Export
document.getElementById('exportJson').addEventListener('click', async () => {
  try {
    const data = await invoke('export_entries', { format: 'json' });
    downloadFile('clipboard-export.json', data, 'application/json');
    toast('Exported JSON');
  } catch (e) { console.error(e); }
});

document.getElementById('exportTxt').addEventListener('click', async () => {
  try {
    const data = await invoke('export_entries', { format: 'txt' });
    downloadFile('clipboard-export.txt', data, 'text/plain');
    toast('Exported TXT');
  } catch (e) { console.error(e); }
});

function downloadFile(name, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = name; a.click();
  URL.revokeObjectURL(url);
}

// Clear
document.getElementById('clearAll').addEventListener('click', async () => {
  if (confirm('Clear all unpinned entries?')) {
    try {
      await invoke('clear_all');
      loadEntries();
      loadStats();
      toast('Cleared');
    } catch (e) { console.error(e); }
  }
});

// Listen for clipboard updates
listen('clipboard-updated', () => {
  loadEntries();
  loadStats();
});

// Init
loadEntries();
loadStats();
