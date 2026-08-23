/* ─── LOADER ─────────────────────────────────────────────── */
const loaderMessages = [
  'Booting secure environment...',
  'Loading encryption modules...',
  'Scanning for vulnerabilities...',
  'Establishing secure channel...',
  'Mounting portfolio filesystem...',
  'Access granted. Welcome.'
];
let loadPct = 0;
const loaderBar = document.getElementById('loader-bar');
const loaderTxt = document.getElementById('loader-txt');
const loader    = document.getElementById('loader');

function advanceLoader() {
  const step = Math.random() * 15 + 5;
  loadPct = Math.min(loadPct + step, 100);
  loaderBar.style.width = loadPct + '%';
  const idx = Math.min(Math.floor(loadPct / 17), loaderMessages.length - 1);
  loaderTxt.textContent = loaderMessages[idx];
  if (loadPct < 100) {
    setTimeout(advanceLoader, Math.random() * 250 + 120);
  } else {
    loaderTxt.textContent = 'Access granted. Welcome.';
    setTimeout(() => {
      loader.classList.add('hidden');
      startTyping();
      animateStats();
    }, 600);
  }
}
window.addEventListener('load', () => setTimeout(advanceLoader, 300));
/* ─── CUSTOM CURSOR ──────────────────────────────────────── */
const cursor     = document.getElementById('cursor');
const cursorRing = document.getElementById('cursor-ring');
let mx = 0, my = 0, rx = 0, ry = 0;

document.addEventListener('mousemove', e => {
  mx = e.clientX; my = e.clientY;
  cursor.style.transform = `translate(${mx - 6}px, ${my - 6}px)`;
});

function animCursor() {
  rx += (mx - rx - 18) * 0.12;
  ry += (my - ry - 18) * 0.12;
  cursorRing.style.transform = `translate(${rx}px, ${ry}px)`;
  requestAnimationFrame(animCursor);
}
animCursor();

document.addEventListener('mousedown', () => document.body.classList.add('clicking'));
document.addEventListener('mouseup',   () => document.body.classList.remove('clicking'));

/* ─── SCROLL REVEAL ──────────────────────────────────────── */
const revealEls = document.querySelectorAll('.reveal');
const observer  = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('visible');
      if (e.target.closest('#skills')) animateSkillBars();
    }
  });
}, { threshold: 0.12 });
revealEls.forEach(el => observer.observe(el));

/* ─── SKILL BARS ─────────────────────────────────────────── */
let skillsAnimated = false;
function animateSkillBars() {
  if (skillsAnimated) return;
  skillsAnimated = true;
  document.querySelectorAll('.skill-fill').forEach((bar, i) => {
    const w = bar.dataset.width;
    setTimeout(() => { bar.style.width = w + '%'; }, i * 80);
  });
}

/* ─── COUNTER STATS ──────────────────────────────────────── */
function animateStats() {
  document.querySelectorAll('.stat-num').forEach(el => {
    const target = parseInt(el.dataset.target);
    let cur = 0;
    const step = Math.ceil(target / 20);
    const timer = setInterval(() => {
      cur = Math.min(cur + step, target);
      el.textContent = cur + (target > 9 ? '+' : '');
      if (cur >= target) clearInterval(timer);
    }, 80);
  });
}
const aboutObs = new IntersectionObserver(entries => {
  if (entries[0].isIntersecting) { animateStats(); aboutObs.disconnect(); }
}, { threshold: 0.3 });
const aboutEl = document.getElementById('about');
if (aboutEl) aboutObs.observe(aboutEl);

/* ─── NAV ACTIVE + MOBILE ────────────────────────────────── */
const sections = document.querySelectorAll('section[id]');
const navLinks = document.querySelectorAll('.nav-links a');
const toggle   = document.getElementById('nav-toggle');
const navMenu  = document.getElementById('nav-links');

window.addEventListener('scroll', () => {
  let cur = '';
  sections.forEach(s => {
    if (window.scrollY >= s.offsetTop - 200) cur = s.id;
  });
  navLinks.forEach(a => {
    a.classList.toggle('active', a.getAttribute('href') === '#' + cur);
  });
});

toggle.addEventListener('click', () => navMenu.classList.toggle('open'));
navLinks.forEach(a => a.addEventListener('click', () => navMenu.classList.remove('open')));


document.getElementById('btn-send').addEventListener('click', async () => {
  const name    = document.getElementById('f-name').value.trim();
  const email   = document.getElementById('f-email').value.trim();
  const subject = document.getElementById('f-subject').value.trim();
  const message = document.getElementById('f-msg').value.trim();

  if (!name || !email || !subject || !message) {
    alert('Fill all fields');
    return;
  }

  try {
    const res = await fetch('http://localhost:5000/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, subject, message })
    });

    const data = await res.json();

    if (data.success) {
      document.getElementById('form-success').style.display = 'block';
      document.getElementById('btn-send').style.display = 'none';
     // 🧹 Clear form fields
      document.getElementById('f-name').value = '';
      document.getElementById('f-email').value = '';
      document.getElementById('f-subject').value = '';
      document.getElementById('f-msg').value = '';
    } else {
      alert('Failed to send');
    }

  } catch (err) {
    alert('Server error');
  }
});