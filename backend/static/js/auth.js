/**
 * static/auth.js - Client-Side Controller & Theme Engine
 */

// Helper to show custom neon alerts
function showNotification(message, type = 'info') {
  const existingAlert = document.getElementById('cyber-notification');
  if (existingAlert) {
    existingAlert.remove();
  }

  const alertDiv = document.createElement('div');
  alertDiv.id = 'cyber-notification';
  alertDiv.className = `cyber-alert ${type}`;
  
  let icon = '⚡';
  if (type === 'success') icon = '✓';
  if (type === 'error') icon = '✗';
  
  alertDiv.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
  document.body.appendChild(alertDiv);

  setTimeout(() => {
    alertDiv.classList.add('show');
  }, 50);

  setTimeout(() => {
    alertDiv.classList.remove('show');
    setTimeout(() => {
      alertDiv.remove();
    }, 400);
  }, 4000);
}

function updateUserProfileUI(username) {
  const nameElements = document.querySelectorAll('.profile-name');
  nameElements.forEach(el => el.textContent = username || 'Operator');
}

// DOM Hookups
document.addEventListener('DOMContentLoaded', () => {
  // Always load current user details from active session
  fetch(`${API_URL}/api/auth/me`, { credentials: 'include' })
    .then(res => res.json())
    .then(data => {
      if (data && data.authenticated) {
        localStorage.setItem('currentUser', JSON.stringify({ username: data.username, email: data.email }));
        updateUserProfileUI(data.username);
      }
    })
    .catch(() => {
      updateUserProfileUI('Operator');
    });
});

// Theme Controller
document.addEventListener('DOMContentLoaded', () => {
  const btnThemeToggle = document.getElementById('btn-theme-toggle');
  const themeIcon = document.getElementById('theme-toggle-icon');
  const themeText = document.getElementById('theme-toggle-text');

  function applyTheme(theme) {
    const isBright = theme === 'bright';
    if (isBright) {
      document.body.classList.add('theme-bright');
      document.documentElement.classList.add('theme-bright');
      if (themeIcon) themeIcon.textContent = '🌙';
      if (themeText) themeText.textContent = 'Cyber Dark Mode';
    } else {
      document.body.classList.remove('theme-bright');
      document.documentElement.classList.remove('theme-bright');
      if (themeIcon) themeIcon.textContent = '☀️';
      if (themeText) themeText.textContent = 'High Visibility Mode';
    }
    localStorage.setItem('qc_theme', theme);
  }

  const savedTheme = localStorage.getItem('qc_theme') || 'dark';
  applyTheme(savedTheme);

  if (btnThemeToggle) {
    btnThemeToggle.addEventListener('click', () => {
      const currentTheme = document.body.classList.contains('theme-bright') ? 'bright' : 'dark';
      const newTheme = currentTheme === 'bright' ? 'dark' : 'bright';
      applyTheme(newTheme);
      showNotification(
        newTheme === 'bright' ? '☀️ High-Visibility Bright Mode Activated' : '🌙 Cyber Dark Mode Activated',
        'info'
      );
    });
  }
});
