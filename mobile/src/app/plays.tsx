import { Ionicons } from '@expo/vector-icons';
import { View } from 'react-native';

import { Card, Empty, ErrorView, Header, Loading, Row, Screen, Section, TeamLogo, Txt } from '@/components/ui';
import { Clip, OpenLink, VideoPlayer } from '@/components/VideoPlayer';
import { closesIn, ErrLine, MineTag, ShareBar, useVote, VoteBtn } from '@/components/vote';
import { useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { C, R } from '@/theme';

// Play of the week: the admin picks a few clips, the fans vote for the best one. The winner stays here until the next week opens, then joins the archive.
type PClip = Clip & { id: string; title: string; player: string; team: string; votes: number | null; vote_share: number | null };
type Plays = {
  week: null | { id: string; title: string; open: boolean; deadline_ts: number | null; clips: PClip[]; my_vote: string | null; total_votes: number | null; winner: PClip | null };
  archive: { id: string; title: string; winner: PClip }[];
};

export default function PlaysScreen() {
  const { vid, lang } = useApp();
  const fr = lang === 'fr';
  const { data, error, refresh, refreshing } = useApi<Plays>(vid ? `/api/plays?vid=${vid}` : null);
  const { busy, err, send } = useVote('/api/plays/vote', refresh, fr);
  const header = <Header title={fr ? 'Action de la semaine' : 'Play of the week'} />;
  if (!data) return <Screen header={header}>{error ? <ErrorView onRetry={refresh} /> : <Loading />}</Screen>;
  const w = data.week;
  const top = Math.max(0, ...(w?.clips || []).map(c => c.votes || 0));
  return (
    <Screen header={header} onRefresh={refresh} refreshing={refreshing}>
      {!w ? <Empty text={fr ? 'Les actions de la semaine arrivent bientôt.' : 'The plays of the week are coming soon.'} /> : (
        <>
          <Txt v="h1" style={{ fontSize: 30 }}>{w.title}</Txt>
          <Txt v="small" style={{ marginBottom: 14 }}>{w.open
            ? `${fr ? 'Regarde et vote pour la plus belle action' : 'Watch and vote for the best play'}${w.deadline_ts ? ' · ' + closesIn(w.deadline_ts, fr) : ''}`
            : `${fr ? 'Vote terminé' : 'Voting over'}${w.total_votes != null ? ` · ${w.total_votes} votes` : ''}`}</Txt>
          {w.winner ? (
            <View style={{ marginBottom: 18, borderRadius: R.lg, padding: 12, backgroundColor: 'rgba(255,181,71,0.10)', borderWidth: 1, borderColor: 'rgba(255,181,71,0.45)', gap: 10 }}>
              <Row style={{ gap: 6 }}><Ionicons name="trophy" size={15} color={C.amber} /><Txt v="label" c={C.amber}>{fr ? 'Action de la semaine' : 'Play of the week'}</Txt></Row>
              <VideoPlayer clip={w.winner} />
              <ClipLine c={w.winner} fr={fr} />
            </View>
          ) : null}
          <View style={{ gap: 14 }}>
            {w.clips.filter(c => c.id !== w.winner?.id).map(c => (
              <Card key={c.id} padded={false} glow={w.my_vote === c.id ? C.orange : undefined}>
                <VideoPlayer clip={c} />
                <View style={{ padding: 12, gap: 10 }}>
                  <Row style={{ gap: 10 }}>
                    <View style={{ flex: 1 }}><ClipLine c={c} fr={fr} /></View>
                    {w.my_vote === c.id ? <MineTag fr={fr} /> : w.open && !w.my_vote ? <VoteBtn label={fr ? 'Voter' : 'Vote'} busy={busy === c.id} onPress={() => send(c.id, { week: w.id, clip: c.id, vid })} /> : null}
                  </Row>
                  {c.vote_share != null ? <ShareBar share={c.vote_share} mine={w.my_vote === c.id} lead={(c.votes || 0) === top && top > 0} /> : null}
                </View>
              </Card>
            ))}
          </View>
          <ErrLine text={err} />
          {w.open ? <Txt v="small" style={{ marginTop: 10 }}>{fr ? 'Un vote par téléphone, définitif. Les pourcentages s’affichent après ton vote.' : 'One final vote per phone. The percentages show after you vote.'}</Txt> : null}
        </>
      )}
      {data.archive.length ? (
        <Section title={fr ? 'Les gagnants' : 'Past winners'}>
          <View style={{ gap: 14 }}>
            {data.archive.map(a => (
              <Card key={a.id} padded={false}>
                <VideoPlayer clip={a.winner} />
                <View style={{ padding: 12 }}>
                  <Row style={{ gap: 6, marginBottom: 4 }}><Ionicons name="trophy" size={13} color={C.amber} /><Txt v="label" c={C.amber}>{a.title}</Txt></Row>
                  <ClipLine c={a.winner} fr={fr} />
                </View>
              </Card>
            ))}
          </View>
        </Section>
      ) : null}
    </Screen>
  );
}

function ClipLine({ c, fr }: { c: PClip; fr: boolean }) {
  return (
    <View style={{ gap: 4 }}>
      <Txt v="h3" numberOfLines={2}>{c.title}</Txt>
      <Row style={{ gap: 8 }}>
        {c.team ? <TeamLogo code={c.team} size={20} /> : null}
        {c.player || c.team ? <Txt v="small" numberOfLines={1} style={{ flexShrink: 1 }}>{[c.player, c.team].filter(Boolean).join(' · ')}</Txt> : null}
        <OpenLink clip={c} label={c.kind === 'youtube' ? 'YouTube' : c.kind === 'facebook' ? 'Facebook' : (fr ? 'Ouvrir' : 'Open')} />
      </Row>
    </View>
  );
}
