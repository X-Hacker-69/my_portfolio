'use strict';

/* ──────────────────────────────────────────────────────────────────
   ENTRY POINT
   ──────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initParticles();
  initNeuralBg();
  initCardNeural();
  initTyping();
  initCursor();
  initGSAP();
  initMagnetic();
  initTilt();
  initTerminal();
  initCodeReveal();
  initOrbit();
  initPanelGlow();
});


/* ══════════════════════════════════════════════════════════════════
   1. FLOATING PARTICLE SYSTEM
   ══════════════════════════════════════════════════════════════════ */
function initParticles() {
  const canvas = document.getElementById('particlesCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let particles = [];
  let W, H;

  const COLORS = [
    'rgba(0,207,255,',    // neon blue
    'rgba(155,95,255,',   // neon purple
    'rgba(0,255,140,',    // neon green
    'rgba(255,255,255,',  // white
  ];

  const resize = () => {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  };
  resize();
  window.addEventListener('resize', resize);

  class Particle {
    constructor(stagger = false) {
      this.reset(stagger);
    }
    reset(stagger = false) {
      this.x      = Math.random() * W;
      this.y      = stagger ? Math.random() * H : H + 10;
      this.sz     = Math.random() * 1.6 + 0.2;
      this.vx     = (Math.random() - 0.5) * 0.25;
      this.vy     = -(Math.random() * 0.45 + 0.1);
      this.alpha  = Math.random() * 0.55 + 0.1;
      this.color  = COLORS[Math.floor(Math.random() * COLORS.length)];
      this.life   = stagger ? Math.random() * 300 : 0;
      this.maxLife= Math.random() * 350 + 200;
      this.twinkle= Math.random() * Math.PI * 2;
      this.twinkleSpeed = 0.02 + Math.random() * 0.04;
    }
    update() {
      this.x   += this.vx;
      this.y   += this.vy;
      this.life++;
      this.twinkle += this.twinkleSpeed;
      if (this.life > this.maxLife || this.y < -10) this.reset();
    }
    draw() {
      const t   = Math.sin(this.twinkle) * 0.5 + 0.5;
      const a   = this.alpha * t * (Math.min(this.life, 40) / 40)
                             * (Math.min(this.maxLife - this.life, 40) / 40);
      ctx.save();
      ctx.globalAlpha = a;
      ctx.shadowBlur  = 8;
      ctx.shadowColor = this.color + '1)';
      ctx.fillStyle   = this.color + '1)';
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.sz, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
  }

  // Seed with staggered lifetimes so they don't all appear at once
  for (let i = 0; i < 180; i++) particles.push(new Particle(true));

  const animate = () => {
    ctx.clearRect(0, 0, W, H);
    particles.forEach(p => { p.update(); p.draw(); });
    requestAnimationFrame(animate);
  };
  animate();
}


/* ══════════════════════════════════════════════════════════════════
   2. NEURAL NETWORK — FULL-PAGE BACKGROUND
   ══════════════════════════════════════════════════════════════════ */
function initNeuralBg() {
  const canvas = document.getElementById('neuralCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let nodes = [];
  let W, H;
  const MAX_DIST = 220;
  const NODE_COUNT = () => Math.max(20, Math.floor((W * H) / 26000));

  const buildNodes = () => {
    nodes = Array.from({ length: NODE_COUNT() }, () => ({
      x:     Math.random() * W,
      y:     Math.random() * H,
      vx:    (Math.random() - 0.5) * 0.38,
      vy:    (Math.random() - 0.5) * 0.38,
      r:     Math.random() * 2.5 + 0.8,
      phase: Math.random() * Math.PI * 2,
    }));
  };

  const resize = () => {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
    buildNodes();
  };
  resize();
  window.addEventListener('resize', resize);

  const animate = () => {
    ctx.clearRect(0, 0, W, H);

    // Move nodes
    nodes.forEach(n => {
      n.x += n.vx; n.y += n.vy;
      n.phase += 0.018;
      if (n.x < 0 || n.x > W) n.vx *= -1;
      if (n.y < 0 || n.y > H) n.vy *= -1;
    });

    // Draw connections
    for (let i = 0; i < nodes.length - 1; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx   = nodes[i].x - nodes[j].x;
        const dy   = nodes[i].y - nodes[j].y;
        const dist = Math.hypot(dx, dy);
        if (dist < MAX_DIST) {
          const a = (1 - dist / MAX_DIST) * 0.12;
          ctx.save();
          ctx.globalAlpha = a;
          ctx.strokeStyle = '#00cfff';
          ctx.lineWidth   = 0.6;
          ctx.beginPath();
          ctx.moveTo(nodes[i].x, nodes[i].y);
          ctx.lineTo(nodes[j].x, nodes[j].y);
          ctx.stroke();
          ctx.restore();
        }
      }
    }

    // Draw node dots
    nodes.forEach(n => {
      const pulse = Math.sin(n.phase) * 0.45 + 0.55;
      ctx.save();
      ctx.globalAlpha  = 0.22 + pulse * 0.28;
      ctx.fillStyle    = '#00cfff';
      ctx.shadowBlur   = 10 * pulse;
      ctx.shadowColor  = '#00cfff';
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r * pulse, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    });

    requestAnimationFrame(animate);
  };
  animate();
}


/* ══════════════════════════════════════════════════════════════════
   3. NEURAL NETWORK — WORKSPACE CARD BACKGROUND
   ══════════════════════════════════════════════════════════════════ */
function initCardNeural() {
  const canvas = document.getElementById('neuralBg');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let nodes = [];

  const setupCanvas = () => {
    canvas.width  = canvas.offsetWidth  || 540;
    canvas.height = canvas.offsetHeight || 380;
    nodes = Array.from({ length: 14 }, () => ({
      x:     Math.random() * canvas.width,
      y:     Math.random() * canvas.height,
      vx:    (Math.random() - 0.5) * 0.6,
      vy:    (Math.random() - 0.5) * 0.6,
      phase: Math.random() * Math.PI * 2,
    }));
  };
  setupCanvas();

  // Re-size when card dimensions settle
  const ro = new ResizeObserver(() => setupCanvas());
  ro.observe(canvas.parentElement);

  const draw = () => {
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    nodes.forEach(n => {
      n.x += n.vx; n.y += n.vy; n.phase += 0.025;
      if (n.x < 0 || n.x > W) n.vx *= -1;
      if (n.y < 0 || n.y > H) n.vy *= -1;
    });

    for (let i = 0; i < nodes.length - 1; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dist = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y);
        if (dist < 170) {
          ctx.save();
          ctx.globalAlpha = (1 - dist / 170) * 0.4;
          ctx.strokeStyle = '#00cfff';
          ctx.lineWidth   = 0.9;
          ctx.beginPath();
          ctx.moveTo(nodes[i].x, nodes[i].y);
          ctx.lineTo(nodes[j].x, nodes[j].y);
          ctx.stroke();
          ctx.restore();
        }
      }
    }

    nodes.forEach(n => {
      const p = Math.sin(n.phase) * 0.5 + 0.5;
      ctx.save();
      ctx.globalAlpha = 0.4 + p * 0.4;
      ctx.fillStyle   = '#00cfff';
      ctx.shadowBlur  = 12;
      ctx.shadowColor = '#00cfff';
      ctx.beginPath();
      ctx.arc(n.x, n.y, 1.6 + p * 0.8, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    });

    requestAnimationFrame(draw);
  };
  draw();
}


/* ══════════════════════════════════════════════════════════════════
   4. TYPING ANIMATION
   ══════════════════════════════════════════════════════════════════ */
function initTyping() {
  const el = document.getElementById('typingDisplay');
  if (!el) return;

  const ROLES = [
    'AI Enthusiast',
    'UI/UX Designer',
    'Web Developer',
    'Problem Solver',
    'Creative Coder',
  ];

  let rIdx = 0, cIdx = 0, deleting = false, paused = false;

  const type = () => {
    if (paused) { paused = false; setTimeout(type, 1300); return; }

    const role = ROLES[rIdx];

    if (!deleting) {
      el.textContent = role.slice(0, ++cIdx);
      if (cIdx >= role.length) { deleting = true; paused = true; }
      setTimeout(type, 72 + Math.random() * 48);
    } else {
      el.textContent = role.slice(0, --cIdx);
      if (cIdx <= 0) {
        deleting = false;
        rIdx = (rIdx + 1) % ROLES.length;
        setTimeout(type, 300);
      } else {
        setTimeout(type, 35 + Math.random() * 20);
      }
    }
  };

  setTimeout(type, 1800);   // delay so GSAP entrance finishes first
}


/* ══════════════════════════════════════════════════════════════════
   5. CUSTOM CURSOR
   ══════════════════════════════════════════════════════════════════ */
function initCursor() {
  const glow = document.getElementById('cursorGlow');
  const dot  = document.getElementById('cursorDot');
  if (!glow || !dot) return;

  // Only activate on devices that support hover
  if (window.matchMedia('(hover: none)').matches) {
    glow.style.display = 'none';
    dot.style.display  = 'none';
    document.body.style.cursor = 'auto';
    return;
  }

  let mx = -400, my = -400;
  let gx = -400, gy = -400;

  document.addEventListener('mousemove', e => { mx = e.clientX; my = e.clientY; });
  document.addEventListener('mouseleave', () => { glow.style.opacity = '0'; dot.style.opacity = '0'; });
  document.addEventListener('mouseenter', () => { glow.style.opacity = '1'; dot.style.opacity = '1'; });

  // Raf loop: dot snaps, glow follows with lag
  const loop = () => {
    dot.style.left = mx + 'px';
    dot.style.top  = my + 'px';

    gx += (mx - gx) * 0.07;
    gy += (my - gy) * 0.07;
    glow.style.left = gx + 'px';
    glow.style.top  = gy + 'px';

    requestAnimationFrame(loop);
  };
  loop();

  // Expand cursor on interactive elements
  const interactive = document.querySelectorAll(
    'a, button, .social-link, .tbadge, [data-magnetic]'
  );
  interactive.forEach(el => {
    el.addEventListener('mouseenter', () => dot.classList.add('expanded'));
    el.addEventListener('mouseleave', () => dot.classList.remove('expanded'));
  });
}


/* ══════════════════════════════════════════════════════════════════
   6. GSAP ENTRANCE ANIMATIONS
   ══════════════════════════════════════════════════════════════════ */
function initGSAP() {
  if (typeof gsap === 'undefined') {
    // Fallback: just show elements
    document.querySelectorAll('.hero-left, .hero-right').forEach(el => {
      el.style.opacity = '1';
    });
    return;
  }

  if (typeof ScrollTrigger !== 'undefined') {
    gsap.registerPlugin(ScrollTrigger);
  }

  const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });

  // ── Left panel ──────────────────────────────────
  tl
    .to('#heroLeft', { opacity: 1, duration: 0.01 })
    .from('.status-badge',    { y: 28, opacity: 0, duration: 0.55 })
    .from('.greeting-line',   { y: 32, opacity: 0, duration: 0.65 }, '-=0.25')
    .from('.hl-line-1',       { y: 50, opacity: 0, duration: 0.7  }, '-=0.35')
    .from('.hl-sep',          { scaleY: 0, opacity: 0, duration: 0.4, transformOrigin: 'center' }, '-=0.5')
    .from('.hl-line-2',       { y: 55, opacity: 0, duration: 0.8  }, '-=0.45')
    .from('.typing-container',{ y: 22, opacity: 0, duration: 0.55 }, '-=0.3')
    .from('.description',     { y: 22, opacity: 0, duration: 0.55 }, '-=0.3')
    .from('.stats-row',       { y: 20, opacity: 0, duration: 0.5  }, '-=0.25')
    .from('.cta-group .btn',  { y: 20, opacity: 0, duration: 0.45, stagger: 0.1 }, '-=0.2')
    .from('.social-link',     { y: 14, opacity: 0, duration: 0.38, stagger: 0.07 }, '-=0.15')

  // ── Right panel ──────────────────────────────────
    .to('#heroRight', { opacity: 1, duration: 0.01 }, 0.35)
    .from('#workspaceCard', {
      y: 70, opacity: 0,
      rotationX: 12,
      transformOrigin: 'center bottom',
      duration: 1.2,
      ease: 'power4.out',
    }, 0.55)
    .from('.fpanel', {
      scale: 0.65, opacity: 0, duration: 0.6,
      stagger: 0.18, ease: 'back.out(1.8)',
    }, 1.3)
    .from('.orbit-track', {
      scale: 0.3, opacity: 0, duration: 0.9,
      ease: 'back.out(1.5)',
    }, 0.9);

  // ── Continuous headline neon breath ──────────────
  gsap.to('.hl-line-2', {
    filter: 'brightness(1.22) drop-shadow(0 0 14px rgba(0,207,255,.5))',
    duration: 2.5,
    ease: 'sine.inOut',
    yoyo: true,
    repeat: -1,
  });
}


