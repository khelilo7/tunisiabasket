import { router } from 'expo-router';
import { useEffect } from 'react';

import { useApp } from '@/lib/app-state';
import { notifications, syncPush } from '@/lib/push';

const PATHS = ['/scores', '/news', '/votes', '/plays'];

// Keeps the server in step with this phone's choice (club, language, level, switches) and opens the right screen when a notification is tapped.
// Never shows the permission prompt itself: that happens only when the user turns notifications on (club picker, Notifications screen).
export function PushSync() {
  const { ready, notif, fav, lang } = useApp();

  useEffect(() => {
    if (ready) syncPush(notif, fav, lang);
  }, [ready, notif, fav, lang]);

  useEffect(() => {
    const Notif = notifications();
    if (!Notif) return;
    Notif.setNotificationHandler({ handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: false, shouldSetBadge: false }) });
    const open = (path: unknown) => { if (typeof path === 'string' && PATHS.includes(path)) router.push(path as '/scores'); };
    const last = Notif.getLastNotificationResponse();
    if (last) open(last.notification.request.content.data?.path);
    const sub = Notif.addNotificationResponseReceivedListener(r => open(r.notification.request.content.data?.path));
    return () => sub.remove();
  }, []);

  return null;
}
