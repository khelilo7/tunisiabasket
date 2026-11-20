import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { useVideoPlayer, VideoView } from 'expo-video';
import { createElement, useState } from 'react';
import { Linking, Platform, Pressable, StyleSheet, View } from 'react-native';
import { WebView } from 'react-native-webview';

import { C, R } from '@/theme';
import { tap, Txt } from './ui';

export type Clip = { kind: 'youtube' | 'facebook' | 'file'; url: string; embed: string; thumb: string | null; title?: string };

// A clip of the plays of the week: its picture with a play button; a tap plays it right there (YouTube / Facebook in their own player, an .mp4 in the
// phone's player). The embed runs from the site's address so YouTube accepts it in an app.
export function VideoPlayer({ clip }: { clip: Clip }) {
  const [on, setOn] = useState(false);
  return (
    <View style={s.box}>
      {on ? <Playing clip={clip} /> : (
        <Pressable style={StyleSheet.absoluteFill} onPress={() => { tap(); setOn(true); }} accessibilityRole="button" accessibilityLabel={clip.title || 'Play'}>
          {clip.thumb ? <Image source={{ uri: clip.thumb }} style={StyleSheet.absoluteFill} contentFit="cover" transition={150} />
            : <View style={[StyleSheet.absoluteFill, { backgroundColor: C.bg2 }]} />}
          <View style={s.shade} />
          <View style={s.play}><Ionicons name="play" size={30} color="#fff" style={{ marginLeft: 3 }} /></View>
          <View style={s.badge}><Ionicons name={clip.kind === 'youtube' ? 'logo-youtube' : clip.kind === 'facebook' ? 'logo-facebook' : 'film'} size={13} color="#fff" /></View>
        </Pressable>
      )}
    </View>
  );
}

function Playing({ clip }: { clip: Clip }) {
  if (clip.kind === 'file') return <FileVideo url={clip.url} />;
  const src = clip.embed + (clip.embed.includes('?') ? '&' : '?') + 'autoplay=1';
  if (Platform.OS === 'web') {
    return createElement('iframe', { src, style: { border: 0, width: '100%', height: '100%' }, allow: 'autoplay; encrypted-media; picture-in-picture; fullscreen', allowFullScreen: true });
  }
  const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>html,body{margin:0;height:100%;background:#000}iframe{border:0;width:100%;height:100%}</style></head>
<body><iframe src="${src}" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen></iframe></body></html>`;
  return (
    <WebView source={{ html, baseUrl: 'https://tunisiabasket.com' }} style={{ flex: 1, backgroundColor: '#000' }} allowsInlineMediaPlayback allowsFullscreenVideo
      mediaPlaybackRequiresUserAction={false} javaScriptEnabled originWhitelist={['*']}
      onShouldStartLoadWithRequest={r => {                 // a tap on the YouTube or Facebook logo opens their app, not a page inside ours
        if (r.isTopFrame === false || r.url.startsWith('about:') || r.url.startsWith('https://tunisiabasket.com')) return true;
        Linking.openURL(r.url).catch(() => {});
        return false;
      }} />
  );
}

function FileVideo({ url }: { url: string }) {
  const player = useVideoPlayer(url, p => { p.play(); });
  return <VideoView player={player} style={{ flex: 1 }} contentFit="contain" nativeControls fullscreenOptions={{ enable: true }} />;
}

export function OpenLink({ clip, label }: { clip: Clip; label: string }) {
  return (
    <Pressable onPress={() => Linking.openURL(clip.url)} hitSlop={8} style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
      <Txt v="small" c={C.sub}>{label}</Txt><Ionicons name="open-outline" size={12} color={C.sub} />
    </Pressable>
  );
}

const s = StyleSheet.create({
  box: { width: '100%', aspectRatio: 16 / 9, borderRadius: R.md, overflow: 'hidden', backgroundColor: '#000' },
  shade: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(5,8,18,0.25)' },
  play: { position: 'absolute', alignSelf: 'center', top: '50%', marginTop: -30, width: 60, height: 60, borderRadius: 30, backgroundColor: 'rgba(255,61,46,0.92)', alignItems: 'center', justifyContent: 'center' },
  badge: { position: 'absolute', left: 8, top: 8, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 6, paddingVertical: 3, borderRadius: 6, backgroundColor: 'rgba(0,0,0,0.55)' },
});
