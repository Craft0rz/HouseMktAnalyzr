'use client';

import { useState, useCallback, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { useMutation } from '@tanstack/react-query';
import { Loader2, Search, LayoutGrid, Map, BedDouble, Ruler, ExternalLink, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { housesApi } from '@/lib/api';
import { useTranslation } from '@/i18n/LanguageContext';
import { formatPrice, formatNumber } from '@/lib/formatters';
import { HouseDetail } from '@/components/HouseDetail';
import type { HouseWithScore, FamilyBatchResponse, PropertyWithMetrics } from '@/lib/types';

// Lazy-load the map component (same pattern as search page)
const mapImport = () => import('@/components/PropertyMap').then((m) => m.PropertyMap);
const PropertyMap = dynamic(mapImport, {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-[600px] rounded-md border bg-muted/30">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  ),
});
if (typeof window !== 'undefined') mapImport();

type SortOption = 'score' | 'price_asc' | 'price_desc' | 'bedrooms' | 'lot_size';

function getScoreBadgeClasses(score: number): string {
  if (score >= 70) return 'bg-green-500 text-white';
  if (score >= 50) return 'bg-yellow-500 text-white';
  return 'bg-red-500 text-white';
}

function PillarBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 truncate text-muted-foreground">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right tabular-nums font-medium">{value.toFixed(0)}/{max}</span>
    </div>
  );
}

