// vite-plugin-pwa generates and registers the actual service worker at build
// time (virtual:pwa-register). This wrapper exists so the rest of the app
// doesn't import the virtual module directly, which keeps `vite build`
// optional for anyone reading the source without the plugin installed.
export async function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  try {
    const { registerSW } = await import("virtual:pwa-register");
    registerSW({ immediate: true });
  } catch (err) {
    console.warn("Service worker registration skipped:", err);
  }
}
