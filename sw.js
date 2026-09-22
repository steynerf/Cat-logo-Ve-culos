// Service worker: prioriza SEMPRE a rede (pra voce nunca mais ficar preso
// numa versao antiga do catalogo). O cache so entra em acao como reserva,
// quando o celular estiver offline. Fotos de sites externos nunca sao
// cacheadas (para nao lotar o armazenamento do aparelho).
const CACHE = "catalogo-carros-v2";
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
  // seguem direto pra rede, sem cache
  if (new URL(event.request.url).origin !== self.location.origin) return;

  event.respondWith(
    fetch(event.request)
      .then((resposta) => {
        // deu certo buscar na rede: atualiza o cache com a versao mais
        // recente e devolve essa versao mais recente
        const copia = resposta.clone();
        caches.open(CACHE).then((cache) => cache.put(event.request, copia));
        return resposta;
      })
      .catch(() => caches.match(event.request)) // offline: usa o cache
  );
});
