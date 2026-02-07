'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { SearchFilters, type SearchFilters as SearchFiltersType } from '@/components/SearchFilters';
import { PropertyTable } from '@/components/PropertyTable';
import { PropertyDetail } from '@/components/PropertyDetail';
import { ComparisonBar } from '@/components/ComparisonBar';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { analysisApi, propertiesApi } from '@/lib/api';
import type { PropertyWithMetrics, BatchAnalysisResponse } from '@/lib/types';

export default function SearchPage() {
  const [results, setResults] = useState<BatchAnalysisResponse | null>(null);
  const [selectedProperty, setSelectedProperty] = useState<PropertyWithMetrics | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [loadingStage, setLoadingStage] = useState<'idle' | 'fetching' | 'analyzing'>('idle');
  const [progress, setProgress] = useState(0);
  const [listingsCount, setListingsCount] = useState(0);
  const [isComprehensive, setIsComprehensive] = useState(false);

  // Track actual stage timing for more accurate progress
  const stageStartTimeRef = useRef(0);

  // Animate progress based on stage and expected duration
  useEffect(() => {
    if (loadingStage === 'idle') {
      setProgress(0);
      return;
    }

    const startTime = Date.now();
    stageStartTimeRef.current = startTime;

    // Expected durations (ms) - comprehensive fetching takes much longer
    const expectedFetchDuration = isComprehensive ? 30000 : 8000; // 30s vs 8s
    const expectedAnalyzeDuration = Math.max(3000, listingsCount * 50); // ~50ms per listing

    const maxProgress = loadingStage === 'fetching' ? 60 : 100;
    const baseProgress = loadingStage === 'fetching' ? 0 : 60;
    const expectedDuration = loadingStage === 'fetching' ? expectedFetchDuration : expectedAnalyzeDuration;

    setProgress(baseProgress);

    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      // Use asymptotic curve: progress approaches max but never quite reaches it
      // This gives realistic feeling - fast at first, slows as it approaches completion
      const progressRatio = 1 - Math.exp(-elapsed / (expectedDuration * 0.4));
      const targetProgress = baseProgress + (maxProgress - baseProgress) * progressRatio * 0.95;

      setProgress(Math.min(targetProgress, maxProgress - 2));
    }, 100);

    return () => clearInterval(interval);
  }, [loadingStage, isComprehensive, listingsCount]);

  const searchMutation = useMutation({
    mutationFn: async (filters: SearchFiltersType) => {
      // Stage 1: Fetching properties
      setIsComprehensive(filters.comprehensiveSearch ?? false);
      setListingsCount(0);
      setLoadingStage('fetching');

      let listings;

      if (filters.comprehensiveSearch) {
        // Use AJAX pagination for more comprehensive results
        // Map property types to API format (use ALL_PLEX for multi-family)
        const propertyType = filters.propertyTypes.some(t =>
          ['DUPLEX', 'TRIPLEX', 'QUADPLEX', 'MULTIPLEX'].includes(t)
        ) ? 'ALL_PLEX' : 'HOUSE';

        const allListingsResponse = await propertiesApi.getAllListings({
          region: filters.region,
          property_type: propertyType,
          min_price: filters.minPrice,
          max_price: filters.maxPrice,
          max_pages: filters.maxPages || 10,
          enrich: true,
        });

        // Filter by selected property types on the client side
        listings = allListingsResponse.listings.filter(l =>
          filters.propertyTypes.includes(l.property_type)
        );
      } else {
        // Standard multi-type search
        const searchResponse = await propertiesApi.searchMultiType({
          region: filters.region,
          property_types: filters.propertyTypes.join(','),
          min_price: filters.minPrice,
          max_price: filters.maxPrice,
          enrich: true,
        });
        listings = searchResponse.listings;
      }

      if (listings.length === 0) {
        return { results: [], count: 0, summary: {} } as BatchAnalysisResponse;
      }

      // Stage 2: Analyzing properties
      setListingsCount(listings.length);
      setProgress(60); // Jump to 60% when fetching complete
      setLoadingStage('analyzing');

      const analysisResponse = await analysisApi.analyzeBatch(listings);
      return analysisResponse;
    },
    onSuccess: (data) => {
      setProgress(100);
      setTimeout(() => {
        setLoadingStage('idle');
        setResults(data);
      }, 300);
    },
    onError: () => {
      setLoadingStage('idle');
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

      {/* Loading Progress */}
      {searchMutation.isPending && (
        <Card>
          <CardContent className="py-6">
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
                <span className="font-medium">
                  {loadingStage === 'fetching'
                    ? 'Fetching properties from Centris...'
                    : 'Analyzing investment metrics...'}
                </span>
              </div>
              <Progress value={progress} className="h-2" />
              <p className="text-sm text-muted-foreground">
                {loadingStage === 'fetching'
                  ? isComprehensive
                    ? 'Comprehensive search: fetching multiple pages from Centris...'
                    : 'Searching for properties matching your criteria'
                  : `Analyzing ${listingsCount} properties: calculating scores, cap rates, and cash flow`}
              </p>
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
              <li>Data is fetched from Centris.ca in real-time</li>
              <li>Properties are analyzed with investment metrics</li>
              <li>Results are ranked by investment score</li>
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
