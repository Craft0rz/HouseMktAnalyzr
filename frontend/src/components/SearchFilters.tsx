'use client';

import { useState, useEffect } from 'react';
import { Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent } from '@/components/ui/card';
import { useTranslation } from '@/i18n/LanguageContext';

export interface SearchFiltersProps {
  onSearch: (filters: SearchFilters) => void;
  isLoading?: boolean;
}

export interface SearchFilters {
  region: string;
  propertyTypes: string[];
  minPrice?: number;
  maxPrice?: number;
}

export function SearchFilters({ onSearch, isLoading }: SearchFiltersProps) {
  const { t } = useTranslation();

  const REGIONS = [
    { value: 'montreal', label: t('regions.montreal') },
    { value: 'laval', label: t('regions.laval') },
    { value: 'south-shore', label: t('regions.southShore') },
    { value: 'laurentides', label: t('regions.laurentides') },
    { value: 'lanaudiere', label: t('regions.lanaudiere') },
    { value: 'capitale-nationale', label: t('regions.capitaleNationale') },
    { value: 'estrie', label: t('regions.estrie') },
  ];

  const PROPERTY_TYPES = [
    { value: 'DUPLEX', label: t('propertyTypes.DUPLEX') },
    { value: 'TRIPLEX', label: t('propertyTypes.TRIPLEX') },
    { value: 'QUADPLEX', label: t('propertyTypes.QUADPLEX') },
    { value: 'MULTIPLEX', label: t('propertyTypes.MULTIPLEX') },
    { value: 'HOUSE', label: t('propertyTypes.HOUSE') },
  ];

  const [region, setRegion] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('hmka-region') || 'montreal';
    }
    return 'montreal';
  });
  const [propertyTypes, setPropertyTypes] = useState<string[]>(['DUPLEX', 'TRIPLEX', 'QUADPLEX']);
  const [minPrice, setMinPrice] = useState<string>('');
  const [maxPrice, setMaxPrice] = useState<string>('');

  useEffect(() => {
    localStorage.setItem('hmka-region', region);
  }, [region]);

  const handleSearch = () => {
    onSearch({
      region,
      propertyTypes,
      minPrice: minPrice ? parseInt(minPrice) : undefined,
      maxPrice: maxPrice ? parseInt(maxPrice) : undefined,
    });
  };

  const togglePropertyType = (type: string) => {
    setPropertyTypes((prev) =>
      prev.includes(type)
        ? prev.filter((t) => t !== type)
        : [...prev, type]
    );
  };

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Region */}
            <div className="space-y-2">
              <label htmlFor="search-region" className="text-sm font-medium">{t('filters.region')}</label>
              <Select value={region} onValueChange={setRegion}>
                <SelectTrigger id="search-region">
                  <SelectValue placeholder={t('regions.selectRegion')} />
                </SelectTrigger>
                <SelectContent>
                  {REGIONS.map((r) => (
                    <SelectItem key={r.value} value={r.value}>
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Min Price */}
            <div className="space-y-2">
              <label htmlFor="search-min-price" className="text-sm font-medium">{t('filters.minPrice')}</label>
              <Input
                id="search-min-price"
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
              <label htmlFor="search-max-price" className="text-sm font-medium">{t('filters.maxPrice')}</label>
              <Input
                id="search-max-price"
                type="number"
                step="10000"
                placeholder={t('filters.maxPricePlaceholder')}
                value={maxPrice}
                onChange={(e) => setMaxPrice(e.target.value)}
                min="0"
              />
            </div>

            {/* Search Button */}
            <div className="space-y-2">
              <span className="text-sm font-medium invisible block">{t('filters.search')}</span>
              <Button onClick={handleSearch} disabled={isLoading} className="w-full">
                <Search className="mr-2 h-4 w-4" />
                {isLoading ? t('filters.searching') : t('filters.search')}
              </Button>
            </div>
          </div>

          {/* Property Types */}
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">{t('filters.propertyTypes')}</legend>
            <div className="flex flex-wrap gap-2" role="group" aria-label={t('filters.propertyTypeFilters')}>
              {PROPERTY_TYPES.map((type) => (
                <Button
                  key={type.value}
                  variant={propertyTypes.includes(type.value) ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => togglePropertyType(type.value)}
                  aria-pressed={propertyTypes.includes(type.value)}
                >
                  {type.label}
                </Button>
              ))}
            </div>
          </fieldset>
        </div>
      </CardContent>
    </Card>
  );
}
