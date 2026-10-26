// The inline head script applies the initial theme before styles can paint.
const root = document.documentElement;
const system = matchMedia('(prefers-color-scheme: dark)');
let preference = 'auto';
try { preference = localStorage.getItem('manga-translation.theme') || 'auto'; } catch {}
const toggle = document.getElementById('theme');
const auto = document.getElementById('system-theme');

function apply() {
  const theme = preference === 'light' || preference === 'dark'
    ? preference : system.matches ? 'dark' : 'light';
  root.dataset.theme = theme;
  toggle.textContent = theme === 'light' ? 'Dark' : 'Light';
  toggle.setAttribute('aria-label', `Switch to ${theme === 'light' ? 'dark' : 'light'} theme`);
  auto.setAttribute('aria-pressed', String(preference === 'auto'));
}
function save(value) {
  preference = value;
  try { localStorage.setItem('manga-translation.theme', value); } catch {}
  apply();
}
toggle.addEventListener('click', () => save(root.dataset.theme === 'dark' ? 'light' : 'dark'));
auto.addEventListener('click', () => save('auto'));
system.addEventListener('change', () => { if (preference === 'auto') apply(); });
apply();
