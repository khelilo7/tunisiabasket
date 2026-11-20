import { Tabs } from 'expo-router';

import { ClubPicker } from '@/components/ClubPicker';
import { TabBar } from '@/components/TabBar';
import { FANTASY_ON } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { C } from '@/theme';

export default function TabsLayout() {
  const { ready, favPrompt } = useApp();
  return (
    <>
    <Tabs tabBar={() => <TabBar />} screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: C.bg } }}>
      <Tabs.Screen name="index" />
      <Tabs.Screen name="live" />
      <Tabs.Screen name="scores" />
      <Tabs.Screen name="standings" />
      <Tabs.Screen name="players" />
      {/* Fantasy: hidden in store builds until it launches (EXPO_PUBLIC_FANTASY=1 shows it, for local testing) */}
      <Tabs.Screen name="fantasy" options={{ href: FANTASY_ON ? undefined : null }} />
      <Tabs.Screen name="more" />
    </Tabs>
    {ready && favPrompt ? <ClubPicker /> : null}
    </>
  );
}
