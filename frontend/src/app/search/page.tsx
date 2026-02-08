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
import { useTranslation } from '@/i18n/LanguageContext';
import { formatPrice } from '@/lib/formatters';
import type { PropertyWithMetrics, BatchAnalysisResponse, RemovedListing } from '@/lib/types';

export default function SearchPage() {
  const { t, locale } = useTranslation();

  const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
    { value: 'all', label: t('search.filterAll') },
    { value: 'new', label: t('search.filterNew') },
    { value: 'price_drop', label: t('search.filterPriceDrops') },
    { value: 'stale', label: t('search.filterStale') },
    { value: 'delisted', label: t('search.filterRemoved') },
  ];

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
        <h1 className="text-3xl font-bold tracking-tight">{t('search.title')}</h1>
        <p className="text-muted-foreground">
          {t('search.subtitle')}
        </p>
      </div>

      {/* MLS # Lookup */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t('search.mlsPlaceholder')}
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
          {t('search.lookUp')}
        </Button>
        {idLookupMutation.isError && (
          <span className="text-sm text-destructive">
            {idLookupMutation.error instanceof Error
              ? idLookupMutation.error.message
              : t('search.propertyNotFound')}
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
              <span className="font-medium">{t('search.searching')}</span>
            </div>
          </CardContent>
        </Card>
      )}

      {searchMutation.isError && (
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive">{t('search.searchFailed')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {searchMutation.error instanceof Error
                ? searchMutation.error.message
                : t('search.searchError')}
            </p>
          </CardContent>
        </Card>
      )}

      {results && (
        <>
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-4">
              <h2 className="text-xl font-semibold">
                {t('search.propertiesFound', { count: results.count })}
              </h2>
              {results.summary.avg_score && (
                <Badge variant="secondary">
                  {t('search.avgScore', { score: results.summary.avg_score.toFixed(0) })}
                </Badge>
              )}
              {results.summary.avg_cap_rate && (
                <Badge variant="secondary">
                  {t('search.avgCapRate', { rate: results.summary.avg_cap_rate.toFixed(1) })}
                </Badge>
              )}
              {results.summary.positive_cash_flow_count !== undefined && (
                <Badge variant="secondary">
                  {t('search.positiveCashFlow', { count: results.summary.positive_cash_flow_count })}
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
            <CardTitle>{t('search.readyTitle')}</CardTitle>
            <CardDescription>
              {t('search.readyDesc')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
              <li>{t('search.readyTip1')}</li>
              <li>{t('search.readyTip2')}</li>
              <li>{t('search.readyTip3')}</li>
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
                <CardTitle className="text-lg">{t('search.recentlyRemoved')}</CardTitle>
                <Badge variant="secondary">{removedListings.length}</Badge>
              </div>
              <Button variant="ghost" size="sm">
                {showRemoved ? t('common.hide') : t('common.show')}
              </Button>
            </div>
            <CardDescription>
              {t('search.recentlyRemovedDesc')}
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
                          {dom !== null && <span>{t('search.daysOnMarket', { days: dom })}</span>}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-medium">
                          {formatPrice(item.listing.price, locale)}
                        </div>
                        {item.last_seen_at && (
                          <div className="text-xs text-muted-foreground">
                            {t('search.lastSeen', { date: new Date(item.last_seen_at).toLocaleDateString() })}
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
