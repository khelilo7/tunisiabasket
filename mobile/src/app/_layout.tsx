import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { PushSync } from '@/components/PushSync';
import { AppStateProvider } from '@/lib/app-state';
import { C } from '@/theme';

SplashScreen.preventAutoHideAsync().catch(() => {});

export default function RootLayout() {
  const [loaded] = useFonts({
    'BarlowCondensed-ExtraBold': require('../../assets/fonts/BarlowCondensed-ExtraBold.ttf'),
    'BarlowCondensed-SemiBold': require('../../assets/fonts/BarlowCondensed-SemiBold.ttf'),
  });
  useEffect(() => { if (loaded) SplashScreen.hideAsync().catch(() => {}); }, [loaded]);
  if (!loaded) return null;
  return (
    <SafeAreaProvider>
      <AppStateProvider>
        <StatusBar style="light" />
        <PushSync />
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: C.bg }, animation: 'slide_from_right' }} />
      </AppStateProvider>
    </SafeAreaProvider>
  );
}
