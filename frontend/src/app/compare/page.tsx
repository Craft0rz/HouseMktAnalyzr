'use client';

import Link from 'next/link';
import { BarChart3, X, ExternalLink, ArrowLeft } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { useComparison } from '@/lib/comparison-context';
import { ScoreRadar } from '@/components/charts';
import type { PropertyWithMetrics } from '@/lib/types';

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

const getCashFlowColor = (cf: number | null | undefined) => {
  if (cf == null) return '';
  return cf >= 0 ? 'text-green-600' : 'text-red-600';
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

// Helper to find best/worst values for highlighting
function getBestValue(
  properties: PropertyWithMetrics[],
  getValue: (p: PropertyWithMetrics) => number | null | undefined,
  higherIsBetter = true
) {
  const values = properties.map(getValue).filter((v) => v != null) as number[];
  if (values.length === 0) return null;
  return higherIsBetter ? Math.max(...values) : Math.min(...values);
}

interface CompareRowProps {
  label: string;
  properties: PropertyWithMetrics[];
  getValue: (p: PropertyWithMetrics) => string | number | boolean | null | undefined;
  format?: (value: unknown) => string;
  getBest?: (properties: PropertyWithMetrics[]) => number | null;
  getNumericValue?: (p: PropertyWithMetrics) => number | null | undefined;
  colorFn?: (value: unknown) => string;
}

function CompareRow({
  label,
  properties,
  getValue,
  format = (v) => String(v ?? '-'),
  getBest,
  getNumericValue,
  colorFn,
}: CompareRowProps) {
  const bestValue = getBest ? getBest(properties) : null;

  return (
    <div className="grid gap-4" style={{ gridTemplateColumns: `200px repeat(${properties.length}, 1fr)` }}>
      <div className="text-sm text-muted-foreground py-2">{label}</div>
      {properties.map((p) => {
        const value = getValue(p);
        const numValue = getNumericValue ? getNumericValue(p) : null;
        const isBest = bestValue !== null && numValue === bestValue;
        const colorClass = colorFn ? colorFn(value) : '';

        return (
          <div
            key={p.listing.id}
            className={`text-sm py-2 font-medium ${colorClass} ${isBest ? 'bg-green-50 dark:bg-green-950 px-2 rounded' : ''}`}
          >
            {format(value)}
            {isBest && <Badge variant="outline" className="ml-2 text-xs">Best</Badge>}
          </div>
        );
      })}
    </div>
  );
}

export default function ComparePage() {
  const { selectedProperties, removeProperty, clearAll } = useComparison();

  if (selectedProperties.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Compare Properties</h1>
          <p className="text-muted-foreground">
            Compare investment metrics side-by-side for multiple properties.
          </p>
        </div>

        <Card>
          <CardHeader>
            <BarChart3 className="h-10 w-10 text-muted-foreground" />
            <CardTitle className="mt-4">No Properties Selected</CardTitle>
          </CardHeader>
          <CardContent>
            <CardDescription className="mb-4">
              Go to the Search page and click the + button on properties you want to compare.
              You can select up to 4 properties.
            </CardDescription>
            <Button asChild>
              <Link href="/search">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Go to Search
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Compare Properties</h1>
          <p className="text-muted-foreground">
            Comparing {selectedProperties.length} properties side-by-side
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={clearAll}>
            Clear All
          </Button>
          <Button asChild variant="outline">
            <Link href="/search">
              Add More
            </Link>
          </Button>
        </div>
      </div>

      {/* Property Headers */}
      <div className="grid gap-4" style={{ gridTemplateColumns: `200px repeat(${selectedProperties.length}, 1fr)` }}>
        <div />
        {selectedProperties.map((p) => (
          <Card key={p.listing.id} className="relative">
            <Button
              variant="ghost"
              size="sm"
              className="absolute top-2 right-2 h-6 w-6 p-0"
              onClick={() => removeProperty(p.listing.id)}
            >
              <X className="h-4 w-4" />
            </Button>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Badge variant="outline">
                  {getPropertyTypeLabel(p.listing.property_type)}
                </Badge>
              </div>
              <CardTitle className="text-lg truncate pr-8">{p.listing.address}</CardTitle>
              <CardDescription>{p.listing.city}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{formatPrice(p.listing.price)}</div>
              <div className={`text-3xl font-bold mt-2 ${getScoreColor(p.metrics.score)}`}>
                {p.metrics.score.toFixed(0)}
                <span className="text-sm font-normal text-muted-foreground ml-1">score</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Property Details */}
      <Card>
        <CardHeader>
          <CardTitle>Property Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <CompareRow
            label="Units"
            properties={selectedProperties}
            getValue={(p) => p.listing.units}
          />
          <CompareRow
            label="Bedrooms"
            properties={selectedProperties}
            getValue={(p) => p.listing.bedrooms}
          />
          <CompareRow
            label="Bathrooms"
            properties={selectedProperties}
            getValue={(p) => p.listing.bathrooms}
          />
          <CompareRow
            label="Square Feet"
            properties={selectedProperties}
            getValue={(p) => p.listing.sqft}
            format={(v) => (v ? `${Number(v).toLocaleString()} sqft` : '-')}
          />
          <CompareRow
            label="Year Built"
            properties={selectedProperties}
            getValue={(p) => p.listing.year_built}
          />
        </CardContent>
      </Card>

      {/* Financial Metrics */}
      <Card>
        <CardHeader>
          <CardTitle>Financial Metrics</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <CompareRow
            label="Price per Unit"
            properties={selectedProperties}
            getValue={(p) => p.metrics.price_per_unit}
            format={(v) => formatPrice(v as number)}
            getBest={(props) => getBestValue(props, (p) => p.metrics.price_per_unit, false)}
            getNumericValue={(p) => p.metrics.price_per_unit}
          />
          <CompareRow
            label="Est. Monthly Rent"
            properties={selectedProperties}
            getValue={(p) => p.metrics.estimated_monthly_rent}
            format={(v) => formatPrice(v as number)}
            getBest={(props) => getBestValue(props, (p) => p.metrics.estimated_monthly_rent, true)}
            getNumericValue={(p) => p.metrics.estimated_monthly_rent}
          />
          <Separator className="my-2" />
          <CompareRow
            label="Cap Rate"
            properties={selectedProperties}
            getValue={(p) => p.metrics.cap_rate}
            format={(v) => formatPercent(v as number | null)}
            getBest={(props) => getBestValue(props, (p) => p.metrics.cap_rate, true)}
            getNumericValue={(p) => p.metrics.cap_rate}
          />
          <CompareRow
            label="Gross Yield"
            properties={selectedProperties}
            getValue={(p) => p.metrics.gross_rental_yield}
            format={(v) => formatPercent(v as number | null)}
            getBest={(props) => getBestValue(props, (p) => p.metrics.gross_rental_yield, true)}
            getNumericValue={(p) => p.metrics.gross_rental_yield}
          />
          <Separator className="my-2" />
          <CompareRow
            label="Monthly Cash Flow"
            properties={selectedProperties}
            getValue={(p) => p.metrics.cash_flow_monthly}
            format={(v) => (v != null ? formatPrice(v as number) : '-')}
            getBest={(props) => getBestValue(props, (p) => p.metrics.cash_flow_monthly, true)}
            getNumericValue={(p) => p.metrics.cash_flow_monthly}
            colorFn={(v) => getCashFlowColor(v as number | null)}
          />
          <CompareRow
            label="Cash Flow Status"
            properties={selectedProperties}
            getValue={(p) => p.metrics.is_positive_cash_flow}
            format={(v) => (
              v ? '✓ Positive' : '✗ Negative'
            )}
            colorFn={(v) => (v ? 'text-green-600' : 'text-red-600')}
          />
        </CardContent>
      </Card>

      {/* Score Breakdown - Visual */}
      <Card>
        <CardHeader>
          <CardTitle>Score Breakdown</CardTitle>
          <CardDescription>Visual comparison of score components</CardDescription>
        </CardHeader>
        <CardContent>
          <div
            className="grid gap-4"
            style={{ gridTemplateColumns: `repeat(${selectedProperties.length}, 1fr)` }}
          >
            {selectedProperties.map((p) => (
              <div key={p.listing.id} className="text-center">
                <p className="text-sm font-medium mb-2 truncate">
                  {p.listing.address.split(',')[0]}
                </p>
                <ScoreRadar scoreBreakdown={p.metrics.score_breakdown} />
                <p className={`text-2xl font-bold mt-2 ${getScoreColor(p.metrics.score)}`}>
                  {p.metrics.score.toFixed(0)}
                </p>
              </div>
            ))}
          </div>
          <Separator className="my-4" />
          {Object.keys(selectedProperties[0]?.metrics.score_breakdown || {}).map((key) => (
            <CompareRow
              key={key}
              label={key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
              properties={selectedProperties}
              getValue={(p) => p.metrics.score_breakdown[key]}
              format={(v) => `${(v as number).toFixed(1)} pts`}
              getBest={(props) => getBestValue(props, (p) => p.metrics.score_breakdown[key], true)}
              getNumericValue={(p) => p.metrics.score_breakdown[key]}
            />
          ))}
          <Separator className="my-2" />
          <CompareRow
            label="Total Score"
            properties={selectedProperties}
            getValue={(p) => p.metrics.score}
            format={(v) => `${(v as number).toFixed(0)}`}
            getBest={(props) => getBestValue(props, (p) => p.metrics.score, true)}
            getNumericValue={(p) => p.metrics.score}
            colorFn={(v) => getScoreColor(v as number)}
          />
        </CardContent>
      </Card>

      {/* Links */}
      <div className="grid gap-4" style={{ gridTemplateColumns: `200px repeat(${selectedProperties.length}, 1fr)` }}>
        <div />
        {selectedProperties.map((p) => (
          <Button key={p.listing.id} asChild variant="outline">
            <a href={p.listing.url} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="mr-2 h-4 w-4" />
              View on Centris
            </a>
          </Button>
        ))}
      </div>
    </div>
  );
}
