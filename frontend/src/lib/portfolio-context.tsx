'use client';

import { createContext, useContext, useCallback, useMemo, type ReactNode } from 'react';
import { toast } from 'sonner';
import { usePortfolio, useAddToPortfolio, useRemoveFromPortfolio } from '@/hooks/useProperties';
import { useTranslation } from '@/i18n/LanguageContext';
import type { PropertyWithMetrics } from './types';

interface PortfolioContextType {
  isInPortfolio: (propertyId: string) => boolean;
  addToWatchList: (property: PropertyWithMetrics) => void;
  removeFromWatchList: (propertyId: string, address?: string) => void;
  portfolioCount: number;
  isLoading: boolean;
}

const PortfolioContext = createContext<PortfolioContextType | null>(null);

export function PortfolioProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const { data, isLoading } = usePortfolio();
  const addMutation = useAddToPortfolio();
  const removeMutation = useRemoveFromPortfolio();

  // Map property_id -> portfolio item id
  const propertyIdMap = useMemo(() => {
    const map = new Map<string, string>();
    if (data?.items) {
      for (const item of data.items) {
        map.set(item.property_id, item.id);
      }
    }
    return map;
  }, [data?.items]);

  const isInPortfolio = useCallback(
    (propertyId: string) => propertyIdMap.has(propertyId),
    [propertyIdMap]
  );

  const addToWatchList = useCallback(
    (property: PropertyWithMetrics) => {
      if (propertyIdMap.has(property.listing.id)) return;
      const address = property.listing.address;
      addMutation.mutate(
        {
          property_id: property.listing.id,
          status: 'watching',
          address,
          property_type: property.listing.property_type,
          purchase_price: property.listing.price,
          current_rent: property.listing.estimated_rent || property.metrics.estimated_monthly_rent || undefined,
        },
        {
          onSuccess: () => toast.success(t('portfolio.addedSuccess', { address })),
          onError: () => toast.error(t('portfolio.addFailed')),
        }
      );
    },
    [propertyIdMap, addMutation, t]
  );

  const removeFromWatchList = useCallback(
    (propertyId: string, address?: string) => {
      const itemId = propertyIdMap.get(propertyId);
      if (!itemId) return;
      removeMutation.mutate(itemId, {
        onSuccess: () => toast.success(t('portfolio.removedSuccess', { address: address || '' })),
        onError: () => toast.error(t('portfolio.removeFailed')),
      });
    },
    [propertyIdMap, removeMutation, t]
  );

  const portfolioCount = data?.count ?? 0;

  return (
    <PortfolioContext.Provider
      value={{
        isInPortfolio,
        addToWatchList,
        removeFromWatchList,
        portfolioCount,
        isLoading,
      }}
    >
      {children}
    </PortfolioContext.Provider>
  );
}

export function usePortfolioContext() {
  const context = useContext(PortfolioContext);
  if (!context) {
    throw new Error('usePortfolioContext must be used within PortfolioProvider');
  }
  return context;
}