/* ══════════════════════════════════════════════════════════════════
   7. MAGNETIC BUTTONS
   ══════════════════════════════════════════════════════════════════ */
function initMagnetic() {
  document.querySelectorAll('[data-magnetic]').forEach(btn => {
    btn.addEventListener('mousemove', e => {
      const r  = btn.getBoundingClientRect();
      const cx = r.left + r.width  / 2;
      const cy = r.top  + r.height / 2;
      const dx = (e.clientX - cx) * 0.28;
      const dy = (e.clientY - cy) * 0.28;
      btn.style.transform = `translate(${dx}px, ${dy}px)`;
    });

    btn.addEventListener('mouseleave', () => {
      if (typeof gsap !== 'undefined') {
        gsap.to(btn, { x: 0, y: 0, duration: 0.55, ease: 'elastic.out(1, 0.55)' });
      } else {
        btn.style.transform = '';
      }
    });
  });
}


/* ══════════════════════════════════════════════════════════════════
   8. 3-D TILT EFFECT (workspace card)
   ══════════════════════════════════════════════════════════════════ */
function initTilt() {
  const card = document.getElementById('workspaceCard');
  if (!card) return;

  // Operate on the parent (hero-right) so the mouse area is larger
  const zone = card.closest('.hero-right') || card.parentElement;

  zone.addEventListener('mousemove', e => {
    const r   = card.getBoundingClientRect();
    const cx  = r.left + r.width  / 2;
    const cy  = r.top  + r.height / 2;
    const nx  = (e.clientX - cx) / (r.width  / 2);  // -1 to 1
    const ny  = (e.clientY - cy) / (r.height / 2);  // -1 to 1

    const tiltX =  -ny * 9;
    const tiltY =   nx * 9;

    card.style.transform =
      `perspective(1200px) rotateX(${tiltX}deg) rotateY(${tiltY}deg) scale3d(1.025,1.025,1.025)`;
  });

  zone.addEventListener('mouseleave', () => {
    if (typeof gsap !== 'undefined') {
      gsap.to(card, {
        rotateX: 0, rotateY: 0, scale: 1,
        duration: 0.9, ease: 'elastic.out(1, 0.5)',
        clearProps: 'transform',
      });
    } else {
      card.style.transform = '';
    }
  });
}


