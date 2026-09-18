// Service worker simples: cacheia o app na instalacao para funcionar offline
// (as fotos dos veiculos, por virem de sites externos, continuam precisando
// de internet - so a estrutura do app funciona sem conexao).
const CACHE = "catalogo-carros-v1";
const ARQUIVOS = ["./", "./index.html", "./manifest.json", "./icon-192.png", "./icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ARQUIVOS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((chaves) =>
      Promise.all(chaves.filter((c) => c !== CACHE).map((c) => caches.delete(c)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  // so intercepta pedidos do proprio app (mesma origem); fotos externas
  // seguem direto pra rede, sem cache, para nao lotar o armazenamento
  if (new URL(event.request.url).origin !== self.location.origin) return;
  event.respondWith(
    caches.match(event.request).then((resp) => resp || fetch(event.request))
  );
});
