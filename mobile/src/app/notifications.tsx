import { Ionicons } from '@expo/vector-icons';
import { useEffect, useState } from 'react';
import { Linking, Pressable, Switch, View } from 'react-native';

import { Card, Header, Row, Screen, tap, TeamLogo, Txt } from '@/components/ui';
import { useApp } from '@/lib/app-state';
import { Level, NotifPrefs, PUSH_SUPPORTED, PushStatus, syncPush } from '@/lib/push';
import { C, R } from '@/theme';

// What this phone is told: nothing, my club only (its results and news), or everything; and which kinds (results, news, votes).
export default function Notifications() {
  const { lang, fav, askFav, notif, setNotif } = useApp();
  const fr = lang === 'fr';
  const [status, setStatus] = useState<PushStatus | null>(null);

  useEffect(() => { syncPush(notif, fav, lang).then(setStatus); }, [notif, fav, lang]);

  const change = (p: NotifPrefs) => {
    tap(); setNotif(p);
    if (p.level !== 'none') syncPush(p, fav, lang, true).then(setStatus);         // the system asks for the permission here, after the user's choice
  };

  const levels: { key: Level; icon: keyof typeof Ionicons.glyphMap; title: string; sub: string }[] = [
    { key: 'team', icon: 'star', title: fr ? 'Mon club' : 'My club', sub: fav ? (fr ? `Les résultats et les actus de ${fav} seulement` : `Only ${fav}'s results and news`) : (fr ? 'Choisis d’abord ton club' : 'Choose your club first') },
    { key: 'all', icon: 'basketball', title: fr ? 'Toute la Pro A' : 'All of Pro A', sub: fr ? 'Chaque résultat et chaque actu' : 'Every result and every news item' },
    { key: 'none', icon: 'notifications-off', title: fr ? 'Aucune' : 'None', sub: fr ? 'Pas de notification' : 'No notifications' },
  ];
  const topics: { key: 'results' | 'news' | 'votes'; title: string; sub: string }[] = [
    { key: 'results', title: fr ? 'Résultats' : 'Results', sub: fr ? 'Le score final dès qu’il est publié' : 'The final score as soon as it is published' },
    { key: 'news', title: fr ? 'Actualités' : 'News', sub: fr ? 'Transferts, blessures, annonces' : 'Transfers, injuries, announcements' },
    { key: 'votes', title: fr ? 'Votes et pronostics' : 'Votes and predictions', sub: fr ? 'Quand un vote ou les pronostics ouvrent' : 'When a vote or the predictions open' },
  ];

  const note = !PUSH_SUPPORTED ? (fr ? 'Les notifications marchent dans l’app installée (Play Store, ou la version de test). Pas dans Expo Go ni sur le web.' : 'Notifications work in the installed app (Play Store, or the test build). Not in Expo Go or on the web.')
    : status === 'denied' ? (fr ? 'Les notifications sont bloquées pour Tunisia Basket dans les réglages du téléphone.' : 'Notifications are blocked for Tunisia Basket in the phone settings.')
    : status === 'noclub' ? (fr ? 'Choisis ton club pour recevoir ses notifications.' : 'Choose your club to get its notifications.')
    : status === 'error' ? (fr ? 'Pas de connexion : ton choix sera envoyé plus tard.' : 'No connection: your choice will be sent later.')
    : status === 'ok' ? (fr ? 'Activées sur ce téléphone.' : 'On for this phone.') : '';

  return (
    <Screen header={<Header title="Notifications" />}>
      <Card padded={false}>
        {levels.map((l, i) => {
          const on = notif.level === l.key;
          return (
            <Pressable key={l.key} onPress={() => { if (l.key === 'team' && !fav) { askFav(); return; } change({ ...notif, level: l.key }); }}>
              <Row style={{ padding: 14, gap: 12, borderTopWidth: i ? 1 : 0, borderColor: C.line }}>
                {l.key === 'team' && fav ? <TeamLogo code={fav} size={36} /> : (
                  <View style={{ width: 36, height: 36, borderRadius: R.sm, backgroundColor: on ? 'rgba(255,138,31,0.16)' : C.glass, alignItems: 'center', justifyContent: 'center' }}>
                    <Ionicons name={l.icon} size={18} color={on ? C.orange : C.sub} />
                  </View>
                )}
                <View style={{ flex: 1 }}><Txt v="h3">{l.title}</Txt><Txt v="small">{l.sub}</Txt></View>
                <Ionicons name={on ? 'radio-button-on' : 'radio-button-off'} size={22} color={on ? C.orange : C.mut} />
              </Row>
            </Pressable>
          );
        })}
      </Card>

      {notif.level !== 'none' ? (
        <>
          <Txt v="label" style={{ marginTop: 22, marginBottom: 8 }}>{fr ? 'Recevoir' : 'Send me'}</Txt>
          <Card padded={false}>
            {topics.map((tp, i) => (
              <Row key={tp.key} style={{ padding: 14, gap: 12, borderTopWidth: i ? 1 : 0, borderColor: C.line }}>
                <View style={{ flex: 1 }}><Txt v="h3">{tp.title}</Txt><Txt v="small">{tp.sub}</Txt></View>
                <Switch value={notif[tp.key]} onValueChange={v => change({ ...notif, [tp.key]: v })} trackColor={{ true: C.orange, false: C.glassStrong }} thumbColor="#fff" />
              </Row>
            ))}
          </Card>
          {notif.level === 'team' ? <Txt v="small" style={{ marginTop: 8 }}>{fr ? 'Votes et pronostics concernent toute la ligue.' : 'Votes and predictions are league-wide.'}</Txt> : null}
        </>
      ) : null}

      {note ? (
        <Row style={{ gap: 8, marginTop: 18, alignItems: 'flex-start' }}>
          <Ionicons name={status === 'ok' ? 'checkmark-circle' : 'information-circle'} size={16} color={status === 'ok' ? C.good : C.mut} style={{ marginTop: 1 }} />
          <Txt v="small" c={status === 'ok' ? C.good : C.sub} style={{ flex: 1 }}>{note}</Txt>
        </Row>
      ) : null}
      {status === 'denied' ? (
        <Pressable onPress={() => Linking.openSettings()} style={{ marginTop: 10, alignSelf: 'flex-start' }}><Txt v="sub" c={C.orange} style={{ fontWeight: '700' }}>{fr ? 'Ouvrir les réglages ›' : 'Open settings ›'}</Txt></Pressable>
      ) : null}
    </Screen>
  );
}
