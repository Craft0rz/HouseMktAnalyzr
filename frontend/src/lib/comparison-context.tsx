'use client';

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import type { PropertyWithMetrics } from './types';

interface ComparisonContextType {
  selectedProperties: PropertyWithMetrics[];
  addProperty: (property: PropertyWithMetrics) => void;
  removeProperty: (propertyId: string) => void;
  clearAll: () => void;
  isSelected: (propertyId: string) => boolean;
  canAdd: boolean;
}

const MAX_COMPARISON = 4;

const ComparisonContext = createContext<ComparisonContextType | null>(null);

export function ComparisonProvider({ children }: { children: ReactNode }) {
  const [selectedProperties, setSelectedProperties] = useState<PropertyWithMetrics[]>([]);

  const addProperty = useCallback((property: PropertyWithMetrics) => {
    setSelectedProperties((prev) => {
      if (prev.length >= MAX_COMPARISON) return prev;
      if (prev.some((p) => p.listing.id === property.listing.id)) return prev;
      return [...prev, property];
    });
  }, []);

  const removeProperty = useCallback((propertyId: string) => {
    setSelectedProperties((prev) => prev.filter((p) => p.listing.id !== propertyId));
  }, []);

  const clearAll = useCallback(() => {
    setSelectedProperties([]);
  }, []);

  const isSelected = useCallback(
    (propertyId: string) => selectedProperties.some((p) => p.listing.id === propertyId),
    [selectedProperties]
  );

  const canAdd = selectedProperties.length < MAX_COMPARISON;

  return (
    <ComparisonContext.Provider
      value={{
        selectedProperties,
        addProperty,
        removeProperty,
        clearAll,
        isSelected,
        canAdd,
      }}
    >
      {children}
    </ComparisonContext.Provider>
  );
}

export function useComparison() {
  const context = useContext(ComparisonContext);
  if (!context) {
    throw new Error('useComparison must be used within ComparisonProvider');
  }
  return context;
}
