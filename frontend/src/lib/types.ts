/**
 * TypeScript types matching the FastAPI backend schemas.
 */

export type PropertyType = 'HOUSE' | 'DUPLEX' | 'TRIPLEX' | 'QUADPLEX' | 'MULTIPLEX';

export interface PropertyListing {
  id: string;
  source: string;
  address: string;
  city: string;
  postal_code: string | null;
  price: number;
  property_type: PropertyType;
  bedrooms: number;
  bathrooms: number;
  sqft: number | null;
  lot_sqft: number | null;
  year_built: number | null;
  units: number;
  estimated_rent: number | null;
  gross_revenue: number | null;
  total_expenses: number | null;
  net_income: number | null;
  municipal_assessment: number | null;
  annual_taxes: number | null;
  walk_score: number | null;
  transit_score: number | null;
  bike_score: number | null;
  latitude: number | null;
  longitude: number | null;
  photo_urls: string[];
  condition_score: number | null;
  condition_details: {
    kitchen: number | null;
    bathroom: number | null;
    floors: number | null;
    exterior: number | null;
    renovation_needed: boolean;
    notes: string;
  } | null;
  listing_date: string | null;
  url: string;
  raw_data: Record<string, unknown> | null;
}

export interface RateSensitivity {
  low_rate: number;
  low_cash_flow: number;
  low_mortgage: number;
  base_rate: number;
  base_cash_flow: number;
  base_mortgage: number;
  high_rate: number;
  high_cash_flow: number;
  high_mortgage: number;
}

export interface ComparablePPU {
  median: number;
  avg: number;
  count: number;
  region: string;
  property_type: string;
}

export interface InvestmentMetrics {
  property_id: string;
  purchase_price: number;
  estimated_monthly_rent: number;
  rent_source: 'declared' | 'cmhc_estimate';
  cmhc_estimated_rent: number | null;
  rent_vs_market_pct: number | null;
  gross_rental_yield: number;
  cap_rate: number | null;
  price_per_unit: number;
  price_per_sqft: number | null;
  cash_flow_monthly: number | null;
  score: number;
  score_breakdown: Record<string, number>;
  annual_rent: number;
  is_positive_cash_flow: boolean;
  rate_sensitivity: RateSensitivity | null;
  comparable_ppu: ComparablePPU | null;
}

export interface PropertyWithMetrics {
  listing: PropertyListing;
  metrics: InvestmentMetrics;
}

export interface PropertySearchResponse {
  listings: PropertyListing[];
  count: number;
  region: string;
}

export interface BatchAnalysisResponse {
  results: PropertyWithMetrics[];
  count: number;
  summary: {
    avg_score?: number;
    avg_cap_rate?: number;
    avg_cash_flow?: number;
    positive_cash_flow_count?: number;
    total_analyzed?: number;
    total_found?: number;
    passed_score_filter?: number;
    returned?: number;
    min_score_threshold?: number;
  };
}

export interface QuickMetricsRequest {
  price: number;
  monthly_rent: number;
  units?: number;
  down_payment_pct?: number;
  interest_rate?: number;
  expense_ratio?: number;
}

export interface QuickMetricsResponse {
  gross_yield: number;
  cap_rate: number;
  grm: number;
  noi: number;
  monthly_mortgage: number;
  monthly_cash_flow: number;
  annual_cash_flow: number;
  cash_on_cash_return: number;
  price_per_unit: number;
  total_cash_needed: number;
}

export interface MortgageResponse {
  price: number;
  down_payment: number;
  down_payment_pct: number;
  principal: number;
  interest_rate: number;
  amortization_years: number;
  monthly_payment: number;
  total_cash_needed: number;
}

export interface AlertCriteria {
  id: string;
  name: string;
  enabled: boolean;
  regions: string[];
  property_types: string[];
  min_price: number | null;
  max_price: number | null;
  min_score: number | null;
  min_cap_rate: number | null;
  min_cash_flow: number | null;
  max_price_per_unit: number | null;
  min_yield: number | null;
  notify_email: string | null;
  notify_on_new: boolean;
  notify_on_price_drop: boolean;
  created_at: string;
  updated_at: string;
  last_checked: string | null;
  last_match_count: number;
}

export interface AlertListResponse {
  alerts: AlertCriteria[];
  count: number;
}

export interface CreateAlertRequest {
  name: string;
  regions?: string[];
  property_types?: string[];
  min_price?: number;
  max_price?: number;
  min_score?: number;
  min_cap_rate?: number;
  min_cash_flow?: number;
  max_price_per_unit?: number;
  min_yield?: number;
  notify_email?: string;
  notify_on_new?: boolean;
  notify_on_price_drop?: boolean;
}

// Search parameters
export interface PropertySearchParams {
  region?: string;
  property_types?: string;
  min_price?: number;
  max_price?: number;
  limit?: number;
  enrich?: boolean;
}

