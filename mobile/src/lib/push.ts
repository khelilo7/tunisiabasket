import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants, { ExecutionEnvironment } from 'expo-constants';
import { Platform } from 'react-native';

import { postJSON } from './api';

// Push notifications: the phone tells the server what it wants (notify.py) — level "team" (only my club's results and news), "all", or "none" — and three
// switches (results, news, votes). The token is an anonymous address of this install; nothing else is sent.
// Remote push needs a real build (a development, preview or store build): Expo Go on Android has none since SDK 53, and the web has none here.
export type Level = 'team' | 'all' | 'none';
export type NotifPrefs = { level: Level; results: boolean; news: boolean; votes: boolean };
export type PushStatus = 'ok' | 'off' | 'denied' | 'noclub' | 'unsupported' | 'error';

export const DEFAULT_PREFS: NotifPrefs = { level: 'none', results: true, news: true, votes: true };
const EXPO_GO = Constants.executionEnvironment === ExecutionEnvironment.StoreClient || Constants.appOwnership === 'expo';
export const PUSH_SUPPORTED = Platform.OS !== 'web' && !EXPO_GO;

type N = typeof import('expo-notifications');
let mod: N | null | undefined;
export function notifications(): N | null {
  if (!PUSH_SUPPORTED) return null;
  if (mod === undefined) {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    try { mod = require('expo-notifications') as N; } catch { mod = null; }      // a build made before notifications were added has no native module
  }
  return mod;
}

async function token(ask: boolean): Promise<string | 'denied' | null> {
  const Notif = notifications();
  if (!Notif) return null;
  if (Platform.OS === 'android') {
    await Notif.setNotificationChannelAsync('default', { name: 'Tunisia Basket', importance: Notif.AndroidImportance.DEFAULT });   // Android 13+ asks only once a channel exists
  }
  let { status } = await Notif.getPermissionsAsync();
  if (status !== 'granted' && ask) status = (await Notif.requestPermissionsAsync()).status;
  if (status !== 'granted') return 'denied';
  const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
  return (await Notif.getExpoPushTokenAsync({ projectId })).data;
}

// Tell the server. `ask` shows the system permission prompt when needed (only when the user chose something, never at launch).
export async function syncPush(p: NotifPrefs, fav: string | null, lang: string, ask = false): Promise<PushStatus> {
  if (!PUSH_SUPPORTED) return 'unsupported';
  try {
    if (p.level === 'none') {
      const old = await AsyncStorage.getItem('pushToken');
      if (old) { await postJSON('/api/push', { token: old, level: 'none' }); await AsyncStorage.removeItem('pushToken'); }
      return 'off';
    }
    if (p.level === 'team' && !fav) return 'noclub';
    const tok = await token(ask);
    if (tok === 'denied') return 'denied';
    if (!tok) return 'unsupported';
    await postJSON('/api/push', { token: tok, level: p.level, team: fav || '', lang, results: p.results, news: p.news, votes: p.votes });
    await AsyncStorage.setItem('pushToken', tok);
    return 'ok';
  } catch {
    return 'error';
  }
}
