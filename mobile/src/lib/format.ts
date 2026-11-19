import { Lang } from './i18n';

export const loc = (l: Lang) => (l === 'fr' ? 'fr-FR' : 'en-GB');

export const dayLabel = (iso: string, l: Lang, opts: Intl.DateTimeFormatOptions = { weekday: 'short', day: 'numeric', month: 'short' }) => {
  try { return new Date(iso + 'T12:00:00').toLocaleDateString(loc(l), opts); } catch { return iso; }
};

export const relDay = (iso: string, l: Lang) => {
  const d = new Date(iso + 'T12:00:00'), now = new Date();
  const diff = Math.round((d.getTime() - new Date(now.toDateString()).getTime() - 12 * 3600e3) / 864e5);
  if (diff === 0) return l === 'fr' ? "Aujourd'hui" : 'Today';
  if (diff === 1) return l === 'fr' ? 'Demain' : 'Tomorrow';
  if (diff === -1) return l === 'fr' ? 'Hier' : 'Yesterday';
  return dayLabel(iso, l);
};

export const titleCase = (s: string) => s.toLowerCase().replace(/(^|[\s'-])\p{L}/gu, c => c.toUpperCase());
export const one = (n?: number | null) => (n == null ? '–' : Number.isInteger(n) ? String(n) : n.toFixed(1));
export const pct = (n?: number | null) => (n == null ? '–' : `${Math.round(n)}%`);
export const seasonLbl = (s: string) => s.replace('-', '/');
