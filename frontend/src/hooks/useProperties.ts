'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { propertiesApi, analysisApi, alertsApi, portfolioApi } from '@/lib/api';
import type {
  PropertySearchParams,
  PropertyListing,
  CreateAlertRequest,
  QuickMetricsRequest,
  CreatePortfolioItemRequest,
  UpdatePortfolioItemRequest,
  PortfolioStatus,
} from '@/lib/types';

// Property search hooks
export function usePropertySearch(params: PropertySearchParams, enabled = true) {
  return useQuery({
    queryKey: ['properties', 'search', params],
    queryFn: () => propertiesApi.search(params),
    enabled,
  });
}

export function useMultiTypeSearch(params: PropertySearchParams, enabled = true) {
  return useQuery({
    queryKey: ['properties', 'multi-type', params],
    queryFn: () => propertiesApi.searchMultiType(params),
    enabled,
  });
}

export function usePropertyDetails(listingId: string, enabled = true) {
  return useQuery({
    queryKey: ['properties', 'details', listingId],
    queryFn: () => propertiesApi.getDetails(listingId),
    enabled: enabled && !!listingId,
  });
}

export interface AllListingsParams {
  region?: string;
  property_type?: string;
  min_price?: number;
  max_price?: number;
  max_pages?: number;
  enrich?: boolean;
}

export function useAllListings(params: AllListingsParams, enabled = true) {
  return useQuery({
    queryKey: ['properties', 'all-listings', params],
    queryFn: () => propertiesApi.getAllListings(params),
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes - these searches take time
  });
}

// Analysis hooks
export function useAnalyze(listing: PropertyListing | null, options?: {
  down_payment_pct?: number;
  interest_rate?: number;
  expense_ratio?: number;
}) {
  return useQuery({
    queryKey: ['analysis', 'analyze', listing?.id, options],
    queryFn: () => analysisApi.analyze(listing!, options),
    enabled: !!listing,
  });
}

export function useTopOpportunities(params?: {
  region?: string;
  property_types?: string;
  min_price?: number;
  max_price?: number;
  min_score?: number;
  limit?: number;
}, enabled = true) {
  return useQuery({
    queryKey: ['analysis', 'top-opportunities', params],
    queryFn: () => analysisApi.topOpportunities(params),
    enabled,
  });
}

export function useQuickCalc(params: QuickMetricsRequest | null) {
  return useQuery({
    queryKey: ['analysis', 'quick-calc', params],
    queryFn: () => analysisApi.quickCalc(params!),
    enabled: !!params,
  });
}

export function useMortgage(params: {
  price: number;
  down_payment_pct?: number;
  interest_rate?: number;
  amortization_years?: number;
} | null) {
  return useQuery({
    queryKey: ['analysis', 'mortgage', params],
    queryFn: () => analysisApi.mortgage(params!),
    enabled: !!params,
  });
}

// Alerts hooks
export function useAlerts(enabledOnly = false) {
  return useQuery({
    queryKey: ['alerts', { enabledOnly }],
    queryFn: () => alertsApi.list(enabledOnly),
  });
}

export function useAlert(alertId: string) {
  return useQuery({
    queryKey: ['alerts', alertId],
    queryFn: () => alertsApi.get(alertId),
    enabled: !!alertId,
  });
}

export function useCreateAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateAlertRequest) => alertsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });
}

export function useUpdateAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ alertId, data }: { alertId: string; data: Partial<CreateAlertRequest> & { enabled?: boolean } }) =>
      alertsApi.update(alertId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });
}

export function useDeleteAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (alertId: string) => alertsApi.delete(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });
}

export function useToggleAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (alertId: string) => alertsApi.toggle(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });
}

// Portfolio hooks
export function usePortfolio(status?: PortfolioStatus) {
  return useQuery({
    queryKey: ['portfolio', { status }],
    queryFn: () => portfolioApi.list(status),
  });
}

export function usePortfolioItem(itemId: string) {
  return useQuery({
    queryKey: ['portfolio', itemId],
    queryFn: () => portfolioApi.get(itemId),
    enabled: !!itemId,
  });
}

export function useAddToPortfolio() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreatePortfolioItemRequest) => portfolioApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
    },
  });
}

export function useUpdatePortfolioItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ itemId, data }: { itemId: string; data: UpdatePortfolioItemRequest }) =>
      portfolioApi.update(itemId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
    },
  });
}

export function useRemoveFromPortfolio() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (itemId: string) => portfolioApi.delete(itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
    },
  });
}

export function useTogglePortfolioStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (itemId: string) => portfolioApi.toggleStatus(itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
    },
  });
}
