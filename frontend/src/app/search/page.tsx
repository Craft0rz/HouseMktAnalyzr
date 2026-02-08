'use client';

import { useState, useCallback, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Loader2, Search, Archive } from 'lucide-react';
import { SearchFilters, type SearchFilters as SearchFiltersType } from '@/components/SearchFilters';
import { PropertyTable, type StatusFilter } from '@/components/PropertyTable';
import { PropertyDetail } from '@/components/PropertyDetail';
import { ComparisonBar } from '@/components/ComparisonBar';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { analysisApi, propertiesApi } from '@/lib/api';
import type { PropertyWithMetrics, BatchAnalysisResponse, RemovedListing } from '@/lib/types';

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'new', label: 'New (≤7d)' },
  { value: 'price_drop', label: 'Price Drops' },
  { value: 'stale', label: 'Stale' },
  { value: 'delisted', label: 'Removed' },
];

export default function SearchPage() {
  const [results, setResults] = useState<BatchAnalysisResponse | null>(null);
  const [selectedProperty, setSelectedProperty] = useState<PropertyWithMetrics | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [mlsNumber, setMlsNumber] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [removedListings, setRemovedListings] = useState<RemovedListing[]>([]);
  const [showRemoved, setShowRemoved] = useState(false);

  // Fetch recently removed listings
  useEffect(() => {
    propertiesApi.getRecentlyRemoved()
      .then((res) => setRemovedListings(res.listings))
      .catch(() => {});
  }, []);

  const idLookupMutation = useMutation({
    mutationFn: async (id: string) => {
      const listing = await propertiesApi.getDetails(id.trim());
      const metrics = await analysisApi.analyze(listing);
      return { listing, metrics } as PropertyWithMetrics;
    },
    onSuccess: (property) => {
      setSelectedProperty(property);
      setDetailOpen(true);
    },
  });

  const handleIdLookup = useCallback(() => {
    const id = mlsNumber.trim();
    if (!id) return;
    idLookupMutation.mutate(id);
  }, [mlsNumber, idLookupMutation]);

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

      {/* MLS # Lookup */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Look up by MLS # (e.g. 28574831)"
            value={mlsNumber}
            onChange={(e) => setMlsNumber(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleIdLookup()}
            className="pl-9"
          />
        </div>
        <Button
          onClick={handleIdLookup}
          disabled={!mlsNumber.trim() || idLookupMutation.isPending}
          size="default"
        >
          {idLookupMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : null}
          Look Up
        </Button>
        {idLookupMutation.isError && (
          <span className="text-sm text-destructive">
            {idLookupMutation.error instanceof Error
              ? idLookupMutation.error.message
              : 'Property not found'}
          </span>
        )}
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
          <div className="flex items-center justify-between flex-wrap gap-4">
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
            <div className="flex items-center gap-1">
              {STATUS_FILTERS.map((f) => (
                <Button
                  key={f.value}
                  variant={statusFilter === f.value ? 'default' : 'outline'}
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => setStatusFilter(f.value)}
                >
                  {f.label}
                </Button>
              ))}
            </div>
          </div>

          <PropertyTable
            data={results.results}
            onRowClick={handleRowClick}
            isLoading={searchMutation.isPending}
            statusFilter={statusFilter}
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

      {/* Recently Removed */}
      {removedListings.length > 0 && (
        <Card>
          <CardHeader className="cursor-pointer" onClick={() => setShowRemoved(!showRemoved)}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Archive className="h-5 w-5 text-muted-foreground" />
                <CardTitle className="text-lg">Recently Removed</CardTitle>
                <Badge variant="secondary">{removedListings.length}</Badge>
              </div>
              <Button variant="ghost" size="sm">
                {showRemoved ? 'Hide' : 'Show'}
              </Button>
            </div>
            <CardDescription>
              Listings that went stale or were delisted in the last 7 days
            </CardDescription>
          </CardHeader>
          {showRemoved && (
            <CardContent>
              <div className="space-y-2">
                {removedListings.map((item) => {
                  const dom = item.days_on_market;
                  return (
                    <div
                      key={item.listing.id}
                      className="flex items-center justify-between p-3 rounded-md border hover:bg-muted/50 cursor-pointer"
                      onClick={() => {
                        setSelectedProperty({ listing: item.listing, metrics: {} as PropertyWithMetrics['metrics'] });
                        setDetailOpen(true);
                      }}
                    >
                      <div>
                        <div className="font-medium">{item.listing.address}</div>
                        <div className="text-sm text-muted-foreground flex items-center gap-2">
                          <span>{item.listing.city}</span>
                          <Badge variant="outline" className="text-[9px] px-1 py-0 h-4 border-gray-400/50 text-gray-500">
                            {item.status}
                          </Badge>
                          {dom !== null && <span>{dom}d on market</span>}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-medium">
                          {new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(item.listing.price)}
                        </div>
                        {item.last_seen_at && (
                          <div className="text-xs text-muted-foreground">
                            Last seen {new Date(item.last_seen_at).toLocaleDateString()}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          )}
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
