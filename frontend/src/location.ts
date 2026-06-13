import { Capacitor } from "@capacitor/core";
import { Geolocation } from "@capacitor/geolocation";

// Gangnam demo point — used on web and as a fallback when GPS is unavailable.
export const DEMO_LAT = 37.5172;
export const DEMO_LNG = 127.0473;

export function isNative(): boolean {
  return Capacitor.isNativePlatform();
}

/** Real device GPS on native. Throws if permission is denied or it times out,
 *  so callers can fall back to the demo point. */
export async function getDeviceLocation(): Promise<{ lat: number; lng: number }> {
  const perm = await Geolocation.checkPermissions();
  if (perm.location !== "granted" && perm.coarseLocation !== "granted") {
    const req = await Geolocation.requestPermissions();
    if (req.location !== "granted" && req.coarseLocation !== "granted") {
      throw new Error("위치 권한이 거부되었습니다");
    }
  }
  const pos = await Geolocation.getCurrentPosition({ enableHighAccuracy: true, timeout: 10000 });
  return { lat: pos.coords.latitude, lng: pos.coords.longitude };
}
