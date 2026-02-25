// ── CORE Clipboard Manager — Frontend ──────────────────────────────────────
const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

// ── State ──────────────────────────────────────────────────────────────────
let state = {
  query: '',
  category: 'all',
  items: [],
  offset: 0,
  limit: 50,
  total: 0,
  loading: false,
  monitoring: true,
  selectedIndex: -1,
};

// ── DOM Refs ───────────────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const searchInput = $('#search-input');
const itemsList = $('#items-list');
const itemsContainer = $('#items-container');
const emptyState = $('#empty-state');
const itemCount = $('#item-count');
const statusBtn = $('#status-btn');
const statusText = $('#status-text');
const toastEl = $('#toast');

// ── Debounce ───────────────────────────────────────────────────────────────
function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

// ── Toast ──────────────────────────────────────────────────────────────────
let toastTimer;
function toast(msg) {
  clearTimeout(toastTimer);
  toastEl.textContent = msg;
  toastEl.classList.add('visible');
  toastTimer = setTimeout(() => toastEl.classList.remove('visible'), 2000);
}

// ── Time Formatting ────────────────────────────────────────────────────────
function formatTime(iso) {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diff = now - d;
    if (diff < 60000) return 'just now';
    if (diff < 3600000) return `${Math.floor(diff/60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff/3600000)}h ago`;
    if (diff < 604800000) return `${Math.floor(diff/86400000)}d ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch { return ''; }
}

// ── Category Info ──────────────────────────────────────────────────────────
const catInfo = {
  text: { icon: '📝', label: 'text' },
  link: { icon: '🔗', label: 'link' },
  code: { icon: '💻', label: 'code' },
  image: { icon: '🖼', label: 'image' },
};

// ── Render ─────────────────────────────────────────────────────────────────
function renderItems() {
  const items = state.items;
  emptyState.classList.toggle('visible', items.length === 0);
  itemCount.textContent = `${state.total} item${state.total !== 1 ? 's' : ''}`;

  // Build HTML
  const html = items.map((item, i) => {
    const cat = catInfo[item.category] || catInfo.text;
    const isPinned = item.pinned ? 'pinned' : '';
    const isSelected = i === state.selectedIndex ? 'selected' : '';
    const contentClass = item.category === 'link' ? 'link' :
                         item.category === 'code' ? 'code' : '';
    const needsFade = item.preview.length > 200 || item.preview.split('\n').length > 3;

    return `
      <div class="clip-card ${isPinned} ${isSelected}" data-index="${i}" data-id="${item.id}">
        <div class="card-header">
          <div class="card-meta">
            <span class="card-category">${cat.icon}</span>
            <span class="card-badge ${item.category}">${cat.label}</span>
            ${item.pinned ? '<span class="card-badge" style="color:var(--pin-color);border-color:rgba(255,204,0,0.2)">📌 pinned</span>' : ''}
            ${item.favorite ? '<span class="card-badge" style="color:var(--fav-color);border-color:rgba(255,107,157,0.2)">★ fav</span>' : ''}
            <span class="card-time">${formatTime(item.timestamp)}</span>
          </div>
          <div class="card-actions">
            <button class="card-action-btn copy" onclick="copyItem('${item.id}', event)" title="Copy">📋</button>
            <button class="card-action-btn ${item.pinned ? 'pin-active' : ''}" onclick="togglePin('${item.id}', event)" title="Pin">📌</button>
            <button class="card-action-btn ${item.favorite ? 'fav-active' : ''}" onclick="toggleFav('${item.id}', event)" title="Favorite">★</button>
            <button class="card-action-btn delete" onclick="deleteItem('${item.id}', event)" title="Delete">✕</button>
          </div>
        </div>
        <div class="card-content ${contentClass}">${escapeHtml(item.preview)}${needsFade ? '<div class="card-content-fade"></div>' : ''}</div>
      </div>
    `;
  }).join('');

  itemsList.innerHTML = html;

  // Click to copy
  $$('.clip-card').forEach(card => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('.card-actions')) return;
      const id = card.dataset.id;
      const item = state.items.find(it => it.id === id);
      if (item) copyToClipboard(item);
    });
  });
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ── Data Loading ───────────────────────────────────────────────────────────
async function loadItems(reset = true) {
  if (state.loading) return;
  state.loading = true;

  if (reset) {
    state.offset = 0;
    state.items = [];
    state.selectedIndex = -1;
  }

  try {
    const [items, total] = await Promise.all([
      invoke('get_items', {
        query: state.query,
        category: state.category,
        limit: state.limit,
        offset: state.offset,
      }),
      invoke('get_count', {
        query: state.query,
        category: state.category,
      }),
    ]);

    if (reset) {
      state.items = items;
    } else {
      state.items.push(...items);
    }
    state.total = total;
    state.offset += items.length;

    renderItems();
  } catch (e) {
    console.error('Failed to load items:', e);
  } finally {
    state.loading = false;
  }
}

// ── Infinite Scroll ────────────────────────────────────────────────────────
itemsContainer.addEventListener('scroll', () => {
  const { scrollTop, scrollHeight, clientHeight } = itemsContainer;
  if (scrollHeight - scrollTop - clientHeight < 200 && state.offset < state.total) {
    loadItems(false);
  }
});

// ── Actions ────────────────────────────────────────────────────────────────
async function copyToClipboard(item) {
  try {
    await invoke('copy_to_clipboard', { content: item.content });
    toast('✓ Copied to clipboard');
  } catch (e) {
    console.error('Copy failed:', e);
  }
}

window.copyItem = async (id, e) => {
  e.stopPropagation();
  const item = state.items.find(it => it.id === id);
  if (item) await copyToClipboard(item);
};

window.togglePin = async (id, e) => {
  e.stopPropagation();
  try {
    const pinned = await invoke('toggle_pin', { id });
    const item = state.items.find(it => it.id === id);
    if (item) item.pinned = pinned;
    toast(pinned ? '📌 Pinned' : 'Unpinned');
    await loadItems();
  } catch (e) { console.error(e); }
};

window.toggleFav = async (id, e) => {
  e.stopPropagation();
  try {
    const fav = await invoke('toggle_favorite', { id });
    const item = state.items.find(it => it.id === id);
    if (item) item.favorite = fav;
    toast(fav ? '★ Favorited' : 'Unfavorited');
    renderItems();
  } catch (e) { console.error(e); }
};

window.deleteItem = async (id, e) => {
  e.stopPropagation();
  try {
    await invoke('delete_item', { id });
    state.items = state.items.filter(it => it.id !== id);
    state.total--;
    renderItems();
    toast('Deleted');
  } catch (e) { console.error(e); }
};

// ── Search ─────────────────────────────────────────────────────────────────
const debouncedSearch = debounce(() => {
  state.query = searchInput.value;
  loadItems();
}, 40);

searchInput.addEventListener('input', debouncedSearch);

// ── Filters ────────────────────────────────────────────────────────────────
$$('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    $$('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.category = btn.dataset.category;
    loadItems();
  });
});

// ── Status Toggle ──────────────────────────────────────────────────────────
statusBtn.addEventListener('click', async () => {
  state.monitoring = !state.monitoring;
  await invoke('set_monitoring', { enabled: state.monitoring });
  statusBtn.classList.toggle('active', state.monitoring);
  statusText.textContent = state.monitoring ? 'Monitoring' : 'Paused';
  toast(state.monitoring ? '● Monitoring resumed' : '○ Monitoring paused');
});

// ── Toolbar ────────────────────────────────────────────────────────────────
$('#export-json-btn').addEventListener('click', async () => {
  try {
    const data = await invoke('export_data', { format: 'json' });
    downloadFile('clipboard-history.json', data, 'application/json');
    toast('📥 Exported JSON');
  } catch (e) { console.error(e); }
});

$('#export-csv-btn').addEventListener('click', async () => {
  try {
    const data = await invoke('export_data', { format: 'csv' });
    downloadFile('clipboard-history.csv', data, 'text/csv');
    toast('📊 Exported CSV');
  } catch (e) { console.error(e); }
});

$('#cleanup-btn').addEventListener('click', async () => {
  try {
    const count = await invoke('cleanup_old', { days: 30 });
    toast(`🧹 Cleaned ${count} old items`);
    loadItems();
  } catch (e) { console.error(e); }
});

$('#clear-btn').addEventListener('click', async () => {
  if (!confirm('Delete all unpinned items?')) return;
  try {
    const count = await invoke('clear_unpinned');
    toast(`✕ Cleared ${count} items`);
    loadItems();
  } catch (e) { console.error(e); }
});

function downloadFile(name, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Keyboard Navigation ───────────────────────────────────────────────────
document.addEventListener('keydown', (e) => {
  // Cmd/Ctrl+F → focus search
  if ((e.metaKey || e.ctrlKey) && e.key === 'f') {
    e.preventDefault();
    searchInput.focus();
    searchInput.select();
    return;
  }

  // Escape → clear search
  if (e.key === 'Escape') {
    searchInput.value = '';
    state.query = '';
    searchInput.blur();
    loadItems();
    return;
  }

  // Arrow navigation
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    const dir = e.key === 'ArrowDown' ? 1 : -1;
    state.selectedIndex = Math.max(-1, Math.min(state.items.length - 1, state.selectedIndex + dir));
    renderItems();
    // Scroll into view
    const sel = $('.clip-card.selected');
    if (sel) sel.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    return;
  }

  // Enter → copy selected
  if (e.key === 'Enter' && state.selectedIndex >= 0) {
    e.preventDefault();
    const item = state.items[state.selectedIndex];
    if (item) copyToClipboard(item);
    return;
  }
});

// ── Clipboard Change Listener ──────────────────────────────────────────────
listen('clipboard-changed', () => {
  loadItems();
});

// ── Init ───────────────────────────────────────────────────────────────────
loadItems();
