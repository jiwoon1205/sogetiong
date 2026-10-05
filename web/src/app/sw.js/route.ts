/**
 * 서비스 워커 (2026-10-05, 휴대폰 알림).
 * 브라우저가 사이트를 닫아 둔 동안에도 알림을 받아 잠금화면에 띄워 주는 작은 프로그램이다.
 * 주소가 꼭 사이트 맨 위(/sw.js)여야 사이트 전체의 알림을 받을 수 있어서, public 폴더 대신 이 경로로 내보낸다.
 *
 * 하는 일은 두 가지뿐:
 *  1) push: 서버가 보낸 알림을 그대로 띄운다 (글: "훕팅 · 새 메시지가 왔어요"처럼 이름·내용 없음)
 *  2) notificationclick: 알림을 누르면 그 대화방을 연다 (이미 열린 창이 있으면 그 창을 씀)
 * 오프라인 저장(캐시)은 하지 않는다.
 */

export const dynamic = "force-static";

const SW = `
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = {};
  }
  const title = data.title || "훕팅";
  event.waitUntil(
    self.registration.showNotification(title, {
      body: data.body || "새 소식이 있어요",
      icon: "/icon.png",
      tag: data.tag || undefined,
      renotify: Boolean(data.tag),
      data: { url: data.url || "/matches" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const path = (event.notification.data && event.notification.data.url) || "/matches";
  const url = new URL(path, self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if (client.url.startsWith(self.location.origin) && "focus" in client) {
          return client.focus().then((c) => (c && "navigate" in c ? c.navigate(url) : c));
        }
      }
      return self.clients.openWindow(url);
    }),
  );
});
`;

export function GET() {
  return new Response(SW, {
    headers: {
      "Content-Type": "application/javascript; charset=utf-8",
      // 고친 내용이 바로 반영되게 (브라우저가 오래 들고 있지 않게)
      "Cache-Control": "no-cache, no-store, must-revalidate",
      "Service-Worker-Allowed": "/",
    },
  });
}
