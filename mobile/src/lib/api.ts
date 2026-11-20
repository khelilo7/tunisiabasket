import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';

// The website's server: its public API is the app's only data source (no admin here, the admin stays on the website).
// Local development: EXPO_PUBLIC_API_URL=http://localhost:5055 (.env.local); an Android emulator reaches the computer at 10.0.2.2.
const RAW = process.env.EXPO_PUBLIC_API_URL || 'https://tunisiabasket.com';
export const API = Platform.OS === 'android' ? RAW.replace('://localhost', '://10.0.2.2') : RAW;
export const FANTASY_ON = process.env.EXPO_PUBLIC_FANTASY === '1';

export const asset = (path?: string | null) => (!path ? undefined : path.startsWith('http') ? path : API + path);
export const teamLogo = (code?: string | null) => (code ? `${API}/img/teams/${code}.png` : undefined);

const memory = new Map<string, { at: number; data: unknown }>();
const KEY = (p: string) => 'api:' + p;
// Every screen showing the same address gets a fresh answer at once: a vote on one screen updates the fan zone of the home screen still open behind it.
const listeners = new Map<string, Set<(d: unknown) => void>>();

export async function getJSON<T>(path: string): Promise<T> {
  const r = await fetch(API + path, { headers: { Accept: 'application/json' } });
  if (!r.ok) throw new Error(String(r.status));
  const data = (await r.json()) as T;
  memory.set(path, { at: Date.now(), data });
  listeners.get(path)?.forEach(f => f(data));
  AsyncStorage.setItem(KEY(path), JSON.stringify(data)).catch(() => {});
  return data;
}

export async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(API + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(String(r.status)), { data });
  return data as T;
}

// Stale-while-revalidate: the last answer shows at once (memory, then the phone's storage, so the app opens offline), then the fresh one replaces it.
export function useApi<T>(path: string | null, { every }: { every?: number } = {}) {
  const [state, setState] = useState<{ path: string | null; data?: T; error: Error | null }>({ path, data: path ? (memory.get(path)?.data as T) : undefined, error: null });
  const [refreshing, setRefreshing] = useState(false);
  const alive = useRef(true);
  const data = state.path === path ? state.data : path ? (memory.get(path)?.data as T | undefined) : undefined;
  const error = state.path === path ? state.error : null;

  const load = useCallback(async (manual = false) => {
    if (!path) return;
    if (manual) setRefreshing(true);
    try {
      const d = await getJSON<T>(path);
      if (alive.current) setState({ path, data: d, error: null });
    } catch (e) {
      if (alive.current) setState(s => ({ path, data: s.path === path ? s.data : undefined, error: e as Error }));
    } finally {
      if (alive.current && manual) setRefreshing(false);
    }
  }, [path]);

  useEffect(() => {
    alive.current = true;
    if (!path) return;
    if (!memory.get(path)) {
      AsyncStorage.getItem(KEY(path)).then(s => {
        if (s && alive.current && !memory.get(path)) setState(st => (st.path === path && st.data ? st : { path, data: JSON.parse(s), error: null }));
      }).catch(() => {});
    }
    const onFresh = (d: unknown) => { if (alive.current) setState({ path, data: d as T, error: null }); };
    if (!listeners.has(path)) listeners.set(path, new Set());
    listeners.get(path)!.add(onFresh);
    load();
    const id = every ? setInterval(() => load(), every) : undefined;
    return () => { alive.current = false; listeners.get(path)?.delete(onFresh); if (id) clearInterval(id); };
  }, [path, load, every]);

  return { data, error, loading: !data && !error, refreshing, refresh: () => load(true) };
}

// Player photos by id (the lists of a game or of the leaders do not carry them): one cached call.
export function usePhotos() {
  const { data } = useApi<{ players: { id: string; photo?: string | null }[] }>('/api/players');
  const map: Record<string, string | undefined> = {};
  for (const p of data?.players || []) if (p.photo) map[p.id] = p.photo;
  return map;
}
