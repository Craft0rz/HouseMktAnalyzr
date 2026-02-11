/**
 * API client for the HouseMktAnalyzr FastAPI backend.
 */

import type {
  PropertySearchParams,
  PropertySearchResponse,
  PropertyListing,
  InvestmentMetrics,
  BatchAnalysisResponse,
  QuickMetricsRequest,
  QuickMetricsResponse,
  MortgageResponse,
  AlertListResponse,
  AlertCriteria,
  CreateAlertRequest,
  PortfolioListResponse,
  PortfolioItem,
  CreatePortfolioItemRequest,
  UpdatePortfolioItemRequest,
  PortfolioStatus,
  MarketRatesResponse,
  MarketSummaryResponse,
  RentTrendResponse,
  DemographicProfile,
  NeighbourhoodResponse,
  PriceHistoryResponse,
  PriceChangeMap,
  LifecycleMap,
  PortfolioNotification,
  FamilyHomeMetrics,
  FamilyBatchResponse,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const TOKEN_KEY = 'housemkt_access_token';
const REFRESH_KEY = 'housemkt_refresh_token';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

let refreshPromise: Promise<boolean> | null = null;

async function attemptTokenRefresh(): Promise<boolean> {
  // Deduplicate concurrent refresh attempts
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const refreshToken = typeof window !== 'undefined'
      ? localStorage.getItem(REFRESH_KEY)
      : null;
    if (!refreshToken) return false;
    try {
      const response = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_KEY);
        return false;
      }
      const tokens = await response.json();
      localStorage.setItem(TOKEN_KEY, tokens.access_token);
      localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
      return true;
    } catch {
      return false;
    }
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {},
  timeoutMs = 60_000,
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const token = getStoredToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string>),
  };

  try {
    let response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers,
    });

    // On 401 for non-auth endpoints, try refreshing the token
    if (response.status === 401 && !endpoint.startsWith('/api/auth/')) {
      const refreshed = await attemptTokenRefresh();
      if (refreshed) {
        const newToken = getStoredToken();
        response = await fetch(url, {
          ...options,
          signal: controller.signal,
          headers: {
            ...headers,
            ...(newToken ? { Authorization: `Bearer ${newToken}` } : {}),
          },
        });
      }
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new ApiError(response.status, error.detail || `HTTP ${response.status}`);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError(408, 'Request timed out');
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

// Property endpoints
export const propertiesApi = {
  search: (params: PropertySearchParams = {}): Promise<PropertySearchResponse> => {
    const searchParams = new URLSearchParams();
    if (params.region) searchParams.set('region', params.region);
    if (params.property_types) searchParams.set('property_types', params.property_types);
    if (params.min_price) searchParams.set('min_price', String(params.min_price));
    if (params.max_price) searchParams.set('max_price', String(params.max_price));
    if (params.limit) searchParams.set('limit', String(params.limit));
    if (params.enrich !== undefined) searchParams.set('enrich', String(params.enrich));

    return fetchApi(`/api/properties/search?${searchParams}`);
  },

  searchMultiType: (params: PropertySearchParams = {}): Promise<PropertySearchResponse> => {
    const searchParams = new URLSearchParams();
    if (params.region) searchParams.set('region', params.region);
    if (params.property_types) searchParams.set('property_types', params.property_types);
    if (params.min_price) searchParams.set('min_price', String(params.min_price));
    if (params.max_price) searchParams.set('max_price', String(params.max_price));
    if (params.enrich !== undefined) searchParams.set('enrich', String(params.enrich));

    return fetchApi(`/api/properties/multi-type?${searchParams}`);
  },

  getDetails: (listingId: string): Promise<PropertyListing> => {
    return fetchApi(`/api/properties/${encodeURIComponent(listingId)}`);
  },

  getPriceHistory: (listingId: string): Promise<PriceHistoryResponse> => {
    return fetchApi(`/api/properties/${encodeURIComponent(listingId)}/price-history`);
  },

  getRecentPriceChanges: (): Promise<{ changes: PriceChangeMap }> => {
    return fetchApi('/api/properties/price-changes');
  },

  getLifecycle: (): Promise<{ listings: LifecycleMap }> => {
    return fetchApi('/api/properties/lifecycle');
  },

  getAllListings: (params: {
    region?: string;
    property_type?: string;
    min_price?: number;
    max_price?: number;
    max_pages?: number;
    enrich?: boolean;
  } = {}): Promise<{
    listings: PropertyListing[];
    count: number;
    region: string;
    pages_fetched: number;
  }> => {
    const searchParams = new URLSearchParams();
    if (params.region) searchParams.set('region', params.region);
    if (params.property_type) searchParams.set('property_type', params.property_type);
    if (params.min_price) searchParams.set('min_price', String(params.min_price));
    if (params.max_price) searchParams.set('max_price', String(params.max_price));
    if (params.max_pages) searchParams.set('max_pages', String(params.max_pages));
    if (params.enrich !== undefined) searchParams.set('enrich', String(params.enrich));

    return fetchApi(`/api/properties/all-listings?${searchParams}`);
  },
};

// Analysis endpoints
export const analysisApi = {
  analyze: (listing: PropertyListing, options?: {
    down_payment_pct?: number;
    interest_rate?: number;
    expense_ratio?: number;
  }): Promise<InvestmentMetrics> => {
    return fetchApi('/api/analysis/analyze', {
      method: 'POST',
      body: JSON.stringify({
        listing,
        ...options,
      }),
    });
  },

  analyzeBatch: (listings: PropertyListing[], options?: {
    down_payment_pct?: number;
    interest_rate?: number;
    expense_ratio?: number;
  }): Promise<BatchAnalysisResponse> => {
    return fetchApi('/api/analysis/analyze-batch', {
      method: 'POST',
      body: JSON.stringify({
        listings,
        ...options,
      }),
    });
  },

  quickCalc: (params: QuickMetricsRequest): Promise<QuickMetricsResponse> => {
    return fetchApi('/api/analysis/quick-calc', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  mortgage: (params: {
    price: number;
    down_payment_pct?: number;
    interest_rate?: number;
    amortization_years?: number;
  }): Promise<MortgageResponse> => {
    const searchParams = new URLSearchParams();
    searchParams.set('price', String(params.price));
    if (params.down_payment_pct) searchParams.set('down_payment_pct', String(params.down_payment_pct));
    if (params.interest_rate) searchParams.set('interest_rate', String(params.interest_rate));
    if (params.amortization_years) searchParams.set('amortization_years', String(params.amortization_years));

    return fetchApi(`/api/analysis/mortgage?${searchParams}`);
  },

  topOpportunities: (params?: {
    region?: string;
    property_types?: string;
    min_price?: number;
    max_price?: number;
    min_score?: number;
    limit?: number;
  }): Promise<BatchAnalysisResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.region) searchParams.set('region', params.region);
    if (params?.property_types) searchParams.set('property_types', params.property_types);
    if (params?.min_price) searchParams.set('min_price', String(params.min_price));
    if (params?.max_price) searchParams.set('max_price', String(params.max_price));
    if (params?.min_score) searchParams.set('min_score', String(params.min_score));
    if (params?.limit) searchParams.set('limit', String(params.limit));

    return fetchApi(`/api/analysis/top-opportunities?${searchParams}`);
  },
};

// Alerts endpoints
export const alertsApi = {
  list: (enabledOnly = false): Promise<AlertListResponse> => {
    const params = enabledOnly ? '?enabled_only=true' : '';
    return fetchApi(`/api/alerts${params}`);
  },

  get: (alertId: string): Promise<AlertCriteria> => {
    return fetchApi(`/api/alerts/${encodeURIComponent(alertId)}`);
  },

  create: (data: CreateAlertRequest): Promise<AlertCriteria> => {
    return fetchApi('/api/alerts', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  update: (alertId: string, data: Partial<CreateAlertRequest> & { enabled?: boolean }): Promise<AlertCriteria> => {
    return fetchApi(`/api/alerts/${encodeURIComponent(alertId)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  delete: (alertId: string): Promise<void> => {
    return fetchApi(`/api/alerts/${encodeURIComponent(alertId)}`, {
      method: 'DELETE',
    });
  },

  toggle: (alertId: string): Promise<AlertCriteria> => {
    return fetchApi(`/api/alerts/${encodeURIComponent(alertId)}/toggle`, {
      method: 'POST',
    });
  },
};

// Portfolio endpoints
export const portfolioApi = {
  list: (status?: PortfolioStatus): Promise<PortfolioListResponse> => {
    const params = status ? `?status=${status}` : '';
    return fetchApi(`/api/portfolio${params}`);
  },

  get: (itemId: string): Promise<PortfolioItem> => {
    return fetchApi(`/api/portfolio/${encodeURIComponent(itemId)}`);
  },

  create: (data: CreatePortfolioItemRequest): Promise<PortfolioItem> => {
    return fetchApi('/api/portfolio', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  update: (itemId: string, data: UpdatePortfolioItemRequest): Promise<PortfolioItem> => {
    return fetchApi(`/api/portfolio/${encodeURIComponent(itemId)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  delete: (itemId: string): Promise<void> => {
    return fetchApi(`/api/portfolio/${encodeURIComponent(itemId)}`, {
      method: 'DELETE',
    });
  },

  toggleStatus: (itemId: string): Promise<PortfolioItem> => {
    return fetchApi(`/api/portfolio/${encodeURIComponent(itemId)}/toggle-status`, {
      method: 'POST',
    });
  },

  getUpdates: (): Promise<{ notifications: PortfolioNotification[]; count: number }> => {
    return fetchApi('/api/portfolio/notifications/updates');
  },
};

// Market intelligence endpoints
export const marketApi = {
  rates: (lookbackMonths = 12): Promise<MarketRatesResponse> => {
    return fetchApi(`/api/market/rates?lookback_months=${lookbackMonths}`);
  },

  summary: (): Promise<MarketSummaryResponse> => {
    return fetchApi('/api/market/summary');
  },

  rentTrend: (zone: string, bedrooms = 2): Promise<RentTrendResponse> => {
    return fetchApi(`/api/market/rents?zone=${encodeURIComponent(zone)}&bedrooms=${bedrooms}`);
  },

  rentZones: (): Promise<{ zones: string[] }> => {
    return fetchApi('/api/market/rents/zones');
  },

  demographics: (city: string, monthlyRent?: number): Promise<DemographicProfile> => {
    const params = new URLSearchParams({ city });
    if (monthlyRent) params.set('monthly_rent', String(monthlyRent));
    return fetchApi(`/api/market/demographics?${params}`);
  },

  neighbourhood: (borough: string, assessment?: number, postalCode?: string): Promise<NeighbourhoodResponse> => {
    const params = new URLSearchParams({ borough });
    if (assessment) params.set('assessment', String(assessment));
    if (postalCode) params.set('postal_code', postalCode);
    return fetchApi(`/api/market/neighbourhood?${params}`);
  },
};

// Houses (family scoring) endpoints
export const housesApi = {
  scoreHouse: async (listing: PropertyListing): Promise<FamilyHomeMetrics> => {
    return fetchApi('/api/analysis/family-score', {
      method: 'POST',
      body: JSON.stringify({ listing }),
    });
  },

  scoreBatch: async (listings: PropertyListing[]): Promise<FamilyBatchResponse> => {
    return fetchApi('/api/analysis/family-score-batch', {
      method: 'POST',
      body: JSON.stringify({ listings }),
    });
  },

  search: async (params: PropertySearchParams): Promise<FamilyBatchResponse> => {
    // Step 1: Fetch HOUSE listings via top-opportunities
    // Use min_score=0 so investment scoring doesn't filter out family homes,
    // and a higher limit since family scoring has its own sort.
    const searchParams = new URLSearchParams();
    searchParams.set('property_types', 'HOUSE');
    searchParams.set('min_score', '0');
    searchParams.set('limit', '200');
    if (params.region) searchParams.set('region', params.region);
    if (params.min_price) searchParams.set('min_price', String(params.min_price));
    if (params.max_price) searchParams.set('max_price', String(params.max_price));

    const topResponse = await fetchApi<import('./types').BatchAnalysisResponse>(
      `/api/analysis/top-opportunities?${searchParams}`,
    );

    const listings = topResponse.results.map((r) => r.listing);

    if (listings.length === 0) {
      return { results: [], count: 0, summary: {} };
    }

    // Step 2: Score the listings with family scoring
    const familyResponse = await fetchApi<FamilyBatchResponse>(
      '/api/analysis/family-score-batch',
      {
        method: 'POST',
        body: JSON.stringify({ listings }),
      },
    );

    return familyResponse;
  },
};

// Health check
export const healthApi = {
  check: (): Promise<{ status: string }> => {
    return fetchApi('/health');
  },
};

// Scraper status endpoints
export const scraperApi = {
  status: (): Promise<import('./types').ScraperStatus> => {
    return fetchApi('/api/scraper/status');
  },

  history: (limit = 20): Promise<import('./types').ScrapeJobHistoryResponse> => {
    return fetchApi(`/api/scraper/history?limit=${limit}`);
  },

  freshness: (): Promise<import('./types').DataFreshnessResponse> => {
    return fetchApi('/api/scraper/freshness');
  },

  trigger: (): Promise<{ status: string; message: string }> => {
    return fetchApi('/api/scraper/trigger', { method: 'POST' });
  },

  stats: (): Promise<{
    groups: Array<{
      region: string;
      property_type: string;
      count: number;
      oldest: string | null;
      newest: string | null;
    }>;
    total: number;
  }> => {
    return fetchApi('/api/scraper/stats');
  },
};

// Auth endpoints
export const authApi = {
  register: (data: import('./types').RegisterRequest): Promise<import('./types').AuthResponse> => {
    return fetchApi('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  login: (data: import('./types').LoginRequest): Promise<import('./types').AuthResponse> => {
    return fetchApi('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  googleAuth: (idToken: string, rememberMe?: boolean): Promise<import('./types').AuthResponse> => {
    return fetchApi('/api/auth/google', {
      method: 'POST',
      body: JSON.stringify({ id_token: idToken, remember_me: rememberMe ?? false }),
    });
  },

  logout: (): Promise<void> => {
    return fetchApi('/api/auth/logout', { method: 'POST' });
  },

  me: (): Promise<import('./types').User> => {
    return fetchApi('/api/auth/me');
  },
};

// Admin endpoints
export const adminApi = {
  stats: (): Promise<import('./types').AdminDashboardStats> => {
    return fetchApi('/api/admin/stats');
  },

  users: (limit = 50, offset = 0): Promise<import('./types').AdminUsersResponse> => {
    return fetchApi(`/api/admin/users?limit=${limit}&offset=${offset}`);
  },

  updateRole: (userId: string, role: string): Promise<{ status: string }> => {
    return fetchApi(`/api/admin/users/${encodeURIComponent(userId)}/role?role=${encodeURIComponent(role)}`, {
      method: 'PATCH',
    });
  },

  toggleActive: (userId: string, isActive: boolean): Promise<{ status: string }> => {
    return fetchApi(`/api/admin/users/${encodeURIComponent(userId)}/active?is_active=${isActive}`, {
      method: 'PATCH',
    });
  },

  removedListings: (page = 0, pageSize = 50, region?: string): Promise<import('./types').AdminRemovedListingsResponse> => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (region) params.set('region', region);
    return fetchApi(`/api/admin/removed-listings?${params}`);
  },

  triggerScrape: (): Promise<{ status: string; message: string }> => {
    return fetchApi('/api/scraper/trigger', { method: 'POST' });
  },

  revalidateListings: (): Promise<{ status: string; cleared: number }> => {
    return fetchApi('/api/scraper/revalidate', { method: 'POST' });
  },

  revalidateGeocoding: (): Promise<{ status: string; message: string; total_queued: number }> => {
    return fetchApi('/api/admin/revalidate-geocoding', { method: 'POST' });
  },

  checkAlerts: (): Promise<{ alerts_checked: number; total_new_matches: number; notifications_sent: number }> => {
    return fetchApi('/api/alerts/check-now', { method: 'POST' });
  },
};

export { ApiError, TOKEN_KEY, REFRESH_KEY, attemptTokenRefresh };
