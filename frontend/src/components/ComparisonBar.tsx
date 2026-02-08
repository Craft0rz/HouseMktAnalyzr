'use client';

import Link from 'next/link';
import { X, BarChart3 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useComparison } from '@/lib/comparison-context';
import { useTranslation } from '@/i18n/LanguageContext';

export function ComparisonBar() {
  const { selectedProperties, removeProperty, clearAll } = useComparison();
  const { t } = useTranslation();

  if (selectedProperties.length === 0) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-background border-t p-4 shadow-lg z-40">
      <div className="container flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 flex-1 overflow-x-auto">
          <span className="text-sm font-medium whitespace-nowrap">
            {t('comparison.compareCount', { count: selectedProperties.length })}
          </span>
          <div className="flex gap-2">
            {selectedProperties.map((property) => (
              <Badge
                key={property.listing.id}
                variant="secondary"
                className="flex items-center gap-1 whitespace-nowrap"
              >
                <span className="max-w-[150px] truncate">
                  {property.listing.address}
                </span>
                <button
                  onClick={() => removeProperty(property.listing.id)}
                  className="ml-1 hover:text-destructive"
                  title={t('comparison.removeFromComparison', { address: property.listing.address })}
                  aria-label={t('comparison.removeFromComparison', { address: property.listing.address })}
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={clearAll}
            title={t('comparison.clearAll')}
          >
            {t('comparison.clear')}
          </Button>
          <Button asChild size="sm" disabled={selectedProperties.length < 2}>
            <Link href="/compare">
              <BarChart3 className="mr-2 h-4 w-4" />
              {t('comparison.compare')}
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
