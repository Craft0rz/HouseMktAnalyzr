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
  municipal_assessment: number | null;
  annual_taxes: number | null;
  walk_score: number | null;
  transit_score: number | null;
  bike_score: number | null;
  latitude: number | null;
  longitude: number | null;
  listing_date: string | null;
  url: string;
  raw_data: Record<string, unknown> | null;
}

export interface InvestmentMetrics {
  property_id: string;
  purchase_price: number;
  estimated_monthly_rent: number;
  gross_rental_yield: number;
  cap_rate: number | null;
  price_per_unit: number;
  price_per_sqft: number | null;
  cash_flow_monthly: number | null;
  score: number;
  score_breakdown: Record<string, number>;
  annual_rent: number;
  is_positive_cash_flow: boolean;
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