/* ══════════════════════════════════════════════════════════════════
   9. TERMINAL LIVE TYPING
   ══════════════════════════════════════════════════════════════════ */
function initTerminal() {
  const el = document.getElementById('termTyping');
  if (!el) return;

  const CMDS = [
    'npm run dev',
    'git commit -m "feat: AI dashboard"',
    'python train.py --lr 0.001',
    'docker-compose up --build',
    'flutter build apk --release',
    'node server.js --port 8080',
    'kubectl apply -f deploy.yaml',
  ];

  let ci = 0, chi = 0, del = false;

  const typeCmd = () => {
    const cmd = CMDS[ci];

    if (!del) {
      el.textContent = cmd.slice(0, ++chi);
      if (chi >= cmd.length) { del = true; setTimeout(typeCmd, 2000); return; }
    } else {
      el.textContent = cmd.slice(0, --chi);
      if (chi <= 0) {
        del = false;
        ci  = (ci + 1) % CMDS.length;
        setTimeout(typeCmd, 380);
        return;
      }
    }

    setTimeout(typeCmd, del ? 28 : 65 + Math.random() * 35);
  };

  setTimeout(typeCmd, 2400);
}


/* ══════════════════════════════════════════════════════════════════
   10. CODE LINES STAGGER REVEAL
   ══════════════════════════════════════════════════════════════════ */
