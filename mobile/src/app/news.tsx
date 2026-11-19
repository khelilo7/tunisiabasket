import { useState } from 'react';
import { View } from 'react-native';

import { News, NEWS_LABEL, NewsCard } from '@/components/news';
import { Chips, Empty, ErrorView, Grid, Header, Loading, Screen, Txt } from '@/components/ui';
import { useApi } from '@/lib/api';
import { useApp } from '@/lib/app-state';

export default function NewsScreen() {
  const { lang } = useApp();
  const { data, error, refresh, refreshing } = useApi<{ items: News[] }>('/api/news');
  const [label, setLabel] = useState('all');
  const title = lang === 'fr' ? 'Actualités' : 'News';
  const items = (data?.items || []).filter(n => label === 'all' || n.label === label);
  const present = Array.from(new Set((data?.items || []).map(n => n.label)));
  return (
    <Screen header={<Header />} onRefresh={refresh} refreshing={refreshing}>
      <Txt v="h1">{title}</Txt>
      {present.length > 1 ? (
        <View style={{ marginTop: 10, marginBottom: 4 }}>
          <Chips<string> value={label} onChange={setLabel} items={[{ key: 'all', label: lang === 'fr' ? 'Tout' : 'All' }, ...present.map(k => ({ key: k, label: (NEWS_LABEL[k] || NEWS_LABEL.info)[lang] }))]} />
        </View>
      ) : null}
      {error && !data ? <ErrorView onRetry={refresh} /> : null}
      {!data && !error ? <Loading /> : null}
      {data && !items.length ? <Empty text={lang === 'fr' ? 'Pas encore d’actualité' : 'No news yet'} /> : null}
      <View style={{ marginTop: 12 }}><Grid>{items.map(n => <NewsCard key={n.id} n={n} />)}</Grid></View>
    </Screen>
  );
}
