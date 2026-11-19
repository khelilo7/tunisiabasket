// French first (the league's language), English for the rest. t('key') falls back to English, then to the key itself.
export type Lang = 'fr' | 'en';

const EN = {
  home: 'Home', scores: 'Scores', standings: 'Standings', players: 'Players', more: 'More', fantasy: 'Fantasy',
  hello: 'Welcome back', proA: 'Pro A', season: 'Season', latest: 'Latest results', upcoming: 'Coming up', seeAll: 'See all',
  final: 'Final', live: 'Live', today: 'Today', matchday: 'Matchday', day: 'Day', vs: 'vs', at: 'at',
  playerOfRound: 'Player of the round', mvpRace: 'MVP race', leaders: 'League leaders', topPerformers: 'Top performers',
  boxScore: 'Box score', summary: 'Summary', comparison: 'Comparison', quarters: 'By quarter', team: 'Team', starters: 'Starters', bench: 'Bench',
  pts: 'PTS', reb: 'REB', ast: 'AST', stl: 'STL', blk: 'BLK', tov: 'TO', min: 'MIN', pir: 'PIR', gp: 'GP',
  points: 'Points', rebounds: 'Rebounds', assists: 'Assists', steals: 'Steals', blocks: 'Blocks', efficiency: 'Efficiency',
  fg: 'Field goals', threes: '3-pointers', ft: 'Free throws', perGame: 'per game',
  w: 'W', l: 'L', diff: '+/-', rank: 'Rank', record: 'Record', form: 'Form',
  playoff: 'Play-off', playout: 'Play-out', topSix: 'top 6', others: 'the others',
  roster: 'Roster', results: 'Results', schedule: 'Schedule', next: 'Next game', lastGames: 'Last games', seasonStats: 'Season stats', gameLog: 'Game log',
  noBox: 'No box score yet', notPlayed: 'Not played yet', tbd: 'Time to be set',
  history: 'History', records: 'Records', champions: 'Champions', format: 'How the season was played',
  language: 'Language', favorite: 'My club', chooseFav: 'Pick your club', website: 'Website', about: 'About',
  aboutText: 'Tunisia Basket is made for free by fans, to give Tunisian basketball the statistics it deserves.',
  offline: 'Offline — showing the last data', retry: 'Try again', loading: 'Loading…', empty: 'Nothing here yet',
  newRecord: 'New record', equalsRecord: 'Equals the record', previous: 'previous',
  nat1: 'National One', search: 'Search a player', all: 'All',
  mvp: 'MVP', game: 'Game', won: 'won', lost: 'lost', home2: 'home', away: 'away',
  // fantasy
  fMyTeam: 'My team', fTransfers: 'Transfers', fRanking: 'Ranking', fLeagues: 'Leagues', fRules: 'How to play',
  fBudget: 'Budget', fLeft: 'left', fSave: 'Save my team', fSaved: 'Team saved', fCaptain: 'Captain', fVice: 'Vice-captain',
  fDeadline: 'Deadline', fPoints: 'pts', fTotal: 'Total', fGrade: 'Grade', fBest: 'Best possible', fChips: 'Chips',
  triple_captain: 'Triple Captain', bench_boost: 'Bench Boost', wildcard: 'Wildcard', all_star: 'All-Star',
  triple_captainD: 'Your captain scores x3 this matchday', bench_boostD: 'Your 3 bench players score too',
  wildcardD: 'Unlimited free transfers this matchday', all_starD: 'Any squad, no budget, for one matchday — your team comes back after',
  fPick: 'Pick', fG: 'Guards', fF: 'Forwards', fC: 'Centres', fFree: 'free transfers', fHit: 'points hit',
  fCreateLeague: 'Create a league', fJoinLeague: 'Join with a code', fCode: 'Code', fYourName: 'Your name', fTeamName: 'Team name',
  fWelcome: 'Build your dream Pro A team', fWelcomeText: '8 players, 70 of budget, a captain. Score with their real box scores every matchday.',
  fStart: 'Build my team', fDream: 'Team of the matchday', fTest: 'Test mode: play a past matchday', fAutoSub: 'auto-sub',
  fHidden: 'Fantasy is hidden in the store build until it launches.',
} as const;

export type Key = keyof typeof EN;

