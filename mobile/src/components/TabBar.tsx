import { Ionicons } from '@expo/vector-icons';
import { BlurView } from 'expo-blur';
import { router, usePathname } from 'expo-router';
import { Platform, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { FANTASY_ON, useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { Key } from '@/lib/i18n';
import { C, R } from '@/theme';
import { tap, Txt } from './ui';

type Tab = { href: '/' | '/live' | '/scores' | '/standings' | '/players' | '/fantasy' | '/more'; label: Key; icon: [keyof typeof Ionicons.glyphMap, keyof typeof Ionicons.glyphMap] };

const TABS: Tab[] = [
  { href: '/', label: 'home', icon: ['home', 'home-outline'] },
  { href: '/live', label: 'live', icon: ['radio', 'radio-outline'] },
  { href: '/scores', label: 'scores', icon: ['basketball', 'basketball-outline'] },
  { href: '/standings', label: 'standings', icon: ['podium', 'podium-outline'] },
  { href: '/players', label: 'players', icon: ['people', 'people-outline'] },
  ...(FANTASY_ON ? [{ href: '/fantasy', label: 'fantasy', icon: ['trophy', 'trophy-outline'] } as Tab] : []),
  { href: '/more', label: 'more', icon: ['grid', 'grid-outline'] },
];

export const TAB_BAR_SPACE = 84;           // what a tab screen leaves free at its bottom, above the safe area

// A small floating glass pill, always on screen (fixed on the web, absolute in the app): the active tab is an orange capsule with its name, the others icons only.
// It reads the route and navigates with Expo Router itself (no navigator props), so it behaves the same on Android, iOS and the web.
export function TabBar() {
  const ins = useSafeAreaInsets();
  const path = usePathname();
  const { t } = useApp();
  const Glass = Platform.OS === 'web' ? View : BlurView;
  const live = (useApi<{ games: unknown[] }>('/api/live', { every: 30000 }).data?.games.length || 0) > 0;     // a red dot on Live while a game is on
  const active = (h: string) => (h === '/' ? path === '/' : path === h || path.startsWith(h + '/'));
  return (
    <View pointerEvents="box-none" style={[s.wrap, { bottom: Math.max(ins.bottom, 8) + 4 }]}>
      <Glass intensity={50} tint="dark" style={s.bar}>
        {TABS.map(tb => {
          const on = active(tb.href);
          return (
            <Pressable key={tb.href} accessibilityRole="tab" accessibilityState={{ selected: on }} accessibilityLabel={t(tb.label)} hitSlop={4}
              onPress={() => { if (!on) { tap(); router.navigate(tb.href); } }} style={[s.item, on && s.itemOn]}>
              <View>
                <Ionicons name={on ? tb.icon[0] : tb.icon[1]} size={19} color={on ? '#1A1205' : tb.href === '/live' && live ? C.bad : C.sub} />
                {tb.href === '/live' && live && !on ? <View style={s.dot} /> : null}
              </View>
              {on ? <Txt v="small" c="#1A1205" style={{ fontWeight: '800', fontSize: 12.5 }} numberOfLines={1}>{t(tb.label)}</Txt> : null}
            </Pressable>
          );
        })}
      </Glass>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { position: Platform.OS === 'web' ? ('fixed' as 'absolute') : 'absolute', left: 0, right: 0, alignItems: 'center', zIndex: 50 },
  bar: { flexDirection: 'row', gap: 2, padding: 4, borderRadius: R.pill, overflow: 'hidden', borderWidth: 1, borderColor: C.lineStrong,
    backgroundColor: Platform.OS === 'android' || Platform.OS === 'web' ? 'rgba(21,29,53,0.94)' : 'rgba(21,29,53,0.55)',
    shadowColor: '#000', shadowOpacity: 0.35, shadowRadius: 16, shadowOffset: { width: 0, height: 6 }, elevation: 12 },
  item: { flexDirection: 'row', alignItems: 'center', gap: 5, height: 42, minWidth: 44, paddingHorizontal: 11, borderRadius: R.pill, justifyContent: 'center' },
  itemOn: { backgroundColor: C.orange, paddingHorizontal: 14 },
  dot: { position: 'absolute', right: -3, top: -2, width: 8, height: 8, borderRadius: 4, backgroundColor: C.bad, borderWidth: 1.5, borderColor: C.card },
});
