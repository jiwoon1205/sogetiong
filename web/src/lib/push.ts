/**
 * 휴대폰 알림(웹 푸시) 도우미 (2026-10-05).
 *
 * - 안드로이드: 크롬·삼성 인터넷에서 바로 켤 수 있다.
 * - 아이폰: iOS 16.4 이상 + 사파리에서 "홈 화면에 추가"한 아이콘으로 열었을 때만 켤 수 있다.
 * - 카카오톡·에브리타임 같은 앱 안에서 열린 화면(인앱 브라우저)에서는 켤 수 없다.
 */

import { api } from "@/lib/api";
import type { Alerts } from "@/lib/types";

/** 이 기기에서 알림을 켤 수 있는 상태인지 */
export type PushEnv = "ready" | "in-app" | "ios-install" | "unsupported";

export function isIos(): boolean {
  if (typeof navigator === "undefined") return false;
  // 아이패드는 데스크톱 사파리처럼 "Macintosh"라고 나오므로 터치 지원으로 구분
  return /iPhone|iPad|iPod/i.test(navigator.userAgent) || (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);
}

export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  const nav = navigator as Navigator & { standalone?: boolean };
  return window.matchMedia?.("(display-mode: standalone)").matches || nav.standalone === true;
}

export function isInAppBrowser(): boolean {
  if (typeof navigator === "undefined") return false;
  return /KAKAOTALK|everytime|Instagram|FBAN|FBAV|Line\/|NAVER\(inapp|DaumApps|Whale\/.*inapp/i.test(navigator.userAgent);
}

function hasPushApi(): boolean {
  return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function detectEnv(): PushEnv {
  if (isInAppBrowser()) return "in-app";
  if (hasPushApi()) return "ready";
  // 아이폰 사파리는 홈 화면에 추가해서 열어야 알림 기능이 생긴다
  if (isIos() && !isStandalone()) return "ios-install";
  return "unsupported";
}

export function permission(): NotificationPermission | null {
  return typeof window !== "undefined" && "Notification" in window ? Notification.permission : null;
}

export async function currentSubscription(): Promise<PushSubscription | null> {
  if (!hasPushApi()) return null;
  const reg = await navigator.serviceWorker.getRegistration("/");
  return reg ? reg.pushManager.getSubscription() : null;
}

function keyBytes(base64url: string): Uint8Array {
  const pad = "=".repeat((4 - (base64url.length % 4)) % 4);
  const raw = atob((base64url + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

function sameKey(sub: PushSubscription, publicKey: string): boolean {
  const current = sub.options?.applicationServerKey;
  if (!current) return true; // 알 수 없으면 그대로 쓴다
  const a = new Uint8Array(current);
  const b = keyBytes(publicKey);
  return a.length === b.length && a.every((v, i) => v === b[i]);
}

export class PushDenied extends Error {}

/**
 * 알림 켜기. 반드시 버튼을 누른 바로 그 순간에 불러야 한다
 * (아이폰은 "사용자가 누른 직후"가 아니면 허용 창을 띄우지 않는다 → 맨 처음에 requestPermission).
 */
export async function enablePush(publicKey: string): Promise<Alerts> {
  const result = await Notification.requestPermission();
  if (result !== "granted") throw new PushDenied("알림이 허용되지 않았어요.");
  const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
  await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (sub && !sameKey(sub, publicKey)) {
    await sub.unsubscribe(); // 서버 열쇠가 바뀐 경우
    sub = null;
  }
  if (!sub) {
    sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(publicKey) as BufferSource });
  }
  return api<Alerts>("/me/alerts/push", { method: "PUT", body: sub.toJSON() });
}

/** 이 기기에서 알림 끄기 (서버에서도 지움) */
export async function disablePush(): Promise<void> {
  const sub = await currentSubscription();
  if (!sub) return;
  await api("/me/alerts/push", { method: "DELETE", body: { endpoint: sub.endpoint } }).catch(() => {});
  await sub.unsubscribe().catch(() => false);
}

/**
 * 화면이 열릴 때: 이 기기에 알림이 켜져 있으면 지금 로그인한 세션에 다시 묶는다.
 * (로그인이 만료돼 다시 로그인했거나, 브라우저가 알림 주소를 새로 바꾼 경우에도 계속 알림이 오게)
 */
export async function syncPush(alerts: Alerts): Promise<boolean> {
  if (!alerts.push_available || !alerts.public_key || permission() !== "granted") return false;
  const sub = await currentSubscription();
  if (!sub || !sameKey(sub, alerts.public_key)) return false;
  await api("/me/alerts/push", { method: "PUT", body: sub.toJSON() });
  return true;
}