function initCodeReveal() {
  const lines = document.querySelectorAll('#editorBody .cl');
  lines.forEach((line, i) => {
    setTimeout(() => {
      line.classList.add('visible');
    }, 1600 + i * 100);
  });
}


/* ══════════════════════════════════════════════════════════════════
   11. ORBITING TECH BADGES
   ══════════════════════════════════════════════════════════════════ */
function initOrbit() {
  const container = document.getElementById('orbitBadges');
  const card      = document.getElementById('workspaceCard');
  if (!container || !card) return;

  const badges = [...container.querySelectorAll('.tbadge')];
  const N      = badges.length;

  // Orbit config
  let centerX, centerY, radius;
  let angle   = 0;
  const SPEED = 0.0055;

  const update = () => {
    // Recompute center relative to the container's parent (.hero-right)
    const parent = container.parentElement.getBoundingClientRect();
    const cardR  = card.getBoundingClientRect();

    // Center on the card's center relative to hero-right
    centerX = (cardR.left + cardR.width  / 2) - parent.left;
    centerY = (cardR.top  + cardR.height / 2) - parent.top;
    radius  = cardR.width * 0.58;
  };

  // Initial layout
  update();
  window.addEventListener('resize', update);

  // Position each badge at its orbit angle, counter-rotating badge to keep upright
  const animate = () => {
    angle += SPEED;
    update();

    badges.forEach((badge, i) => {
      const theta = angle + (i / N) * Math.PI * 2;
      const x     = centerX + Math.cos(theta) * radius;
      const y     = centerY + Math.sin(theta) * radius;

      // Translate to position; translate back -50% to centre badge
      badge.style.left      = `${x}px`;
      badge.style.top       = `${y}px`;
      badge.style.transform = `translate(-50%, -50%)`;

      // Subtle scale pulse with depth illusion (front = larger)
      const depth = Math.sin(theta) * 0.12 + 1;
      badge.style.transform += ` scale(${depth.toFixed(3)})`;

      // Opacity based on depth
      badge.style.opacity = (0.65 + Math.sin(theta) * 0.35).toFixed(2);
    });

    requestAnimationFrame(animate);
  };

  animate();

  // Pause orbit on hover
  badges.forEach(b => {
    b.addEventListener('mouseenter', () => {
      b.style.opacity = '1';
      b.style.zIndex  = '30';
    });
    b.addEventListener('mouseleave', () => {
      b.style.zIndex = '';
    });
  });
}


