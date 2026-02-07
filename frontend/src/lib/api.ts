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
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(response.status, error.detail || `HTTP ${response.status}`);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
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
};

// Health check
export const healthApi = {
  check: (): Promise<{ status: string }> => {
    return fetchApi('/health');
  },
};

export { ApiError };
