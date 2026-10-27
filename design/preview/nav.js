document.addEventListener('DOMContentLoaded', () => {
  const rail = document.querySelector('.rail');
  const primaryNav = rail?.querySelector(':scope > nav');
  if (!rail || !primaryNav) return;

  const menu = document.createElement('details');
  menu.className = 'mobile-menu';

  const toggle = document.createElement('summary');
  toggle.textContent = 'Menu completo';

  const links = primaryNav.cloneNode(true);
  links.setAttribute('aria-label', 'Todas as áreas da guilda');
  menu.append(toggle, links);
  rail.insertBefore(menu, primaryNav);
  document.documentElement.classList.add('has-mobile-menu');
});
