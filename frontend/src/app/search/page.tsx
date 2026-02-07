'use client';

import { useState, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { SearchFilters, type SearchFilters as SearchFiltersType } from '@/components/SearchFilters';
import { PropertyTable } from '@/components/PropertyTable';
import { PropertyDetail } from '@/components/PropertyDetail';
import { ComparisonBar } from '@/components/ComparisonBar';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { analysisApi, propertiesApi } from '@/lib/api';
import type { PropertyWithMetrics, BatchAnalysisResponse } from '@/lib/types';

export default function SearchPage() {
  const [results, setResults] = useState<BatchAnalysisResponse | null>(null);
  const [selectedProperty, setSelectedProperty] = useState<PropertyWithMetrics | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const searchMutation = useMutation({
    mutationFn: async (filters: SearchFiltersType) => {
      const searchResponse = await propertiesApi.searchMultiType({
        region: filters.region,
        property_types: filters.propertyTypes.join(','),
        min_price: filters.minPrice,
        max_price: filters.maxPrice,
      });
      const listings = searchResponse.listings;

      if (listings.length === 0) {
        return { results: [], count: 0, summary: {} } as BatchAnalysisResponse;
      }

      const analysisResponse = await analysisApi.analyzeBatch(listings);
      return analysisResponse;
    },
    onSuccess: (data) => {
      setResults(data);
    },
  });

  const handleSearch = useCallback((filters: SearchFiltersType) => {
    searchMutation.mutate(filters);
  }, [searchMutation]);

  const handleRowClick = useCallback((property: PropertyWithMetrics) => {
    setSelectedProperty(property);
    setDetailOpen(true);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Property Search</h1>
        <p className="text-muted-foreground">
          Search for investment properties across Greater Montreal
        </p>
      </div>

      <SearchFilters onSearch={handleSearch} isLoading={searchMutation.isPending} />

      {/* Loading */}
      {searchMutation.isPending && (
        <Card>
          <CardContent className="py-6">
            <div className="flex items-center gap-3">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              <span className="font-medium">Searching and analyzing properties...</span>
            </div>
          </CardContent>
        </Card>
      )}

      {searchMutation.isError && (
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive">Search Failed</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {searchMutation.error instanceof Error
                ? searchMutation.error.message
                : 'An error occurred while searching. Make sure the backend is running.'}
            </p>
          </CardContent>
        </Card>
      )}

      {results && (
        <>
          <div className="flex items-center gap-4">
            <h2 className="text-xl font-semibold">
              {results.count} Properties Found
            </h2>
            {results.summary.avg_score && (
              <Badge variant="secondary">
                Avg Score: {results.summary.avg_score.toFixed(0)}
              </Badge>
            )}
            {results.summary.avg_cap_rate && (
              <Badge variant="secondary">
                Avg Cap Rate: {results.summary.avg_cap_rate.toFixed(1)}%
              </Badge>
            )}
            {results.summary.positive_cash_flow_count !== undefined && (
              <Badge variant="secondary">
                {results.summary.positive_cash_flow_count} Positive Cash Flow
              </Badge>
            )}
          </div>

          <PropertyTable
            data={results.results}
            onRowClick={handleRowClick}
            isLoading={searchMutation.isPending}
          />
        </>
      )}

      {!results && !searchMutation.isPending && (
        <Card>
          <CardHeader>
            <CardTitle>Ready to Search</CardTitle>
            <CardDescription>
              Configure your search filters above and click Search to find investment properties.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
              <li>Properties are pre-loaded from Centris.ca and updated every 4 hours</li>
              <li>Results are analyzed with investment metrics and ranked by score</li>
              <li>Click any row to see full property details</li>
            </ul>
          </CardContent>
        </Card>
      )}

      <PropertyDetail
        property={selectedProperty}
        open={detailOpen}
        onOpenChange={setDetailOpen}
      />

      <ComparisonBar />
    </div>
  );
}
