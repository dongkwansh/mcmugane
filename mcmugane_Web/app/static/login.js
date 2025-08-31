const base = (location.pathname.startsWith('/cli')) ? '/cli' : '';
async function login() {
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;
  const res = await fetch(base + '/api/login', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({username, password})
  });
  if (!res.ok) {
    document.getElementById('err').textContent = 'Invalid username or password';
    return;
  }
  const data = await res.json();
  localStorage.setItem('authToken', data.token);
  window.location.href = base + '/';
}
document.getElementById('loginBtn').addEventListener('click', login);
document.getElementById('password').addEventListener('keydown', e => { if (e.key === 'Enter') login(); });