// Portfolio types
export type PortfolioStatus = 'owned' | 'watching';

export interface PortfolioItem {
  id: string;
  property_id: string;
  status: PortfolioStatus;
  address: string;
  property_type: string;
  purchase_price: number | null;
  purchase_date: string | null;
  down_payment: number | null;
  mortgage_rate: number | null;
  current_rent: number | null;
  current_expenses: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  // Calculated metrics
  monthly_cash_flow: number | null;
  annual_return: number | null;
  equity: number | null;
}

export interface PortfolioSummary {
  total_owned: number;
  total_watching: number;
  total_invested: number;
  total_equity: number;
  monthly_cash_flow: number;
  annual_cash_flow: number;
  avg_return: number;
}

export interface PortfolioListResponse {
  items: PortfolioItem[];
  count: number;
  summary: PortfolioSummary;
}

export interface CreatePortfolioItemRequest {
  property_id: string;
  status: PortfolioStatus;
  address: string;
  property_type: string;
  purchase_price?: number;
  purchase_date?: string;
  down_payment?: number;
  mortgage_rate?: number;
  current_rent?: number;
  current_expenses?: number;
  notes?: string;
}

export interface UpdatePortfolioItemRequest {
  status?: PortfolioStatus;
  purchase_price?: number;
  purchase_date?: string;
  down_payment?: number;
  mortgage_rate?: number;
  current_rent?: number;
  current_expenses?: number;
  notes?: string;
}

// Market intelligence types
export interface MarketObservation {
  date: string;
  value: number;
}

export interface RateSeriesResponse {
  series_id: string;
  label: string;
  latest_value: number | null;
  latest_date: string | null;
  direction: 'up' | 'down' | 'stable';
  observations: MarketObservation[];
}

export interface MarketRatesResponse {
  mortgage_5yr: RateSeriesResponse | null;
  policy_rate: RateSeriesResponse | null;
  prime_rate: RateSeriesResponse | null;
  cpi: RateSeriesResponse | null;
  last_updated: string | null;
}

export interface MarketSummaryResponse {
  mortgage_rate: number | null;
  policy_rate: number | null;
  prime_rate: number | null;
  cpi: number | null;
  mortgage_direction: 'up' | 'down' | 'stable';
  policy_direction: 'up' | 'down' | 'stable';
}

export interface RentForecast {
  year: number;
  projected_rent: number;
  lower_bound: number;
  upper_bound: number;
}

export interface TalForecast {
  year: number;
  projected_rent: number;
  tal_rate_pct: number;
}

export interface RentTrendResponse {
  zone: string;
  bedroom_type: string;
  current_rent: number | null;
  years: number[];
  rents: number[];
  annual_growth_rate: number | null;
  cagr_5yr: number | null;
  growth_direction: 'accelerating' | 'decelerating' | 'stable';
  forecasts: RentForecast[];
  tal_forecasts: TalForecast[];
  vacancy_rate: number | null;
  vacancy_direction: 'up' | 'down' | 'stable';
}

export interface DemographicProfile {
  municipality: string;
  csd_code: string;
  population: number | null;
  population_2016: number | null;
  pop_change_pct: number | null;
  avg_household_size: number | null;
  total_households: number | null;
  median_household_income: number | null;
  median_after_tax_income: number | null;
  avg_household_income: number | null;
  rent_to_income_ratio: number | null;
}

export interface CrimeStats {
  total_crimes: number;
  violent_crimes: number;
  property_crimes: number;
  year_over_year_change_pct: number | null;
}

export interface PermitStats {
  total_permits: number;
  construction_permits: number;
  transform_permits: number;
  demolition_permits: number;
  total_cost: number;
}

export interface HousingStarts {
  total: number;
  single: number;
  semi: number;
  row: number;
  apartment: number;
}

export interface TaxRateHistoryPoint {
  year: number;
  residential_rate: number;
}

export interface TaxRate {
  residential_rate: number;
  total_tax_rate: number;
  annual_tax_estimate: number | null;
  year: number | null;
  yoy_change_pct: number | null;
  cagr_5yr: number | null;
  history: TaxRateHistoryPoint[];
  city_avg_rate: number | null;
  rank: number | null;
  total_boroughs: number | null;
}

export interface NeighbourhoodResponse {
  borough: string;
  year: number;
  crime: CrimeStats | null;
  permits: PermitStats | null;
  housing_starts: HousingStarts | null;
  tax: TaxRate | null;
  safety_score: number | null;
  gentrification_signal: string | null;
}

// Price history & lifecycle types
export interface PriceChange {
  old_price: number;
  new_price: number;
  change: number;
  change_pct: number;
  recorded_at: string;
}

export interface PriceHistoryResponse {
  property_id: string;
  current_price: number | null;
  original_price: number | null;
  total_change: number;
  total_change_pct: number;
  changes: PriceChange[];
  days_on_market: number | null;
  status: string;
  first_seen_at: string | null;
}

