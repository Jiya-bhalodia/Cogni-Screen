// ===== COGNISCREEN — SHARED UTILITIES =====

const API_BASE = 'http://localhost:5001';

// ---- API Helpers ----
async function apiFetch(path) {
  const res = await fetch(API_BASE + path);
  return res.json();
}

async function apiPost(path, data) {
  const res = await fetch(API_BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return res.json();
}

// ---- Auth ----
function requireAuth() {
  const raw = localStorage.getItem('user');
  if (!raw) {
    location.href = 'login.html';
    return null;
  }
  return JSON.parse(raw);
}

function requireGuest() {
  if (localStorage.getItem('user')) location.href = 'dashboard.html';
}

function logout() {
  localStorage.removeItem('user');
  location.href = 'login.html';
}

// ---- Toast Notifications ----
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const colors = { success: '#4caf50', error: '#ef5350', warn: '#ffb74d', info: '#4fc3f7' };
  const icons = { success: '✓', error: '✕', warn: '⚠', info: 'ℹ' };
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.style.borderLeft = `3px solid ${colors[type] || colors.info}`;
  toast.innerHTML = `<span style="color:${colors[type]||colors.info};margin-right:8px;">${icons[type]||'ℹ'}</span> ${message}`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
