'use client';

import { ExternalLink, MapPin, Home, DollarSign, TrendingUp, Calculator } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import type { PropertyWithMetrics } from '@/lib/types';

interface PropertyDetailProps {
  property: PropertyWithMetrics | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const formatPrice = (price: number) => {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    maximumFractionDigits: 0,
  }).format(price);
};

const formatPercent = (value: number | null | undefined) => {
  if (value == null) return '-';
  return `${value.toFixed(2)}%`;
};

const getScoreColor = (score: number) => {
  if (score >= 70) return 'text-green-600';
  if (score >= 50) return 'text-yellow-600';
  return 'text-red-600';
};

const getPropertyTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    DUPLEX: 'Duplex',
    TRIPLEX: 'Triplex',
    QUADPLEX: 'Quadplex',
    MULTIPLEX: '5+ Units',
    HOUSE: 'House',
  };
  return labels[type] || type;
};

export function PropertyDetail({ property, open, onOpenChange }: PropertyDetailProps) {
  if (!property) return null;

  const { listing, metrics } = property;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <MapPin className="h-5 w-5" />
            {listing.address}
          </SheetTitle>
          <SheetDescription>
            {listing.city}
            {listing.postal_code && ` • ${listing.postal_code}`}
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* Score and Price */}
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-muted-foreground">Investment Score</div>
              <div className={`text-4xl font-bold ${getScoreColor(metrics.score)}`}>
                {metrics.score.toFixed(0)}
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm text-muted-foreground">Asking Price</div>
              <div className="text-3xl font-bold">{formatPrice(listing.price)}</div>
            </div>
          </div>

          <Separator />

          {/* Property Details */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Home className="h-4 w-4" />
                Property Details
              </CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-muted-foreground">Type</div>
                <div className="font-medium">
                  <Badge variant="outline">
                    {getPropertyTypeLabel(listing.property_type)}
                  </Badge>
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">Units</div>
                <div className="font-medium">{listing.units}</div>
              </div>
              <div>
                <div className="text-muted-foreground">Bedrooms</div>
                <div className="font-medium">{listing.bedrooms}</div>
              </div>
              <div>
                <div className="text-muted-foreground">Bathrooms</div>
                <div className="font-medium">{listing.bathrooms}</div>
              </div>
              {listing.sqft && (
                <div>
                  <div className="text-muted-foreground">Living Area</div>
                  <div className="font-medium">{listing.sqft.toLocaleString()} sqft</div>
                </div>
              )}
              {listing.year_built && (
                <div>
                  <div className="text-muted-foreground">Year Built</div>
                  <div className="font-medium">{listing.year_built}</div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Financial Details */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <DollarSign className="h-4 w-4" />
                Financial Details
              </CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-muted-foreground">Price per Unit</div>
                <div className="font-medium">{formatPrice(metrics.price_per_unit)}</div>
              </div>
              {metrics.price_per_sqft && (
                <div>
                  <div className="text-muted-foreground">Price per sqft</div>
                  <div className="font-medium">${metrics.price_per_sqft.toFixed(0)}</div>
                </div>
              )}
              <div>
                <div className="text-muted-foreground">Est. Monthly Rent</div>
                <div className="font-medium">{formatPrice(metrics.estimated_monthly_rent)}</div>
              </div>
              <div>
                <div className="text-muted-foreground">Annual Rent</div>
                <div className="font-medium">{formatPrice(metrics.annual_rent)}</div>
              </div>
              {listing.annual_taxes && (
                <div>
                  <div className="text-muted-foreground">Annual Taxes</div>
                  <div className="font-medium">{formatPrice(listing.annual_taxes)}</div>
                </div>
              )}
              {listing.municipal_assessment && (
                <div>
                  <div className="text-muted-foreground">Assessment</div>
                  <div className="font-medium">{formatPrice(listing.municipal_assessment)}</div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Investment Metrics */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <TrendingUp className="h-4 w-4" />
                Investment Metrics
              </CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-muted-foreground">Cap Rate</div>
                <div className="font-medium">{formatPercent(metrics.cap_rate)}</div>
              </div>
              <div>
                <div className="text-muted-foreground">Gross Yield</div>
                <div className="font-medium">{formatPercent(metrics.gross_rental_yield)}</div>
              </div>
              <div>
                <div className="text-muted-foreground">Monthly Cash Flow</div>
                <div className={`font-medium ${metrics.cash_flow_monthly && metrics.cash_flow_monthly > 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {metrics.cash_flow_monthly != null
                    ? `${metrics.cash_flow_monthly >= 0 ? '' : '-'}${formatPrice(Math.abs(metrics.cash_flow_monthly))}`
                    : '-'}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">Cash Flow Status</div>
                <div className="font-medium">
                  <Badge variant={metrics.is_positive_cash_flow ? 'default' : 'destructive'}>
                    {metrics.is_positive_cash_flow ? 'Positive' : 'Negative'}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Score Breakdown */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Calculator className="h-4 w-4" />
                Score Breakdown
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {Object.entries(metrics.score_breakdown).map(([key, value]) => (
                <div key={key} className="flex justify-between">
                  <div className="text-muted-foreground capitalize">
                    {key.replace(/_/g, ' ')}
                  </div>
                  <div className="font-medium">{value.toFixed(1)} pts</div>
                </div>
              ))}
              <Separator className="my-2" />
              <div className="flex justify-between font-medium">
                <div>Total Score</div>
                <div className={getScoreColor(metrics.score)}>{metrics.score.toFixed(1)}</div>
              </div>
            </CardContent>
          </Card>

          {/* Actions */}
          <div className="flex gap-2">
            <Button asChild className="flex-1">
              <a href={listing.url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="mr-2 h-4 w-4" />
                View on Centris
              </a>
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