export interface PriceChangeMap {
  [property_id: string]: {
    old_price: number;
    new_price: number;
    change: number;
    change_pct: number;
    recorded_at: string;
  };
}

export interface LifecycleData {
  status: 'active' | 'stale' | 'delisted';
  days_on_market: number | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
}

export interface LifecycleMap {
  [property_id: string]: LifecycleData;
}

export interface PortfolioNotification {
  type: 'price_drop' | 'price_increase' | 'status_change';
  property_id: string;
  address: string;
  old_price?: number;
  new_price?: number;
  change?: number;
  change_pct?: number;
  recorded_at?: string;
  listing_status?: string;
  last_seen_at?: string;
}

// Scraper status types

export interface EnrichmentPhaseProgress {
  total: number;
  done: number;
  failed: number;
  phase: 'pending' | 'running' | 'done';
}

export interface RefreshStatus {
  status: 'pending' | 'running' | 'skipped' | 'done' | 'failed';
}

export interface StepResult {
  region: string;
  type: string;
  count: number;
  duration_sec: number;
  error: string | null;
}

export interface DataWarning {
  source: string;
  message: string;
  action: string;
}

export interface DataQuality {
  total: number;
  avg_score: number;
  high_quality: number;
  low_quality: number;
  flagged: number;
  corrected: number;
}

export interface QualitySnapshot extends DataQuality {
  enrichment_rates?: {
    details: number;
    walk_scores: number;
    photos: number;
    conditions: number;
  };
}

export interface ScraperStatus {
  enabled?: boolean;
  message?: string;
  is_running: boolean;
  last_run_started: string | null;
  last_run_completed: string | null;
  last_run_duration_sec: number | null;
  total_listings_stored: number;
  errors: string[];
  data_warnings?: DataWarning[];
  data_quality?: DataQuality;
  next_run_at: string | null;
  current_phase: string | null;
  current_step: number;
  total_steps: number;
  current_region: string | null;
  current_type: string | null;
  step_results: StepResult[];
  enrichment_progress: {
    details: EnrichmentPhaseProgress;
    walk_scores: EnrichmentPhaseProgress;
    photos: EnrichmentPhaseProgress;
    conditions: EnrichmentPhaseProgress;
  };
  refresh_progress: {
    market: RefreshStatus;
    rent: RefreshStatus;
    demographics: RefreshStatus;
    neighbourhood: RefreshStatus;
  };
}

export interface ScrapeJob {
  id: number;
  started_at: string | null;
  completed_at: string | null;
  status: 'running' | 'completed' | 'failed';
  total_listings: number;
  total_enriched: number;
  errors: string[];
  step_log: StepResult[];
  duration_sec: number | null;
  quality_snapshot: QualitySnapshot | null;
}

export interface ScrapeJobHistoryResponse {
  jobs: ScrapeJob[];
  count: number;
}

export interface DataSourceFreshness {
  last_fetched: string | null;
  age_hours: number | null;
  threshold_hours: number;
  total_active?: number;
}

export interface DataFreshnessResponse {
  market_data: DataSourceFreshness;
  rent_data: DataSourceFreshness;
  demographics: DataSourceFreshness;
  neighbourhood: DataSourceFreshness;
  listings: DataSourceFreshness;
}

// Auth types
export interface User {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  auth_provider: 'local' | 'google';
  role: 'free' | 'pro' | 'admin';
  is_verified: boolean;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse {
  user: User;
  tokens: AuthTokens;
}

export interface RegisterRequest {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
  remember_me?: boolean;
}

// Admin types
export interface AdminUserRow {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  auth_provider: string;
  role: 'free' | 'pro' | 'admin';
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface AdminDashboardStats {
  total_users: number;
  active_users_24h: number;
  total_requests_24h: number;
  total_requests_7d: number;
  avg_response_ms_24h: number | null;
  top_endpoints: { endpoint: string; count: number }[];
  requests_per_day: { day: string; count: number }[];
  users_by_role: { role: string; count: number }[];
  recent_signups: AdminUserRow[];
}

export interface AdminUsersResponse {
  users: AdminUserRow[];
  total: number;
}

export interface AdminRemovedListingRow {
  property_id: string;
  address: string;
  city: string;
  region: string | null;
  property_type: string | null;
  price: number | null;
  status: string;
  days_on_market: number | null;
  last_seen_at: string | null;
}

export interface AdminRemovedListingsStats {
  total_removed_7d: number;
  total_removed_30d: number;
  avg_days_on_market: number | null;
  by_region: { region: string; count: number }[];
  by_property_type: { property_type: string; count: number }[];
  weekly_removals: { week_start: string; count: number }[];
}

export interface AdminRemovedListingsResponse {
  stats: AdminRemovedListingsStats;
  listings: AdminRemovedListingRow[];
  total_count: number;
  page: number;
  page_size: number;
}
