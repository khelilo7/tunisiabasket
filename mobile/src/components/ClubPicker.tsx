import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { Modal, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { PUSH_SUPPORTED, syncPush } from '@/lib/push';
import { C, R } from '@/theme';
import { tap, TeamLogo, Txt, useLayout } from './ui';

// A quiet sheet over the home screen: on the first launch, again three days after "later", never after "don't ask again"; the "My club" pill of the home header
// opens it any time. A tap picks the club and it is kept for good (changed from More or a team's star).
export function ClubPicker() {
  const { lang, setFav, skipFav, notif, setNotif } = useApp();
  const [bell, setBell] = useState(notif.level !== 'none' || PUSH_SUPPORTED);      // "tell me its results": on by default where notifications exist
  const ins = useSafeAreaInsets();
  const { tablet } = useLayout();
  const { data } = useApi<{ standings: { code: string; name: string }[] }>('/api/overview');
  const clubs = (data?.standings || []).slice().sort((a, b) => a.name.localeCompare(b.name));
  const fr = lang === 'fr';
  const pick = (code: string) => {
    setFav(code);
    if (bell && notif.level === 'none') {
      const next = { ...notif, level: 'team' as const };
      setNotif(next);
      syncPush(next, code, lang, true);                 // the system asks for the permission now, right after the user's tap
    }
  };
  return (
    <Modal transparent animationType="slide" visible onRequestClose={() => skipFav()} statusBarTranslucent>
      <Pressable style={s.backdrop} onPress={() => skipFav()} />
      <View style={[s.sheet, { paddingBottom: ins.bottom + 18 }, tablet && s.sheetTablet]}>
        <View style={s.grip} />
        <Txt v="h3" style={{ fontSize: 17 }}>{fr ? 'Ton club ?' : 'Your club?'}</Txt>
        <Txt v="small" style={{ marginTop: 2, marginBottom: 14 }}>{fr ? 'Ses matchs et son classement passent en premier.' : 'Its games and standing come first.'}</Txt>
        <View style={s.grid}>
          {clubs.map(c => (
            <Pressable key={c.code} onPress={() => { tap(); pick(c.code); }} style={({ pressed }) => [s.club, pressed && { backgroundColor: C.glassStrong }]}>
              <TeamLogo code={c.code} size={46} />
              <Txt v="small" c={C.sub} numberOfLines={1} style={{ marginTop: 6 }}>{c.code}</Txt>
            </Pressable>
          ))}
        </View>
        {PUSH_SUPPORTED && notif.level === 'none' ? (
          <Pressable onPress={() => { tap(); setBell(!bell); }} style={s.bell} hitSlop={6}>
            <Ionicons name={bell ? 'notifications' : 'notifications-off-outline'} size={16} color={bell ? C.orange : C.mut} />
            <Txt v="small" c={bell ? C.txt : C.mut} style={{ flex: 1 }}>{fr ? 'Me notifier de ses résultats et de ses actus' : 'Notify me of its results and news'}</Txt>
            <View style={[s.check, bell && { backgroundColor: C.orange, borderColor: C.orange }]}>{bell ? <Ionicons name="checkmark" size={13} color="#1A1205" /> : null}</View>
          </Pressable>
        ) : null}
        <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 22, marginTop: 12 }}>
          <Pressable onPress={() => skipFav()} hitSlop={10}><Txt v="small" c={C.sub}>{fr ? 'Plus tard' : 'Later'}</Txt></Pressable>
          <Pressable onPress={() => skipFav(true)} hitSlop={10}><Txt v="small" c={C.mut}>{fr ? 'Ne plus demander' : 'Don’t ask again'}</Txt></Pressable>
        </View>
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
  bell: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10, paddingVertical: 10, paddingHorizontal: 12, borderRadius: R.md, backgroundColor: C.glass },
  check: { width: 20, height: 20, borderRadius: 6, borderWidth: 1.5, borderColor: C.lineStrong, alignItems: 'center', justifyContent: 'center' },
});
