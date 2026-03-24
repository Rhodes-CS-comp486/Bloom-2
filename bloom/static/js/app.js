// Bloom — Global Frontend JS

// Flash auto-dismiss
document.querySelectorAll('.flash').forEach(flash => {
  setTimeout(() => {
    flash.style.opacity = '0';
    flash.style.transform = 'translateY(-8px)';
    flash.style.transition = 'opacity 0.4s, transform 0.4s';
    setTimeout(() => flash.remove(), 400);
  }, 4000);
});

// Garden animation: stagger plant appearances
document.querySelectorAll('.garden-plant').forEach((plant, i) => {
  plant.style.opacity = '0';
  plant.style.transform = 'translate(-50%, 20px)';
  plant.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
  setTimeout(() => {
    plant.style.opacity = '1';
    plant.style.transform = 'translate(-50%, 0)';
  }, 150 * i);
});

// Score ring animation on dashboard
const ring = document.querySelector('.score-circle');
if (ring) {
  const target = ring.getAttribute('stroke-dasharray');
  ring.setAttribute('stroke-dasharray', '0 213');
  setTimeout(() => {
    ring.style.transition = 'stroke-dasharray 1.2s cubic-bezier(0.4, 0, 0.2, 1)';
    ring.setAttribute('stroke-dasharray', target);
  }, 300);
}

// Progress bar animation
document.querySelectorAll('.gpb-fill, .hp-fill').forEach(bar => {
  const target = bar.style.width;
  bar.style.width = '0%';
  setTimeout(() => {
    bar.style.transition = 'width 1s ease';
    bar.style.width = target;
  }, 200);
});

// Confirm habit toggle with visual feedback
window.habitToggleCooldown = {};

// ── Notifications ─────────────────────────────────────────────────────────────
(function () {
  const bell     = document.getElementById('notifBell');
  const dropdown = document.getElementById('notifDropdown');
  const badge    = document.getElementById('notifBadge');
  const list     = document.getElementById('notifList');
  const closeBtn = document.getElementById('notifClose');

  if (!bell) return; // not logged in

  const TYPE_ICONS = { checkin: '🌿', period: '🌹', habit: '✨' };

  async function loadNotifications() {
    try {
      const res  = await fetch('/api/notifications');
      const data = await res.json();
      const notifs = data.notifications;

      if (notifs.length === 0) {
        list.innerHTML = '<div class="notif-empty">You\'re all caught up 🌸</div>';
        badge.style.display = 'none';
      } else {
        badge.textContent    = notifs.length;
        badge.style.display  = 'flex';
        list.innerHTML = notifs.map(n => `
          <div class="notif-card type-${n.type}">
            <div class="notif-card-title">${TYPE_ICONS[n.type] || ''} ${n.title}</div>
            <div class="notif-card-msg">${n.message}</div>
            <a class="notif-card-link" href="${n.link}">${n.link_label} →</a>
          </div>
        `).join('');
      }
    } catch (e) {
      console.warn('Could not load notifications', e);
    }
  }

  bell.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('open');
  });

  closeBtn.addEventListener('click', () => dropdown.classList.remove('open'));

  document.addEventListener('click', (e) => {
    if (!dropdown.contains(e.target) && e.target !== bell) {
      dropdown.classList.remove('open');
    }
  });

  // Load on page open, refresh every 5 minutes
  loadNotifications();
  setInterval(loadNotifications, 5 * 60 * 1000);
})();
