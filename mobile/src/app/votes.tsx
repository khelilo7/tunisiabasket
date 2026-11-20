import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { ReactNode, useState } from 'react';
import { Pressable, View } from 'react-native';

import { closesIn, ErrLine, MineTag, ShareBar, useVote, VoteBtn } from '@/components/vote';
import { Avatar, Card, Empty, ErrorView, Header, Loading, Pill, Row, Screen, Section, Segmented, tap, TeamLogo, Txt } from '@/components/ui';
import { useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';
import { C, R } from '@/theme';

// The fans' corner: predictions of the next matchday, the player of the round, the phase MVP. Every vote is final; shares show once you voted (or it ended).
type Tab = 'predict' | 'round' | 'mvp';

type PGame = { key: string; home: string; away: string; home_name: string; away_name: string; my: 'H' | 'A' | null; split?: { H: number; A: number } | null };
type Predict = { round: null | { matchday: number; date: string; deadline_ts: number | null; open: boolean; games: PGame[]; picked: number; of: number } };
type Cand = { id: string; name: string; team: string; number?: number; photo?: string | null; pts: number; reb: number; ast: number; pir?: number | null; votes: number; vote_share: number;
  game?: { id: string; opp: string; score: string } };
type Round = { round: number | null; open?: boolean; deadline_ts?: number | null; total_votes?: number; candidates?: Cand[]; winner?: Cand | null; my_vote?: string | null;
  history: { round: number; winner: Cand; game?: { opp: string; score: string } }[] };
type Mvp = { phase: number; voting_open: boolean; ballot: string[]; candidates: Cand[]; winner: Cand | null; my_vote: string | null; deadline_ts: number | null; total_votes: number; complete: boolean };

export default function Votes() {
  const { tab: start } = useLocalSearchParams<{ tab?: Tab }>();
  const [tab, setTab] = useState<Tab>(start === 'round' || start === 'mvp' ? start : 'predict');
  const { lang } = useApp();
  const fr = lang === 'fr';
  return (
    <Screen header={<Header title={fr ? 'Pronos & votes' : 'Predictions & votes'} />}>
      <Segmented<Tab> value={tab} onChange={setTab} items={[
        { key: 'predict', label: fr ? 'Pronostics' : 'Predictions' },
        { key: 'round', label: fr ? 'Joueur J.' : 'Player' },
        { key: 'mvp', label: 'MVP' },
      ]} />
      {tab === 'predict' ? <Predictions /> : tab === 'round' ? <PlayerOfRound /> : <PhaseMvp />}
      <Pressable onPress={() => { tap(); router.push('/plays'); }} style={{ marginTop: 22 }}>
        <Card style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <View style={{ width: 40, height: 40, borderRadius: R.sm, backgroundColor: 'rgba(238,75,82,0.16)', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="play-circle" size={24} color={C.red} /></View>
          <View style={{ flex: 1 }}><Txt v="h3">{fr ? 'Action de la semaine' : 'Play of the week'}</Txt><Txt v="small">{fr ? 'Regarde les vidéos et vote pour la plus belle' : 'Watch the clips and vote for the best'}</Txt></View>
          <Ionicons name="chevron-forward" size={18} color={C.mut} />
        </Card>
      </Pressable>
    </Screen>
  );
}

// ---------------------------------------------------------------- predictions
function Predictions() {
  const { vid, lang } = useApp();
  const fr = lang === 'fr';
  const { data, error, refresh } = useApi<Predict>(vid ? `/api/predict?vid=${vid}` : null);
  const { busy, err, send } = useVote('/api/predict/pick', refresh, fr);
  if (!data) return error ? <ErrorView onRetry={refresh} /> : <Loading />;
  const r = data.round;
  if (!r) return <View style={{ marginTop: 16 }}><Empty text={fr ? 'Pas de journée à pronostiquer pour l’instant.' : 'No round to predict right now.'} /></View>;
  return (
    <View style={{ marginTop: 16 }}>
      <Row style={{ justifyContent: 'space-between', marginBottom: 10 }}>
        <View>
          <Txt v="h2">{fr ? `Journée ${r.matchday}` : `Round ${r.matchday}`}</Txt>
          <Txt v="small">{r.open ? `${fr ? 'Qui va gagner ?' : 'Who wins?'} · ${closesIn(r.deadline_ts, fr)}` : (fr ? 'Pronostics fermés' : 'Predictions closed')}</Txt>
        </View>
        <Pill label={`${r.picked}/${r.of}`} color={r.picked === r.of ? C.good : C.glassStrong} text={r.picked === r.of ? '#08130D' : C.txt} icon="checkmark-done" />
      </Row>
      <View style={{ gap: 10 }}>
        {r.games.map(g => (
          <Card key={g.key} style={{ paddingVertical: 12 }}>
            <Row style={{ gap: 10 }}>
              <Side code={g.home} name={g.home_name} on={g.my === 'H'} off={!!g.my && g.my !== 'H'} busy={busy === g.key + 'H'}
                disabled={!r.open || !!g.my} onPress={() => send(g.key + 'H', { game: g.key, side: 'H', vid })} />
              <Txt v="label" style={{ width: 22, textAlign: 'center' }}>vs</Txt>
              <Side code={g.away} name={g.away_name} on={g.my === 'A'} off={!!g.my && g.my !== 'A'} busy={busy === g.key + 'A'}
                disabled={!r.open || !!g.my} onPress={() => send(g.key + 'A', { game: g.key, side: 'A', vid })} />
            </Row>
            {g.split ? (
              <View style={{ marginTop: 10 }}>
                <View style={{ flexDirection: 'row', height: 6, borderRadius: 3, overflow: 'hidden', gap: 3 }}>
                  <View style={{ flex: Math.max(1, g.split.H), backgroundColor: g.my === 'H' ? C.orange : C.lineStrong }} />
                  <View style={{ flex: Math.max(1, g.split.A), backgroundColor: g.my === 'A' ? C.orange : C.lineStrong }} />
                </View>
                <Row style={{ justifyContent: 'space-between', marginTop: 4 }}>
                  <Txt v="small" c={g.my === 'H' ? C.orange : C.sub}>{g.split.H}%</Txt>
                  <Txt v="small">{fr ? 'des fans' : 'of fans'}</Txt>
                  <Txt v="small" c={g.my === 'A' ? C.orange : C.sub}>{g.split.A}%</Txt>
                </Row>
              </View>
            ) : null}
          </Card>
        ))}
      </View>
      <ErrLine text={err} />
      <Txt v="small" style={{ marginTop: 10 }}>{fr ? 'Touche le vainqueur. Un pronostic est définitif ; la répartition des fans s’affiche ensuite.' : 'Tap the winner. A pick is final; the fans’ split shows after.'}</Txt>
    </View>
  );
}

function Side({ code, name, on, off, busy, disabled, onPress }: { code: string; name: string; on: boolean; off: boolean; busy: boolean; disabled: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} disabled={disabled || busy} style={({ pressed }) => [{ flex: 1, alignItems: 'center', gap: 6, paddingVertical: 8, borderRadius: R.md, borderWidth: 1.5,
      borderColor: on ? C.orange : 'transparent', backgroundColor: on ? 'rgba(255,138,31,0.12)' : C.glass, opacity: off ? 0.45 : 1 }, pressed && { opacity: 0.7 }]}>
      <TeamLogo code={code} size={44} />
      <Txt v="small" c={on ? C.orange : C.txt} numberOfLines={1} style={{ fontWeight: '700' }}>{busy ? '…' : name}</Txt>
    </Pressable>
  );
}

// ---------------------------------------------------------------- player of the round
function PlayerOfRound() {
  const { vid, lang } = useApp();
  const fr = lang === 'fr';
  const { data, error, refresh } = useApi<Round>(vid ? `/api/round?vid=${vid}` : null);
  const { busy, err, send } = useVote('/api/round/vote', refresh, fr);
  if (!data) return error ? <ErrorView onRetry={refresh} /> : <Loading />;
  const reveal = !!data.my_vote || !data.open;
  const top = Math.max(0, ...(data.candidates || []).map(c => c.votes));
  return (
    <View style={{ marginTop: 16 }}>
      {data.round ? (
        <>
          <Txt v="h2">{fr ? `Joueur de la J${data.round}` : `Player of round ${data.round}`}</Txt>
          <Txt v="small" style={{ marginBottom: 10 }}>{data.open ? `${fr ? 'Le meilleur joueur de chaque match' : 'The best player of each game'}${data.deadline_ts ? ' · ' + closesIn(data.deadline_ts, fr) : ''}`
            : `${fr ? 'Vote terminé' : 'Voting over'} · ${data.total_votes || 0} ${fr ? 'votes' : 'votes'}`}</Txt>
          {data.winner ? <WinnerCard c={data.winner} label={fr ? `Joueur de la J${data.round}` : `Player of round ${data.round}`} /> : null}
          <View style={{ gap: 10 }}>
            {(data.candidates || []).map(c => (
              <CandRow key={c.id} c={c} fr={fr} mine={data.my_vote === c.id} reveal={reveal} lead={reveal && c.votes === top && top > 0}
                sub={c.game ? `${fr ? 'vs' : 'vs'} ${c.game.opp} · ${c.game.score}` : ''}
                action={data.open && !data.my_vote ? <VoteBtn label={fr ? 'Voter' : 'Vote'} busy={busy === c.id} onPress={() => send(c.id, { round: data.round, player: c.id, vid })} /> : null} />
            ))}
          </View>
          <ErrLine text={err} />
        </>
      ) : <Empty text={fr ? 'Le vote ouvre quand tous les matchs de la journée sont joués.' : 'Voting opens once every game of the round is played.'} />}
      {data.history.length ? (
        <Section title={fr ? 'Précédents' : 'Earlier rounds'}>
          <Card padded={false}>
            {data.history.map((h, i) => (
              <Pressable key={h.round} onPress={() => { tap(); router.push(`/player/${h.winner.id}`); }}>
                <Row style={{ padding: 12, gap: 12, borderTopWidth: i ? 1 : 0, borderColor: C.line }}>
                  <Txt v="label" style={{ width: 34 }}>J{h.round}</Txt>
                  <Avatar photo={h.winner.photo} name={h.winner.name} size={36} team={h.winner.team} />
                  <View style={{ flex: 1 }}><Txt v="h3" numberOfLines={1}>{h.winner.name}</Txt><Txt v="small">{h.winner.vote_share}% {fr ? 'des votes' : 'of votes'}</Txt></View>
                  <Ionicons name="trophy" size={16} color={C.amber} />
                </Row>
              </Pressable>
            ))}
          </Card>
        </Section>
      ) : null}
    </View>
  );
}

// ---------------------------------------------------------------- phase MVP
function PhaseMvp() {
  const { lang, vid } = useApp();
  const fr = lang === 'fr';
  const p1 = useApi<Mvp>(vid ? `/api/mvp?phase=1&vid=${vid}` : null);
  const p2 = useApi<Mvp>(vid ? `/api/mvp?phase=2&vid=${vid}` : null);
  if (!p1.data || !p2.data) return (p1.error || p2.error) ? <ErrorView onRetry={() => { p1.refresh(); p2.refresh(); }} /> : <Loading />;
  const phases = [p2.data, p1.data].filter(p => p.candidates.length);           // the newest phase first
  if (!phases.length) return <View style={{ marginTop: 16 }}><Empty text={fr ? 'La course au MVP commence après les premières journées.' : 'The MVP race starts after the first rounds.'} /></View>;
  return <View style={{ marginTop: 16, gap: 22 }}>{phases.map(p => <MvpPhase key={p.phase} p={p} refresh={p.phase === 1 ? p1.refresh : p2.refresh} />)}</View>;
}

function MvpPhase({ p, refresh }: { p: Mvp; refresh: () => void }) {
  const { vid, lang } = useApp();
  const fr = lang === 'fr';
  const { busy, err, send } = useVote(`/api/mvp/vote?phase=${p.phase}`, refresh, fr);
  const d = p;
  const open = d.voting_open && d.ballot.length > 0 && !d.winner;
  const ballot = d.ballot.map(id => d.candidates.find(c => c.id === id)).filter(Boolean) as Cand[];
  const reveal = !!d.my_vote || !open;
  const top = Math.max(0, ...ballot.map(c => c.votes));
  return (
    <View>
      <Txt v="h2">{fr ? `MVP · phase ${p.phase}` : `MVP · phase ${p.phase}`}</Txt>
      <Txt v="small" style={{ marginBottom: 10 }}>{open ? `${fr ? 'Vote des fans parmi les 3 meilleurs' : 'Fans’ vote among the top 3'}${d.deadline_ts ? ' · ' + closesIn(d.deadline_ts, fr) : ''}`
        : d.winner ? `${d.total_votes} ${fr ? 'votes' : 'votes'}` : (fr ? 'Le vote ouvre en fin de phase' : 'Voting opens at the end of the phase')}</Txt>
      {d.winner ? <WinnerCard c={d.winner} label={`MVP · phase ${p.phase}`} /> : null}
      {ballot.length ? (
        <View style={{ gap: 10 }}>
          {ballot.map(c => (
            <CandRow key={c.id} c={c} fr={fr} mine={d.my_vote === c.id} reveal={reveal} lead={reveal && c.votes === top && top > 0}
              sub={`${c.pts} pts · ${c.reb} reb · ${c.ast} ast ${fr ? 'par match' : 'per game'}`}
              action={open && !d.my_vote ? <VoteBtn label={fr ? 'Voter' : 'Vote'} busy={busy === c.id} onPress={() => send(c.id, { player: c.id, vid, phase: p.phase })} /> : null} />
          ))}
        </View>
      ) : !d.winner ? (
        <Card padded={false}>
          {d.candidates.slice(0, 5).map((c, i) => (
            <CandRow key={c.id} c={c} fr={fr} flat first={!i} sub={`${c.pts} pts · ${c.reb} reb · ${c.ast} ast`} rank={i + 1} />
          ))}
        </Card>
      ) : null}
      <ErrLine text={err} />
    </View>
  );
}

// ---------------------------------------------------------------- pieces
function WinnerCard({ c, label }: { c: Cand; label: string }) {
  return (
    <Pressable onPress={() => { tap(); router.push(`/player/${c.id}`); }} style={{ marginBottom: 12 }}>
      <View style={{ borderRadius: R.lg, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: 'rgba(255,181,71,0.12)', borderWidth: 1, borderColor: 'rgba(255,181,71,0.45)' }}>
        <Avatar photo={c.photo} name={c.name} size={58} team={c.team} />
        <View style={{ flex: 1 }}>
          <Row style={{ gap: 6 }}><Ionicons name="trophy" size={14} color={C.amber} /><Txt v="label" c={C.amber}>{label}</Txt></Row>
          <Txt v="h3" style={{ fontSize: 18, marginTop: 2 }} numberOfLines={1}>{c.name}</Txt>
          <Txt v="small">{c.vote_share}% · {c.votes} votes</Txt>
        </View>
      </View>
    </Pressable>
  );
}

function CandRow({ c, fr, mine, reveal, lead, sub, action, flat, first, rank }: { c: Cand; fr: boolean; mine?: boolean; reveal?: boolean; lead?: boolean; sub: string; action?: ReactNode;
  flat?: boolean; first?: boolean; rank?: number }) {
  const body = (
    <>
      <Row style={{ gap: 12 }}>
        {rank ? <Txt v="num" c={rank === 1 ? C.orange : C.mut} style={{ width: 20, fontSize: 18 }}>{rank}</Txt> : null}
        <Pressable onPress={() => { tap(); router.push(`/player/${c.id}`); }}><Avatar photo={c.photo} name={c.name} size={46} team={c.team} /></Pressable>
        <View style={{ flex: 1 }}>
          <Txt v="h3" numberOfLines={1}>{c.name}</Txt>
          <Txt v="small" numberOfLines={1}>{sub}</Txt>
        </View>
        {mine ? <MineTag fr={fr} /> : action}
      </Row>
      {reveal ? <View style={{ marginTop: 10 }}><ShareBar share={c.vote_share} mine={mine} lead={lead} /></View> : null}
    </>
  );
  if (flat) return <View style={{ padding: 12, borderTopWidth: first ? 0 : 1, borderColor: C.line }}>{body}</View>;
  return <Card glow={mine ? C.orange : undefined} style={{ paddingVertical: 12 }}>{body}</Card>;
}