/* ══════════════════════════════════════════════════════════════════
   12. FLOATING PANEL GLOW PULSE
   ══════════════════════════════════════════════════════════════════ */
function initPanelGlow() {
  const panels = document.querySelectorAll('.fpanel');
  let t = 0;

  const pulse = () => {
    t += 0.018;
    panels.forEach((p, i) => {
      const v = Math.sin(t + i * 1.3) * 0.5 + 0.5;
      p.style.borderColor =
        `rgba(0,207,255,${(0.18 + v * 0.32).toFixed(2)})`;
      p.style.boxShadow =
        `0 8px 32px rgba(0,0,0,.45), ` +
        `0 0 ${(12 + v * 22).toFixed(0)}px rgba(0,90,255,${(0.06 + v * 0.12).toFixed(2)})`;
    });
    requestAnimationFrame(pulse);
  };

  pulse();
}


/* ══════════════════════════════════════════════════════════════════
   MOUSE-PARALLAX on hero background blobs
   ══════════════════════════════════════════════════════════════════ */
(function initParallax() {
  const blobs = document.querySelectorAll('.blob');
  if (!blobs.length) return;

  let tx = 0, ty = 0;
  let cx = 0, cy = 0;

  document.addEventListener('mousemove', e => {
    tx = ((e.clientX / window.innerWidth)  - 0.5) * 30;
    ty = ((e.clientY / window.innerHeight) - 0.5) * 20;
  });

  const update = () => {
    cx += (tx - cx) * 0.06;
    cy += (ty - cy) * 0.06;

    blobs.forEach((b, i) => {
      const factor = 0.5 + i * 0.25;
      b.style.transform =
        `translate(${(cx * factor).toFixed(2)}px, ${(cy * factor).toFixed(2)}px)`;
    });

    requestAnimationFrame(update);
  };
  update();
})();


/* ══════════════════════════════════════════════════════════════════
   SOUND-WAVE VISUALISER (decorative SVG bars, bottom-left)
   ══════════════════════════════════════════════════════════════════ */
(function initWaveViz() {
  // Inject a subtle animated SVG wave visualiser into .hero
  const hero = document.querySelector('.hero');
  if (!hero) return;

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'wave-viz');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('viewBox', '0 0 120 40');

  const BARS = 18;
  for (let i = 0; i < BARS; i++) {
    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    const x    = i * (120 / BARS) + 1;
    rect.setAttribute('x',      x);
    rect.setAttribute('y',      20);
    rect.setAttribute('width',  4);
    rect.setAttribute('height', 0);
    rect.setAttribute('rx',     2);
    rect.setAttribute('fill',   'rgba(0,207,255,0.35)');
    svg.appendChild(rect);
  }
  hero.appendChild(svg);

  // Inline style
  Object.assign(svg.style, {
    position: 'absolute',
    bottom: '3.5rem',
    left:   '2rem',
    width:  '80px',
    height: '30px',
    zIndex: '10',
    opacity: '0.6',
  });

  // Animate bars
  const bars = [...svg.querySelectorAll('rect')];
  let t = 0;
  const waveAnim = () => {
    t += 0.08;
    bars.forEach((bar, i) => {
      const h = (Math.sin(t + i * 0.6) * 0.5 + 0.5) * 18 + 3;
      bar.setAttribute('height', h.toFixed(1));
      bar.setAttribute('y',      (40 - h).toFixed(1));
    });
    requestAnimationFrame(waveAnim);
  };
  waveAnim();
})();