export default function HousesPage() {
  const { t, locale } = useTranslation();

  // Filter state
  const [region, setRegion] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('hmka-region') || 'montreal';
    }
    return 'montreal';
  });
  const [minPrice, setMinPrice] = useState<string>('');
  const [maxPrice, setMaxPrice] = useState<string>('');
  const [minBedrooms, setMinBedrooms] = useState<string>('');
  const [minLotSize, setMinLotSize] = useState<string>('');

  // Results state
  const [results, setResults] = useState<FamilyBatchResponse | null>(null);
  const [sortBy, setSortBy] = useState<SortOption>('score');
  const [viewMode, setViewMode] = useState<'grid' | 'map'>('grid');
  const [selectedHouse, setSelectedHouse] = useState<HouseWithScore | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const REGIONS = [
    { value: 'montreal', label: t('regions.montreal') },
    { value: 'laval', label: t('regions.laval') },
    { value: 'south-shore', label: t('regions.southShore') },
    { value: 'laurentides', label: t('regions.laurentides') },
    { value: 'lanaudiere', label: t('regions.lanaudiere') },
    { value: 'capitale-nationale', label: t('regions.capitaleNationale') },
    { value: 'estrie', label: t('regions.estrie') },
  ];

  const SORT_OPTIONS: { value: SortOption; label: string }[] = [
    { value: 'score', label: t('houses.sortByScore') },
    { value: 'price_asc', label: `${t('houses.sortByPrice')} (asc)` },
    { value: 'price_desc', label: `${t('houses.sortByPrice')} (desc)` },
    { value: 'bedrooms', label: t('houses.sortByBedrooms') },
    { value: 'lot_size', label: t('houses.sortByLotSize') },
  ];

  const searchMutation = useMutation({
    mutationFn: async () => {
      const response = await housesApi.search({
        region,
        min_price: minPrice ? parseInt(minPrice) : undefined,
        max_price: maxPrice ? parseInt(maxPrice) : undefined,
      });
      return response;
    },
    onSuccess: (data) => {
      setResults(data);
    },
  });

  const handleSearch = useCallback(() => {
    searchMutation.mutate();
  }, [searchMutation]);

  // Filter and sort results
  const displayResults = useMemo(() => {
    if (!results) return [];
    let filtered = [...results.results];

    // Client-side filter by bedrooms
    if (minBedrooms) {
      const minBeds = parseInt(minBedrooms);
      filtered = filtered.filter((h) => h.listing.bedrooms >= minBeds);
    }

    // Client-side filter by lot size
    if (minLotSize) {
      const minLot = parseInt(minLotSize);
      filtered = filtered.filter((h) => (h.listing.lot_sqft ?? 0) >= minLot);
    }

    // Sort
    switch (sortBy) {
      case 'score':
        filtered.sort((a, b) => b.family_metrics.family_score - a.family_metrics.family_score);
        break;
      case 'price_asc':
        filtered.sort((a, b) => a.listing.price - b.listing.price);
        break;
      case 'price_desc':
        filtered.sort((a, b) => b.listing.price - a.listing.price);
        break;
      case 'bedrooms':
        filtered.sort((a, b) => b.listing.bedrooms - a.listing.bedrooms);
        break;
      case 'lot_size':
        filtered.sort((a, b) => (b.listing.lot_sqft ?? 0) - (a.listing.lot_sqft ?? 0));
        break;
    }

    return filtered;
  }, [results, sortBy, minBedrooms, minLotSize]);

  // Adapt data for PropertyMap (it expects PropertyWithMetrics[])
  const mapData = useMemo<PropertyWithMetrics[]>(() => {
    return displayResults.map((h) => ({
      listing: h.listing,
      metrics: {
        property_id: h.listing.id,
        purchase_price: h.listing.price,
        estimated_monthly_rent: 0,
        rent_source: 'declared' as const,
        cmhc_estimated_rent: null,
        rent_vs_market_pct: null,
        gross_rental_yield: 0,
        cap_rate: null,
        price_per_unit: h.listing.price,
        price_per_sqft: h.family_metrics.price_per_sqft,
        cash_flow_monthly: null,
        score: h.family_metrics.family_score,
        score_breakdown: h.family_metrics.score_breakdown,
        annual_rent: 0,
        is_positive_cash_flow: false,
        rate_sensitivity: null,
        comparable_ppu: null,
      },
    }));
  }, [displayResults]);

  const handleCardClick = useCallback((house: HouseWithScore) => {
    setSelectedHouse(house);
    setDetailOpen(true);
  }, []);

  const handleMapMarkerClick = useCallback((property: PropertyWithMetrics) => {
    // Find the corresponding HouseWithScore
    const house = displayResults.find((h) => h.listing.id === property.listing.id);
    if (house) {
      setSelectedHouse(house);
      setDetailOpen(true);
    }
  }, [displayResults]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t('houses.title')}</h1>
        <p className="text-muted-foreground">{t('houses.subtitle')}</p>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            {/* Region */}
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('filters.region')}</label>
              <Select value={region} onValueChange={setRegion}>
                <SelectTrigger>
                  <SelectValue placeholder={t('regions.selectRegion')} />
                </SelectTrigger>
                <SelectContent>
                  {REGIONS.map((r) => (
                    <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Min Price */}
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('filters.minPrice')}</label>
              <Input
                type="number"
                step="10000"
                placeholder={t('filters.minPricePlaceholder')}
                value={minPrice}
                onChange={(e) => setMinPrice(e.target.value)}
                min="0"
              />
            </div>

            {/* Max Price */}
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('filters.maxPrice')}</label>
              <Input
                type="number"
                step="10000"
                placeholder={t('filters.maxPricePlaceholder')}
                value={maxPrice}
                onChange={(e) => setMaxPrice(e.target.value)}
                min="0"
              />
            </div>

            {/* Min Bedrooms */}
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('houses.minBedrooms')}</label>
              <Select value={minBedrooms} onValueChange={setMinBedrooms}>
                <SelectTrigger>
                  <SelectValue placeholder="-" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="any">-</SelectItem>
                  <SelectItem value="2">2+</SelectItem>
                  <SelectItem value="3">3+</SelectItem>
                  <SelectItem value="4">4+</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Search Button */}
            <div className="space-y-2">
              <span className="text-sm font-medium invisible block">{t('filters.search')}</span>
              <Button onClick={handleSearch} disabled={searchMutation.isPending} className="w-full">
                <Search className="mr-2 h-4 w-4" />
                {searchMutation.isPending ? t('filters.searching') : t('filters.search')}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

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

      {/* Error */}
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

      {/* Results header */}
      {results && (
        <>
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-4">
              <h2 className="text-xl font-semibold">
                {t('search.propertiesFound', { count: displayResults.length })}
              </h2>
              {results.summary.avg_family_score != null && (
                <Badge variant="secondary">
                  {t('houses.familyScore')}: {results.summary.avg_family_score.toFixed(0)}
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-3">
              {/* Sort */}
              <Select value={sortBy} onValueChange={(v) => setSortBy(v as SortOption)}>
                <SelectTrigger className="w-[180px] h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SORT_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* View mode toggle */}
              <div className="flex items-center gap-1 border-l pl-3">
                <Button
                  variant={viewMode === 'grid' ? 'default' : 'outline'}
                  size="sm"
                  className="h-7 px-2"
                  onClick={() => setViewMode('grid')}
                >
                  <LayoutGrid className="h-4 w-4" />
                  <span className="ml-1 text-xs hidden sm:inline">{t('search.tableView')}</span>
                </Button>
                <Button
                  variant={viewMode === 'map' ? 'default' : 'outline'}
                  size="sm"
                  className="h-7 px-2"
                  onClick={() => setViewMode('map')}
                >
                  <Map className="h-4 w-4" />
                  <span className="ml-1 text-xs hidden sm:inline">{t('search.mapView')}</span>
                </Button>
              </div>
            </div>
          </div>

          {/* Grid or Map */}
          {viewMode === 'grid' ? (
            displayResults.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center">
                  <p className="text-muted-foreground">{t('houses.noResults')}</p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {displayResults.map((house) => (
                  <HouseCard
                    key={house.listing.id}
                    house={house}
                    onClick={() => handleCardClick(house)}
                    t={t}
                    locale={locale}
                  />
                ))}
              </div>
            )
          ) : (
            <PropertyMap
              data={mapData}
              onMarkerClick={handleMapMarkerClick}
            />
          )}
        </>
      )}

      {/* Empty state */}
      {!results && !searchMutation.isPending && (
        <Card>
          <CardHeader>
            <CardTitle>{t('search.readyTitle')}</CardTitle>
            <CardDescription>{t('houses.subtitle')}</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
              <li>{t('search.readyTip1')}</li>
              <li>{t('search.readyTip3')}</li>
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Detail sheet */}
      <HouseDetail
        house={selectedHouse}
        open={detailOpen}
        onOpenChange={setDetailOpen}
      />
    </div>
  );
}

