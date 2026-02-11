'use client';

import { ExternalLink, AlertTriangle, Footprints, Bus, Bike, ChevronLeft, ChevronRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Progress } from '@/components/ui/progress';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { useTranslation } from '@/i18n/LanguageContext';
import { formatPrice, formatNumber } from '@/lib/formatters';
import type { HouseWithScore } from '@/lib/types';
import { useState } from 'react';

interface HouseDetailProps {
  house: HouseWithScore | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function getScoreColor(score: number, max: number): string {
  const pct = (score / max) * 100;
  if (pct >= 70) return 'text-green-600';
  if (pct >= 50) return 'text-yellow-600';
  return 'text-red-600';
}

function getScoreBg(score: number, max: number): string {
  const pct = (score / max) * 100;
  if (pct >= 70) return 'bg-green-500';
  if (pct >= 50) return 'bg-yellow-500';
  return 'bg-red-500';
}

function getBadgeColor(score: number): string {
  if (score >= 70) return 'bg-green-500';
  if (score >= 50) return 'bg-yellow-500';
  return 'bg-red-500';
}

function getWalkScoreColor(score: number | null): string {
  if (score == null) return 'text-muted-foreground';
  if (score >= 70) return 'text-green-600';
  if (score >= 50) return 'text-yellow-600';
  return 'text-red-600';
}

/** Circular progress visualization for pillar scores */
function CircularScore({ value, max, label, colorClass }: { value: number; max: number; label: string; colorClass: string }) {
  const pct = Math.min(100, (value / max) * 100);
  const circumference = 2 * Math.PI * 36; // radius = 36
  const strokeDashoffset = circumference - (pct / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-20 h-20">
        <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
          <circle cx="40" cy="40" r="36" fill="none" stroke="currentColor" strokeWidth="6" className="text-muted" />
          <circle
            cx="40" cy="40" r="36" fill="none" strokeWidth="6"
            stroke="currentColor"
            className={colorClass}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-bold tabular-nums">{value.toFixed(0)}/{max}</span>
        </div>
      </div>
      <span className="text-xs font-medium text-center">{label}</span>
    </div>
  );
}

function SubScoreRow({ label, value, suffix }: { label: string; value: number | null; suffix?: string }) {
  const { t } = useTranslation();
  if (value == null) return (
    <div className="flex justify-between text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-muted-foreground">{t('houses.dataNotAvailable')}</span>
    </div>
  );
  return (
    <div className="flex justify-between text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium tabular-nums">{value.toFixed(1)}{suffix ? ` ${suffix}` : ''}</span>
    </div>
  );
}

function CostRow({ label, value, locale, bold }: { label: string; value: number | null; locale: string; bold?: boolean }) {
  return (
    <div className={`flex justify-between text-sm ${bold ? 'font-semibold' : ''}`}>
      <span className={bold ? '' : 'text-muted-foreground'}>{label}</span>
      <span className="tabular-nums">
        {value != null ? formatPrice(value, locale as 'en' | 'fr') : '-'}
      </span>
    </div>
  );
}

export function HouseDetail({ house, open, onOpenChange }: HouseDetailProps) {
  const { t, locale } = useTranslation();
  const [photoIndex, setPhotoIndex] = useState(0);

  if (!house) return null;

  const { listing, family_metrics: fm } = house;
  const photos = listing.photo_urls ?? [];

  const monthlyTotal =
    (fm.estimated_monthly_mortgage ?? 0) +
    (fm.estimated_monthly_taxes ?? 0) +
    (fm.estimated_annual_energy != null ? fm.estimated_annual_energy / 12 : 0) +
    (fm.estimated_annual_insurance != null ? fm.estimated_annual_insurance / 12 : 0);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-xl md:max-w-2xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="text-left">{listing.address}</SheetTitle>
          <SheetDescription className="text-left">{listing.city}</SheetDescription>
        </SheetHeader>

        <div className="mt-4 space-y-6">
          {/* 1. Header: Photo + Price + Score */}
          <div className="space-y-3">
            {/* Photo gallery */}
            {photos.length > 0 ? (
              <div className="relative rounded-lg overflow-hidden bg-muted h-56">
                <img
                  src={photos[photoIndex]}
                  alt={`${listing.address} - ${photoIndex + 1}`}
                  className="w-full h-full object-cover"
                />
                {photos.length > 1 && (
                  <>
                    <button
                      className="absolute left-2 top-1/2 -translate-y-1/2 bg-black/50 text-white rounded-full p-1 hover:bg-black/70"
                      onClick={() => setPhotoIndex((i) => (i - 1 + photos.length) % photos.length)}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </button>
                    <button
                      className="absolute right-2 top-1/2 -translate-y-1/2 bg-black/50 text-white rounded-full p-1 hover:bg-black/70"
                      onClick={() => setPhotoIndex((i) => (i + 1) % photos.length)}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </button>
                    <div className="absolute bottom-2 left-1/2 -translate-x-1/2 bg-black/50 text-white text-xs px-2 py-0.5 rounded-full">
                      {photoIndex + 1} / {photos.length}
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div className="rounded-lg bg-muted h-32 flex items-center justify-center text-muted-foreground text-sm">
                {t('houses.noPhoto')}
              </div>
            )}

            <div className="flex items-center justify-between">
              <span className="text-2xl font-bold">{formatPrice(listing.price, locale as 'en' | 'fr')}</span>
              <div className={`rounded-full w-14 h-14 flex items-center justify-center text-lg font-bold text-white shadow-lg ${getBadgeColor(fm.family_score)}`}>
                {fm.family_score.toFixed(0)}
              </div>
            </div>
            <p className="text-sm text-muted-foreground">{t('houses.familyScore')}</p>
          </div>

          <Separator />

          {/* 2. Score Breakdown - 3-column grid */}
          <div>
            <h3 className="text-sm font-semibold mb-3">{t('detail.scoreBreakdown')}</h3>
            <div className="grid grid-cols-3 gap-4">
              {/* Livability */}
              <Card>
                <CardContent className="p-3 space-y-2">
                  <CircularScore
                    value={fm.livability_score}
                    max={40}
                    label={t('houses.livability')}
                    colorClass="text-blue-500"
                  />
                  <div className="space-y-1">
                    <SubScoreRow label={t('houses.walkScore')} value={fm.walk_score_pts} />
                    <SubScoreRow label={t('houses.transitScore')} value={fm.transit_score_pts} />
                    <SubScoreRow label={t('houses.safety')} value={fm.safety_pts} />
                    <SubScoreRow label={t('houses.schoolProximity')} value={fm.school_proximity_pts} />
                    <SubScoreRow label={t('houses.parks')} value={fm.parks_pts} />
                  </div>
                </CardContent>
              </Card>

              {/* Value */}
              <Card>
                <CardContent className="p-3 space-y-2">
                  <CircularScore
                    value={fm.value_score}
                    max={35}
                    label={t('houses.value')}
                    colorClass="text-green-500"
                  />
                  <div className="space-y-1">
                    <SubScoreRow label={t('houses.priceVsAssessment')} value={fm.price_vs_assessment_pts} />
                    <SubScoreRow label={t('houses.pricePerSqft')} value={fm.price_per_sqft_pts} />
                    <SubScoreRow label={t('houses.affordability')} value={fm.affordability_pts} />
                    <SubScoreRow label={t('houses.marketTrajectory')} value={fm.market_trajectory_pts} />
                  </div>
                </CardContent>
              </Card>

              {/* Space */}
              <Card>
                <CardContent className="p-3 space-y-2">
                  <CircularScore
                    value={fm.space_score}
                    max={25}
                    label={t('houses.spaceComfort')}
                    colorClass="text-purple-500"
                  />
                  <div className="space-y-1">
                    <SubScoreRow label={t('houses.lotSize')} value={fm.lot_size_pts} />
                    <SubScoreRow label={t('houses.bedrooms')} value={fm.bedroom_pts} />
                    <SubScoreRow label={t('houses.condition')} value={fm.condition_pts} />
                    <SubScoreRow label={t('houses.propertyAge')} value={fm.age_pts} />
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>

          <Separator />

          {/* 3. Cost of Ownership */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{t('houses.costOfOwnership')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <CostRow label={t('houses.monthlyMortgage')} value={fm.estimated_monthly_mortgage} locale={locale} />
              <CostRow label={t('houses.monthlyTaxes')} value={fm.estimated_monthly_taxes} locale={locale} />
              <CostRow
                label={t('houses.annualEnergy')}
                value={fm.estimated_annual_energy != null ? fm.estimated_annual_energy / 12 : null}
                locale={locale}
              />
              <CostRow
                label={t('houses.annualInsurance')}
                value={fm.estimated_annual_insurance != null ? fm.estimated_annual_insurance / 12 : null}
                locale={locale}
              />
              <Separator />
              <CostRow label={t('houses.totalMonthlyCost')} value={monthlyTotal > 0 ? monthlyTotal : null} locale={locale} bold />
              <Separator />
              <CostRow label={t('houses.welcomeTax')} value={fm.welcome_tax} locale={locale} />
              <CostRow label={t('houses.totalCashNeeded')} value={fm.total_cash_needed} locale={locale} bold />
            </CardContent>
          </Card>

          {/* 4. Property Details */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{t('detail.propertyDetails')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-y-2 gap-x-4 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('houses.bedrooms')}</span>
                  <span className="font-medium">{listing.bedrooms}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('common.baths')}</span>
                  <span className="font-medium">{listing.bathrooms}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('common.sqft')}</span>
                  <span className="font-medium">{listing.sqft ? formatNumber(listing.sqft, locale as 'en' | 'fr') : '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('houses.lotSize')}</span>
                  <span className="font-medium">{listing.lot_sqft ? formatNumber(listing.lot_sqft, locale as 'en' | 'fr') : '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('common.built')}</span>
                  <span className="font-medium">{listing.year_built ?? '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('detail.assessment')}</span>
                  <span className="font-medium">{listing.municipal_assessment ? formatPrice(listing.municipal_assessment, locale as 'en' | 'fr') : '-'}</span>
                </div>
                {fm.price_per_sqft != null && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">{t('houses.pricePerSqft')}</span>
                    <span className="font-medium">{formatPrice(fm.price_per_sqft, locale as 'en' | 'fr')}/{t('common.sqft')}</span>
                  </div>
                )}
              </div>

              {/* Walk / Transit / Bike scores */}
              {(listing.walk_score != null || listing.transit_score != null || listing.bike_score != null) && (
                <div className="mt-4 flex gap-4">
                  {listing.walk_score != null && (
                    <div className="flex items-center gap-1.5">
                      <Footprints className="h-4 w-4 text-muted-foreground" />
                      <span className={`text-sm font-medium ${getWalkScoreColor(listing.walk_score)}`}>
                        {listing.walk_score}
                      </span>
                      <span className="text-xs text-muted-foreground">{t('houses.walkScore')}</span>
                    </div>
                  )}
                  {listing.transit_score != null && (
                    <div className="flex items-center gap-1.5">
                      <Bus className="h-4 w-4 text-muted-foreground" />
                      <span className={`text-sm font-medium ${getWalkScoreColor(listing.transit_score)}`}>
                        {listing.transit_score}
                      </span>
                      <span className="text-xs text-muted-foreground">{t('houses.transitScore')}</span>
                    </div>
                  )}
                  {listing.bike_score != null && (
                    <div className="flex items-center gap-1.5">
                      <Bike className="h-4 w-4 text-muted-foreground" />
                      <span className={`text-sm font-medium ${getWalkScoreColor(listing.bike_score)}`}>
                        {listing.bike_score}
                      </span>
                      <span className="text-xs text-muted-foreground">{t('detail.bikeScore')}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Condition */}
              {listing.condition_score != null && (
                <div className="mt-3">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-muted-foreground">{t('houses.condition')}:</span>
                    <span className="font-medium">{listing.condition_score}/10</span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* 5. Risk Flags */}
          {(fm.flood_zone || fm.contaminated_nearby) && (
            <div className="space-y-2">
              {fm.flood_zone && (
                <div className="flex items-center gap-2 rounded-md bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 p-3">
                  <AlertTriangle className="h-4 w-4 text-red-600" />
                  <span className="text-sm text-red-800 dark:text-red-300">{t('houses.floodZoneWarning')}</span>
                </div>
              )}
              {fm.contaminated_nearby && (
                <div className="flex items-center gap-2 rounded-md bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 p-3">
                  <AlertTriangle className="h-4 w-4 text-red-600" />
                  <span className="text-sm text-red-800 dark:text-red-300">{t('houses.contaminatedWarning')}</span>
                </div>
              )}
            </div>
          )}

          {/* Check if all risk data is null (not yet available) */}
          {fm.flood_zone == null && fm.contaminated_nearby == null && (
            <div className="rounded-md bg-muted/50 border p-3">
              <span className="text-sm text-muted-foreground">{t('houses.dataNotAvailable')}</span>
            </div>
          )}

          {/* 6. Action buttons */}
          <div className="flex gap-3">
            <Button asChild className="flex-1">
              <a href={listing.url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="mr-2 h-4 w-4" />
                {t('houses.viewOnCentris')}
              </a>
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
