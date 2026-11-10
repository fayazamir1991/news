const installButton = document.getElementById('install-app');
const help = document.getElementById('install-help');
let installPrompt;
const standalone = () => window.matchMedia('(display-mode: standalone)').matches || navigator.standalone;
const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
if (ios && !standalone()) installButton.hidden = false;

window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault();
  installPrompt = event;
  installButton.hidden = standalone();
});
installButton.addEventListener('click', async () => {
  if (!installPrompt) { help.hidden = !help.hidden; return; }
  await installPrompt.prompt();
  await installPrompt.userChoice;
  installPrompt = undefined;
  installButton.hidden = true;
});
window.addEventListener('appinstalled', () => { installButton.hidden = true; help.hidden = true; });
const showConnection = () => { document.getElementById('offline-status').hidden = navigator.onLine; };
window.addEventListener('online', showConnection);
window.addEventListener('offline', showConnection);
showConnection();
if ('serviceWorker' in navigator) {
  let refreshing = false;
  const alreadyControlled = !!navigator.serviceWorker.controller;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (alreadyControlled && !refreshing) { refreshing = true; location.reload(); }
  });
  navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' }).catch(error => console.warn('Offline support unavailable', error));
}
