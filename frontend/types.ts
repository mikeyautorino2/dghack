export interface Game {
  game_id: string;
  sport: 'NBA' | 'NFL';
  game_date: string;
  away_team: string;
  home_team: string;
  away_team_id?: number;
  home_team_id?: number;
}

export interface PricePoint {
  timestamp: number;
  away_price: number; // 0-1
  home_price: number; // 0-1
}

export interface MarketMetadata {
  market_open_ts: number;
  market_close_ts: number;
  game_start_ts: number;
}

export interface SimilarGame {
  game_id: string;
  date: string;
  home_team: string;
  away_team: string;
  similarity: number; // 0-100
  mapping: 'direct' | 'flipped';
  current_home_corresponds_to: 'home' | 'away';
  current_away_corresponds_to: 'home' | 'away';
  price_history: PricePoint[];
  market_metadata: MarketMetadata | null;
}

export interface GameAnalysisResponse {
  target_game: Game & {
    sport: string;
    date: string;
  };
  similar_games: SimilarGame[];
}

export interface ActiveMarket extends Game {
  game_start_ts: number;
  polymarket_away_price?: number;
  polymarket_home_price?: number;
}
