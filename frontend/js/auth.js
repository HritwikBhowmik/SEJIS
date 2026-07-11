/* ============================================================
   SEJIS — Authentication Page Logic
   Handles registration & login form submissions
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  // If already logged in, redirect to dashboard
  const token = localStorage.getItem('sejis_token');
  if (token) {
    window.location.href = 'dashboard.html';
    return;
  }

  setupTabs();
  setupForms();
});

/**
 * Set up tab switching between Sign In and Register panels.
 */
function setupTabs() {
  const tabs = document.querySelectorAll('.auth-tab');
  const panels = document.querySelectorAll('.auth-panel');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;

      // Update active tab
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      // Update active panel
      panels.forEach(p => p.classList.remove('active'));
      document.getElementById(target).classList.add('active');

      // Clear messages
      clearMessages();
    });
  });
}

/**
 * Set up form submission handlers.
 */
function setupForms() {
  // Login form
  const loginForm = document.getElementById('login-form');
  loginForm.addEventListener('submit', handleLogin);

  // Register form
  const registerForm = document.getElementById('register-form');
  registerForm.addEventListener('submit', handleRegister);
}

/**
 * Handle login form submission.
 */
async function handleLogin(e) {
  e.preventDefault();

  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  const submitBtn = e.target.querySelector('button[type="submit"]');
  const msgContainer = document.getElementById('login-message');

  if (!email || !password) {
    showMessage(msgContainer, 'Please fill in all fields.', 'error');
    return;
  }

  // Set loading state
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner"></span> Signing in...';
  clearMessages();

  try {
    const data = await apiPost('/api/v1/auth/login', { email, password });

    if (data.access_token) {
      localStorage.setItem('sejis_token', data.access_token);
      showMessage(msgContainer, 'Login successful! Redirecting...', 'success');

      setTimeout(() => {
        window.location.href = 'dashboard.html';
      }, 800);
    }
  } catch (error) {
    showMessage(msgContainer, error.message || 'Login failed. Please check your credentials.', 'error');
    submitBtn.disabled = false;
    submitBtn.textContent = 'Sign In';
  }
}

/**
 * Handle registration form submission.
 */
async function handleRegister(e) {
  e.preventDefault();

  const fullName = document.getElementById('register-name').value.trim();
  const email = document.getElementById('register-email').value.trim();
  const password = document.getElementById('register-password').value;
  const confirmPassword = document.getElementById('register-confirm-password').value;
  const submitBtn = e.target.querySelector('button[type="submit"]');
  const msgContainer = document.getElementById('register-message');

  // Validation
  if (!fullName || !email || !password || !confirmPassword) {
    showMessage(msgContainer, 'Please fill in all fields.', 'error');
    return;
  }

  if (password.length < 6) {
    showMessage(msgContainer, 'Password must be at least 6 characters.', 'error');
    return;
  }

  if (password !== confirmPassword) {
    showMessage(msgContainer, 'Passwords do not match.', 'error');
    return;
  }

  // Set loading state
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner"></span> Creating account...';
  clearMessages();

  try {
    const data = await apiPost('/api/v1/auth/register', {
      email,
      password,
      full_name: fullName
    });

    showMessage(msgContainer, 'Registration successful! You can now sign in.', 'success');
    submitBtn.disabled = false;
    submitBtn.textContent = 'Create Account';

    // Auto-switch to login tab after a brief delay
    setTimeout(() => {
      document.querySelector('[data-tab="login-panel"]').click();
      // Pre-fill email in login form
      document.getElementById('login-email').value = email;
    }, 1500);

  } catch (error) {
    showMessage(msgContainer, error.message || 'Registration failed. Please try again.', 'error');
    submitBtn.disabled = false;
    submitBtn.textContent = 'Create Account';
  }
}

/**
 * Display a message in the given container.
 */
function showMessage(container, message, type) {
  container.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
}

/**
 * Clear all message containers.
 */
function clearMessages() {
  document.querySelectorAll('.auth-message').forEach(el => el.innerHTML = '');
}
