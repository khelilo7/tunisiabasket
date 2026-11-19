import { Modal, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { C, R } from '@/theme';
import { tap, TeamLogo, Txt, useLayout } from './ui';

// Asked once, on the first launch: a quiet sheet over the home screen. A tap picks the club and it is kept for good (it can still be changed in More);
// "later" closes it and it never comes back by itself.
export function ClubPicker() {
  const { lang, setFav, skipFav } = useApp();
  const ins = useSafeAreaInsets();
  const { tablet } = useLayout();
  const { data } = useApi<{ standings: { code: string; name: string }[] }>('/api/overview');
  const clubs = (data?.standings || []).slice().sort((a, b) => a.name.localeCompare(b.name));
  const fr = lang === 'fr';
  return (
    <Modal transparent animationType="slide" visible onRequestClose={skipFav} statusBarTranslucent>
      <Pressable style={s.backdrop} onPress={skipFav} />
      <View style={[s.sheet, { paddingBottom: ins.bottom + 18 }, tablet && s.sheetTablet]}>
        <View style={s.grip} />
        <Txt v="h3" style={{ fontSize: 17 }}>{fr ? 'Ton club ?' : 'Your club?'}</Txt>
        <Txt v="small" style={{ marginTop: 2, marginBottom: 14 }}>{fr ? 'Ses matchs et son classement passent en premier.' : 'Its games and standing come first.'}</Txt>
        <View style={s.grid}>
          {clubs.map(c => (
            <Pressable key={c.code} onPress={() => { tap(); setFav(c.code); }} style={({ pressed }) => [s.club, pressed && { backgroundColor: C.glassStrong }]}>
              <TeamLogo code={c.code} size={46} />
              <Txt v="small" c={C.sub} numberOfLines={1} style={{ marginTop: 6 }}>{c.code}</Txt>
            </Pressable>
          ))}
        </View>
        <Pressable onPress={skipFav} hitSlop={10} style={{ alignSelf: 'center', marginTop: 12 }}>
          <Txt v="small" c={C.mut}>{fr ? 'Plus tard' : 'Later'}</Txt>
        </Pressable>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(5,8,18,0.55)' },
  sheet: { backgroundColor: C.bg2, borderTopLeftRadius: R.xl, borderTopRightRadius: R.xl, borderWidth: 1, borderColor: C.line, paddingHorizontal: 18, paddingTop: 10 },
  sheetTablet: { alignSelf: 'center', width: 560, marginBottom: 24, borderRadius: R.xl },
  grip: { alignSelf: 'center', width: 38, height: 4, borderRadius: 2, backgroundColor: C.lineStrong, marginBottom: 14 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', rowGap: 6 },
  club: { width: '24%', alignItems: 'center', paddingVertical: 8, borderRadius: R.md },
});