/** Individual house card in the grid */
function HouseCard({
  house,
  onClick,
  t,
  locale,
}: {
  house: HouseWithScore;
  onClick: () => void;
  t: (key: string, params?: Record<string, string | number>) => string;
  locale: string;
}) {
  const { listing, family_metrics: fm } = house;
  const photoUrl = listing.photo_urls?.[0];

  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow overflow-hidden"
      onClick={onClick}
    >
      {/* Photo */}
      <div className="relative h-40 bg-muted">
        {photoUrl ? (
          <img
            src={photoUrl}
            alt={listing.address}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            {t('houses.noPhoto')}
          </div>
        )}
        {/* Family Score Badge */}
        <div
          className={`absolute top-2 right-2 rounded-full w-10 h-10 flex items-center justify-center text-sm font-bold shadow-lg ${getScoreBadgeClasses(fm.family_score)}`}
        >
          {fm.family_score.toFixed(0)}
        </div>
      </div>

      <CardContent className="p-4 space-y-3">
        {/* Address */}
        <div>
          <h3 className="font-semibold text-sm truncate">{listing.address}</h3>
          <p className="text-xs text-muted-foreground">{listing.city}</p>
        </div>

        {/* Price */}
        <div className="text-lg font-bold">{formatPrice(listing.price, locale as 'en' | 'fr')}</div>

        {/* Key stats row */}
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <BedDouble className="h-3.5 w-3.5" />
            {listing.bedrooms}
          </span>
          <span>{listing.bathrooms} {t('common.baths')}</span>
          {listing.sqft && (
            <span>{formatNumber(listing.sqft, locale as 'en' | 'fr')} {t('common.sqft')}</span>
          )}
          {listing.lot_sqft && (
            <span className="flex items-center gap-1">
              <Ruler className="h-3.5 w-3.5" />
              {formatNumber(listing.lot_sqft, locale as 'en' | 'fr')}
            </span>
          )}
        </div>

        {/* Pillar mini-bars */}
        <div className="space-y-1.5">
          <PillarBar label={t('houses.livability')} value={fm.livability_score} max={40} color="bg-blue-500" />
          <PillarBar label={t('houses.value')} value={fm.value_score} max={35} color="bg-green-500" />
          <PillarBar label={t('houses.spaceComfort')} value={fm.space_score} max={25} color="bg-purple-500" />
        </div>

        {/* Monthly cost */}
        {fm.monthly_cost_estimate != null && (
          <div className="text-xs text-muted-foreground pt-1 border-t">
            {t('houses.totalMonthlyCost')}: <span className="font-medium text-foreground">{formatPrice(fm.monthly_cost_estimate, locale as 'en' | 'fr')}{t('common.perMonth')}</span>
          </div>
        )}

        {/* Risk flags */}
        {(fm.flood_zone || fm.contaminated_nearby) && (
          <div className="flex gap-1">
            {fm.flood_zone && (
              <Badge variant="destructive" className="text-[10px] gap-1">
                <AlertTriangle className="h-3 w-3" />
                {t('houses.floodZoneWarning')}
              </Badge>
            )}
            {fm.contaminated_nearby && (
              <Badge variant="destructive" className="text-[10px] gap-1">
                <AlertTriangle className="h-3 w-3" />
                {t('houses.contaminatedWarning')}
              </Badge>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
