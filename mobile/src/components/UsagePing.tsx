import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { useEffect } from 'react';
import { AppState, Platform } from 'react-native';

import { postJSON } from '@/lib/api';
import { useApp } from '@/lib/app-state';

const EVERY = 6 * 3600e3;          // at most once every 6 hours (the server keeps one row per install per day)

// Tells the server "this app was opened today", so the admin can count the app's daily and monthly users.
// Sends only the device's random id (the one used for votes; the server stores a keyed hash of it), the platform and the app version.
export function UsagePing() {
  const { ready, vid } = useApp();

  useEffect(() => {
    if (!ready || !vid || (Platform.OS !== 'android' && Platform.OS !== 'ios')) return;
    const ping = async () => {
      try {
        const last = Number(await AsyncStorage.getItem('pingAt')) || 0;
        const today = new Date().toDateString();
        if (Date.now() - last < EVERY && new Date(last).toDateString() === today) return;
        await postJSON('/api/app/open', { vid, platform: Platform.OS, version: Constants.expoConfig?.version ?? '' });
        await AsyncStorage.setItem('pingAt', String(Date.now()));
      } catch {}                    // offline or server busy: try again next time the app comes to the front
    };
    ping();
    const sub = AppState.addEventListener('change', s => { if (s === 'active') ping(); });
    return () => sub.remove();
  }, [ready, vid]);

  return null;
}
