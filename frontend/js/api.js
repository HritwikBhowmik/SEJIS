/* ============================================================
   SEJIS — Centralized API Client & Auth Utilities
   ============================================================ */

// Use the same origin as the frontend — works when served by FastAPI
const API_BASE = window.location.origin;

/**
 * Returns authorization headers with the Bearer token from localStorage.
 */
function getAuthHeaders() {
  const token = localStorage.getItem('sejis_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
}

/**
 * Checks if user is authenticated. Redirects to auth page if not.
 * Call this at the top of protected pages.
 */
function requireAuth() {
  const token = localStorage.getItem('sejis_token');
  if (!token) {
    window.location.href = 'auth.html';
    return false;
  }
  return true;
}

/**
 * Logs the user out by clearing stored data and redirecting.
 */
function logout() {
  localStorage.removeItem('sejis_token');
  localStorage.removeItem('sejis_session_id');
  window.location.href = 'auth.html';
}

/**
 * Generic GET request with auth.
 * @param {string} path - API path (e.g. '/api/v1/dashboard/dashboard')
 * @returns {Promise<any>} Parsed JSON response
 */
async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders()
    }
  });

  if (response.status === 401) {
    logout();
    throw new Error('Session expired. Please log in again.');
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Request failed (${response.status})`);
  }

  return response.json();
}

/**
 * Generic POST request with JSON body and auth.
 * @param {string} path - API path
 * @param {object} body - JSON body payload
 * @returns {Promise<any>} Parsed JSON response
 */
async function apiPost(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders()
    },
    body: JSON.stringify(body)
  });

  if (response.status === 401) {
    logout();
    throw new Error('Session expired. Please log in again.');
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Request failed (${response.status})`);
  }

  return response.json();
}

/**
 * POST request with FormData (for file uploads) and auth.
 * Does NOT set Content-Type — browser sets it with boundary automatically.
 * @param {string} path - API path
 * @param {FormData} formData - FormData object
 * @returns {Promise<any>} Parsed JSON response
 */
async function apiPostFormData(path, formData) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      ...getAuthHeaders()
    },
    body: formData
  });

  if (response.status === 401) {
    logout();
    throw new Error('Session expired. Please log in again.');
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Request failed (${response.status})`);
  }

  return response.json();
}

/**
 * Download a file (PDF) via authenticated GET request.
 * @param {string} path - API path
 * @param {string} filename - Suggested download filename
 */
async function apiDownloadFile(path, filename) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'GET',
    headers: {
      ...getAuthHeaders()
    }
  });

  if (response.status === 401) {
    logout();
    throw new Error('Session expired. Please log in again.');
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Download failed (${response.status})`);
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || 'report.pdf';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

/**
 * Show a toast notification.
 * @param {string} message - Toast message
 * @param {'success'|'error'|'info'} type - Toast type
 */
function showToast(message, type = 'info') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('removing');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
