// Design tokens: a deep navy night with the brand's red and orange, glass cards, condensed display numbers.
export const C = {
  bg: '#0B1020',
  bg2: '#111833',
  card: '#151D35',
  card2: '#1C2644',
  glass: 'rgba(255,255,255,0.06)',
  glassStrong: 'rgba(255,255,255,0.10)',
  line: 'rgba(255,255,255,0.08)',
  lineStrong: 'rgba(255,255,255,0.16)',
  txt: '#F2F5FB',
  sub: '#C3CBE0',
  mut: '#8790AD',
  red: '#EE4B52',
  orange: '#FF8A1F',
  amber: '#FFB547',
  good: '#3ECF8E',
  bad: '#FF5D6C',
  blue: '#5B8CFF',
  violet: '#7C5CFF',
};

export const GRAD = {
  page: ['#0B1020', '#0E1530', '#0B1020'] as const,
  hero: ['#EE4B52', '#FF8A1F'] as const,
  violet: ['#5B4BFF', '#8F5BFF'] as const,
  card: ['rgba(255,255,255,0.08)', 'rgba(255,255,255,0.03)'] as const,
  gold: ['#FFB547', '#FF8A1F'] as const,
};

export const R = { sm: 10, md: 16, lg: 22, xl: 28, pill: 999 };
export const S = { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 28 };

export const F = {
  display: 'BarlowCondensed-ExtraBold',
  displayMid: 'BarlowCondensed-SemiBold',
};

// Tablet: wider than this, screens use two columns and a centred column of reading width.
export const TABLET = 768;
export const MAX_W = 1100;
