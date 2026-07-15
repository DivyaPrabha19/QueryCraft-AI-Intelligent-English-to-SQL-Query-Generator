/**
 * static/auth.js - Client-Side Authentication Controller using Flask Sessions
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

// Router guards checking Flask session state
const pathname = window.location.pathname;
const isAuthPage = pathname === '/' || pathname.endsWith('index.html') || pathname.includes('index') || pathname === '';
const isDashboardPage = pathname.endsWith('dashboard.html') || pathname.includes('dashboard');

function checkAuth() {
  fetch(`${API_URL}/api/auth/me`, { credentials: 'include' })
    .then(res => res.json())
    .then(data => {
      if (data.authenticated) {
        // Cache user details locally
        localStorage.setItem('currentUser', JSON.stringify({ username: data.username, email: data.email }));
        
        // If on Auth page, redirect to dashboard
        if (isAuthPage) {
          window.location.href = 'dashboard.html';
        } else {
          // If on dashboard, update username displays
          updateUserProfileUI(data.username);
        }
      } else {
        localStorage.removeItem('currentUser');
        if (isDashboardPage) {
          window.location.href = 'index.html';
        }
      }
    })
    .catch(() => {
      if (isDashboardPage) {
        window.location.href = 'index.html';
      }
    });
}

function updateUserProfileUI(username) {
  const nameElements = document.querySelectorAll('.profile-name');
  nameElements.forEach(el => el.textContent = username);
}

// Run auth checks immediately
checkAuth();

// Sign Up Handler
function handleSignUp(username, email, password, confirmPassword) {
  if (!username || !email || !password || !confirmPassword) {
    showNotification('All fields are required!', 'error');
    return;
  }
  
  if (password !== confirmPassword) {
    showNotification('Passwords do not match!', 'error');
    return;
  }

  if (password.length < 6) {
    showNotification('Password must be at least 6 characters.', 'error');
    return;
  }

  showNotification('CREATING SECURE PROFILE...', 'info');

  fetch(`${API_URL}/api/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password }),
    credentials: 'include'
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      showNotification('ACCESS GRANTED: Account registered!', 'success');
      setTimeout(() => {
        window.location.href = 'dashboard.html';
      }, 1500);
    } else {
      showNotification(data.message || 'Signup failed.', 'error');
    }
  })
  .catch(err => {
    showNotification('Server communication failure.', 'error');
    console.error(err);
  });
}

// Sign In Handler
function handleSignIn(email, password) {
  if (!email || !password) {
    showNotification('Please enter email and password.', 'error');
    return;
  }

  showNotification('DECRYPTING CREDENTIALS...', 'info');

  fetch(`${API_URL}/api/auth/signin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
    credentials: 'include'
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      showNotification('ACCESS APPROVED. TERMINAL UNLOCKED.', 'success');
      setTimeout(() => {
        window.location.href = 'dashboard.html';
      }, 1200);
    } else {
      showNotification(data.message || 'Access denied: Invalid identity.', 'error');
    }
  })
  .catch(err => {
    showNotification('Authentication server offline.', 'error');
    console.error(err);
  });
}

// Logout Handler
function logout() {
  fetch(`${API_URL}/api/auth/logout`, { method: 'POST', credentials: 'include' })
    .then(() => {
      localStorage.removeItem('currentUser');
      showNotification('CONNECTION TERMINATED.', 'info');
      setTimeout(() => {
        window.location.href = 'index.html';
      }, 1000);
    })
    .catch(() => {
      window.location.href = 'index.html';
    });
}

// DOM Hookups
document.addEventListener('DOMContentLoaded', () => {
  if (isAuthPage) {
    const tabSignIn = document.getElementById('tab-signin');
    const tabSignUp = document.getElementById('tab-signup');
    const formSignIn = document.getElementById('form-signin');
    const formSignUp = document.getElementById('form-signup');
    const authCard = document.querySelector('.auth-card');
    
    if (tabSignIn && tabSignUp) {
      tabSignIn.addEventListener('click', () => {
        tabSignIn.classList.add('active');
        tabSignIn.classList.remove('pink');
        tabSignUp.classList.remove('active', 'pink');
        formSignIn.classList.add('active');
        formSignUp.classList.remove('active');
        authCard.style.animation = 'neonPulseCyan 8s infinite alternate';
        authCard.style.borderColor = 'var(--border-cyan)';
      });

      tabSignUp.addEventListener('click', () => {
        tabSignUp.classList.add('active', 'pink');
        tabSignIn.classList.remove('active');
        formSignUp.classList.add('active');
        formSignIn.classList.remove('active');
        authCard.style.animation = 'neonPulsePink 8s infinite alternate';
        authCard.style.borderColor = 'var(--border-pink)';
      });
    }

    if (formSignIn) {
      formSignIn.addEventListener('submit', (e) => {
        e.preventDefault();
        const email = document.getElementById('signin-email').value.trim();
        const password = document.getElementById('signin-password').value;
        handleSignIn(email, password);
      });
    }

    if (formSignUp) {
      formSignUp.addEventListener('submit', (e) => {
        e.preventDefault();
        const username = document.getElementById('signup-username').value.trim();
        const email = document.getElementById('signup-email').value.trim();
        const password = document.getElementById('signup-password').value;
        const confirm = document.getElementById('signup-confirm').value;
        handleSignUp(username, email, password, confirm);
      });
    }

    // Dynamic Google button rendering
    fetch(`${API_URL}/api/status/engine`, { credentials: 'include' })
      .then(res => res.json())
      .then(data => {
        if (data.google_client_id) {
          const container = document.getElementById('google-btn-container');
          if (container) {
            container.innerHTML = `
              <div id="g_id_onload"
                   data-client_id="${data.google_client_id}"
                   data-context="signin"
                   data-ux_mode="popup"
                   data-callback="handleGoogleAuth"
                   data-auto_prompt="false">
              </div>
              <div class="g_id_signin"
                   data-type="standard"
                   data-shape="rectangular"
                   data-theme="dark"
                   data-text="signin_with"
                   data-size="large"
                   data-logo_alignment="left"
                   data-width="400">
              </div>
            `;
            // Load button rendering if SDK is ready
            if (window.google && window.google.accounts && window.google.accounts.id) {
              window.google.accounts.id.initialize({
                client_id: data.google_client_id,
                callback: window.handleGoogleAuth
              });
              const btn = document.querySelector('.g_id_signin');
              if (btn) {
                window.google.accounts.id.renderButton(btn, {
                  type: "standard",
                  shape: "rectangular",
                  theme: "dark",
                  text: "signin_with",
                  size: "large",
                  logo_alignment: "left",
                  width: 400
                });
              }
            }
          }
        }
      })
      .catch(err => console.error("Error loading engine status:", err));
  }

  if (isDashboardPage) {
    const btnLogout = document.getElementById('btn-logout');
    if (btnLogout) {
      btnLogout.addEventListener('click', logout);
    }
  }
});

// Google Identity Services Auth Callback
window.handleGoogleAuth = function(response) {
  if (!response || !response.credential) {
    showNotification('No Google credentials received.', 'error');
    return;
  }
  
  showNotification('VERIFYING IDENTITY WITH GOOGLE...', 'info');
  
  fetch(`${API_URL}/api/auth/google`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential: response.credential }),
    credentials: 'include'
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      showNotification('ACCESS APPROVED via Google.', 'success');
      setTimeout(() => {
        window.location.href = 'dashboard.html';
      }, 1200);
    } else {
      showNotification(data.message || 'Google Authentication Failed', 'error');
    }
  })
  .catch(err => {
    showNotification('OAuth Server Offline.', 'error');
    console.error(err);
  });
};

// Google Auth Simulator Modal Handlers
window.openGoogleSimulator = function() {
  const modal = document.getElementById('google-simulator-modal');
  if (modal) {
    modal.style.display = 'flex';
  }
};

window.closeGoogleSimulator = function() {
  const modal = document.getElementById('google-simulator-modal');
  if (modal) {
    modal.style.display = 'none';
  }
};

// Safe base64url encoder in browser JS
function base64UrlEncode(str) {
  return btoa(unescape(encodeURIComponent(str)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

window.submitGoogleSimulation = function() {
  const name = document.getElementById('sim-name').value.trim();
  const email = document.getElementById('sim-email').value.trim();
  
  if (!name || !email) {
    showNotification('Name and email are required to simulate Google authorization.', 'error');
    return;
  }
  
  // Construct a simulated JWT structure: header.payload.signature
  const header = base64UrlEncode(JSON.stringify({ alg: "none", typ: "JWT" }));
  const payload = base64UrlEncode(JSON.stringify({ email: email, name: name, sub: "simulated_google_sub_12345" }));
  const mockCredential = `${header}.${payload}.mocksignature`;
  
  closeGoogleSimulator();
  
  // Call the same callback as real Google Sign-In
  window.handleGoogleAuth({ credential: mockCredential });
};


