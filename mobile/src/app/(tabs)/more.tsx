import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { Linking, Pressable, ScrollView, View } from 'react-native';

import { SocialLinks } from '@/components/fans';
import { Card, Row, Screen, Segmented, tap, TeamLogo, Txt } from '@/components/ui';
import { API, useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { Lang } from '@/lib/i18n';
import { C, F, R } from '@/theme';

export default function More() {
  const { t, lang, setLang, fav, setFav, notif } = useApp();
  const fr = lang === 'fr';
  const ov = useApi<{ standings: { code: string; name: string }[] }>('/api/overview');
  const links: { icon: keyof typeof Ionicons.glyphMap; label: string; go: () => void; value?: string }[] = [
    { icon: 'analytics', label: fr ? 'Pronos & votes' : 'Predictions & votes', go: () => router.push('/votes') },
    { icon: 'play-circle', label: fr ? 'Action de la semaine' : 'Play of the week', go: () => router.push('/plays') },
    { icon: 'notifications', label: 'Notifications', go: () => router.push('/notifications'),
      value: notif.level === 'team' ? (fr ? 'Mon club' : 'My club') : notif.level === 'all' ? (fr ? 'Tout' : 'All') : (fr ? 'Aucune' : 'None') },
    { icon: 'newspaper', label: lang === 'fr' ? 'Actualités' : 'News', go: () => router.push('/news') },
    { icon: 'ribbon', label: t('records'), go: () => router.push('/records') },
    { icon: 'time', label: `${t('history')} · ${t('champions')}`, go: () => router.push('/history') },
    { icon: 'globe-outline', label: t('website'), go: () => Linking.openURL(API + (lang === 'en' ? '/en/' : '/')) },
    { icon: 'shield-checkmark-outline', label: lang === 'fr' ? 'Confidentialité' : 'Privacy policy', go: () => Linking.openURL(API + (lang === 'en' ? '/en/privacy' : '/confidentialite')) },
  ];
  return (
    <Screen>
      <Row style={{ gap: 12, marginBottom: 20 }}>
        <Image source={require('../../../assets/logo.png')} style={{ width: 52, height: 52 }} />
        <View style={{ flex: 1 }}><Txt style={{ fontFamily: F.display, fontSize: 28 }}>TUNISIA <Txt style={{ fontFamily: F.display, fontSize: 28, color: C.red }}>BASKET</Txt></Txt><Txt v="small" numberOfLines={3}>{t('aboutText')}</Txt></View>
      </Row>

      <Txt v="label" style={{ marginBottom: 8 }}>{t('favorite')} · {t('chooseFav')}</Txt>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10 }}>
        {(ov.data?.standings || []).map(s => {
          const on = fav === s.code;
          return (
            <Pressable key={s.code} onPress={() => { tap(); setFav(on ? null : s.code); }} style={{ alignItems: 'center', width: 76, gap: 6 }}>
              <View style={{ padding: 3, borderRadius: 40, borderWidth: 2, borderColor: on ? C.orange : 'transparent' }}><TeamLogo code={s.code} size={58} /></View>
              <Txt v="small" c={on ? C.orange : C.sub} numberOfLines={1}>{s.code}</Txt>
            </Pressable>
          );
        })}
      </ScrollView>

      <Txt v="label" style={{ marginTop: 24, marginBottom: 8 }}>{t('language')}</Txt>
      <Segmented<Lang> value={lang} onChange={setLang} items={[{ key: 'fr', label: 'Français' }, { key: 'en', label: 'English' }]} />

      <Card padded={false} style={{ marginTop: 24 }}>
        {links.map((l, i) => (
          <Pressable key={l.label} onPress={() => { tap(); l.go(); }}>
            <Row style={{ padding: 16, gap: 14, borderTopWidth: i ? 1 : 0, borderColor: C.line }}>
              <View style={{ width: 38, height: 38, borderRadius: R.sm, backgroundColor: 'rgba(255,138,31,0.14)', alignItems: 'center', justifyContent: 'center' }}><Ionicons name={l.icon} size={20} color={C.orange} /></View>
              <Txt v="h3" style={{ flex: 1 }}>{l.label}</Txt>
              {l.value ? <Txt v="small" c={C.sub}>{l.value}</Txt> : null}
              <Ionicons name="chevron-forward" size={18} color={C.mut} />
            </Row>
          </Pressable>
        ))}
      </Card>
      <View style={{ marginTop: 26 }}><SocialLinks big /></View>
      <Txt v="small" style={{ marginTop: 18, textAlign: 'center' }}>© Tunisia Basket · {lang === 'fr' ? 'site indépendant, non affilié à la FTBB' : 'independent, not affiliated with the FTBB'}</Txt>
    </Screen>
  );
}
