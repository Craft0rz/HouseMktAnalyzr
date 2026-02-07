'use client';

import { useState } from 'react';
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

const REGIONS = [
  { value: 'montreal', label: 'Montreal Island' },
  { value: 'laval', label: 'Laval' },
  { value: 'longueuil', label: 'Longueuil' },
  { value: 'south-shore', label: 'South Shore' },
  { value: 'north-shore', label: 'North Shore' },
  { value: 'laurentides', label: 'Laurentides' },
  { value: 'lanaudiere', label: 'Lanaudière' },
];

const PROPERTY_TYPES = [
  { value: 'DUPLEX', label: 'Duplex' },
  { value: 'TRIPLEX', label: 'Triplex' },
  { value: 'QUADPLEX', label: 'Quadplex' },
  { value: 'MULTIPLEX', label: 'Multiplex (5+)' },
  { value: 'HOUSE', label: 'House' },
];

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
  const [region, setRegion] = useState('montreal');
  const [propertyTypes, setPropertyTypes] = useState<string[]>(['DUPLEX', 'TRIPLEX', 'QUADPLEX']);
  const [minPrice, setMinPrice] = useState<string>('');
  const [maxPrice, setMaxPrice] = useState<string>('');

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
              <label className="text-sm font-medium">Region</label>
              <Select value={region} onValueChange={setRegion}>
                <SelectTrigger>
                  <SelectValue placeholder="Select region" />
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
              <label className="text-sm font-medium">Min Price</label>
              <Input
                type="number"
                placeholder="e.g. 400000"
                value={minPrice}
                onChange={(e) => setMinPrice(e.target.value)}
              />
            </div>

            {/* Max Price */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Max Price</label>
              <Input
                type="number"
                placeholder="e.g. 800000"
                value={maxPrice}
                onChange={(e) => setMaxPrice(e.target.value)}
              />
            </div>

            {/* Search Button */}
            <div className="space-y-2">
              <label className="text-sm font-medium">&nbsp;</label>
              <Button onClick={handleSearch} disabled={isLoading} className="w-full">
                <Search className="mr-2 h-4 w-4" />
                {isLoading ? 'Searching...' : 'Search'}
              </Button>
            </div>
          </div>

          {/* Property Types */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Property Types</label>
            <div className="flex flex-wrap gap-2">
              {PROPERTY_TYPES.map((type) => (
                <Button
                  key={type.value}
                  variant={propertyTypes.includes(type.value) ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => togglePropertyType(type.value)}
                >
                  {type.label}
                </Button>
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