const FR: Partial<Record<Key, string>> = {
  home: 'Accueil', scores: 'Matchs', standings: 'Classement', players: 'Joueurs', more: 'Plus', fantasy: 'Fantasy',
  hello: 'Bon retour', season: 'Saison', latest: 'Derniers résultats', upcoming: 'À venir', seeAll: 'Tout voir',
  final: 'Terminé', live: 'En direct', today: "Aujourd'hui", matchday: 'Journée', day: 'J', vs: 'contre', at: 'à',
  playerOfRound: 'Joueur de la journée', mvpRace: 'Course au MVP', leaders: 'Meilleurs joueurs', topPerformers: 'Meilleurs joueurs du match',
  boxScore: 'Feuille de match', summary: 'Résumé', comparison: 'Comparaison', quarters: 'Par quart-temps', team: 'Équipe', starters: 'Cinq de départ', bench: 'Banc',
  pts: 'PTS', reb: 'REB', ast: 'PD', stl: 'INT', blk: 'CTR', tov: 'BP', min: 'MIN', pir: 'ÉVAL', gp: 'MJ',
  points: 'Points', rebounds: 'Rebonds', assists: 'Passes décisives', steals: 'Interceptions', blocks: 'Contres', efficiency: 'Évaluation',
  fg: 'Tirs', threes: '3 points', ft: 'Lancers francs', perGame: 'par match',
  w: 'V', l: 'D', diff: '+/-', rank: 'Rang', record: 'Bilan', form: 'Forme',
  playoff: 'Play-off', playout: 'Play-out', topSix: 'top 6', others: 'les autres',
  roster: 'Effectif', results: 'Résultats', schedule: 'Calendrier', next: 'Prochain match', lastGames: 'Derniers matchs', seasonStats: 'Stats de la saison', gameLog: 'Match par match',
  noBox: 'Pas encore de feuille de match', notPlayed: 'Pas encore joué', tbd: 'Horaire à fixer',
  history: 'Historique', records: 'Records', champions: 'Champions', format: 'La formule de la saison',
  language: 'Langue', favorite: 'Mon club', chooseFav: 'Choisis ton club', website: 'Site web', about: 'À propos',
  aboutText: 'Tunisia Basket est fait gratuitement par des passionnés, pour donner au basket tunisien les statistiques qu’il mérite.',
  offline: 'Hors ligne — dernières données', retry: 'Réessayer', loading: 'Chargement…', empty: 'Rien pour l’instant',
  newRecord: 'Nouveau record', equalsRecord: 'Égale le record', previous: 'précédent',
  nat1: 'Nationale 1', search: 'Chercher un joueur', all: 'Tous',
  mvp: 'MVP', game: 'Match', won: 'gagné', lost: 'perdu', home2: 'domicile', away: 'extérieur',
  fMyTeam: 'Mon équipe', fTransfers: 'Transferts', fRanking: 'Classement', fLeagues: 'Ligues', fRules: 'Règles',
  fBudget: 'Budget', fLeft: 'restant', fSave: 'Valider mon équipe', fSaved: 'Équipe enregistrée', fCaptain: 'Capitaine', fVice: 'Vice-capitaine',
  fDeadline: 'Clôture', fPoints: 'pts', fTotal: 'Total', fGrade: 'Note', fBest: 'Meilleur possible', fChips: 'Bonus',
  triple_captain: 'Triple capitaine', bench_boost: 'Banc boosté', wildcard: 'Joker', all_star: 'All-Star',
  triple_captainD: 'Ton capitaine marque x3 cette journée', bench_boostD: 'Tes 3 remplaçants marquent aussi',
  wildcardD: 'Transferts illimités et gratuits cette journée', all_starD: 'N’importe quelle équipe, sans budget, pour une journée — ton équipe revient ensuite',
  fPick: 'Choisir', fG: 'Meneurs/arrières', fF: 'Ailiers', fC: 'Pivots', fFree: 'transferts gratuits', fHit: 'points de pénalité',
  fCreateLeague: 'Créer une ligue', fJoinLeague: 'Rejoindre avec un code', fCode: 'Code', fYourName: 'Ton prénom', fTeamName: 'Nom de l’équipe',
  fWelcome: 'Construis ton équipe de rêve de Pro A', fWelcomeText: '8 joueurs, 70 de budget, un capitaine. Marque des points avec leurs vraies feuilles de match à chaque journée.',
  fStart: 'Créer mon équipe', fDream: 'Équipe type de la journée', fTest: 'Mode test : jouer une journée passée', fAutoSub: 'remplacement auto',
  fHidden: 'Le Fantasy reste caché dans la version publiée jusqu’à son lancement.',
};

export const DICT: Record<Lang, Partial<Record<Key, string>>> = { en: EN, fr: FR };

export const translate = (lang: Lang, k: Key) => DICT[lang][k] ?? EN[k] ?? k;
