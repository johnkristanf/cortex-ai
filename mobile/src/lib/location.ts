import * as Location from 'expo-location';

export interface Coords {
  latitude: number;
  longitude: number;
}

const TTL_MS = 3 * 60 * 1000;
const GPS_TIMEOUT_MS = 2000;

let cached: Coords | null = null;
let lastFetch = 0;
let refreshPromise: Promise<Coords | null> | null = null;

async function fetchCoords(): Promise<Coords | null> {
  try {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== 'granted') return cached;

    const loc = await Promise.race([
      Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error('GPS timeout')), GPS_TIMEOUT_MS)
      ),
    ]);

    cached = {
      latitude: loc.coords.latitude,
      longitude: loc.coords.longitude,
    };
    lastFetch = Date.now();
    return cached;
  } catch {
    return cached;
  }
}

/** Returns the best-known coords immediately without waiting on GPS. */
export function getCachedCoords(): Coords | null {
  return cached;
}

/** Kick off a background GPS refresh. Safe to call without await. */
export function refreshLocation(): void {
  const isFresh = cached && Date.now() - lastFetch < TTL_MS;
  if (isFresh || refreshPromise) return;

  refreshPromise = fetchCoords().finally(() => {
    refreshPromise = null;
  });
}
