'use client';

import { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useTranslation } from '@/i18n/LanguageContext';
import { formatPrice, formatPercent } from '@/lib/formatters';
import type { PropertyWithMetrics, LifecycleMap, PriceChangeMap } from '@/lib/types';

interface PropertyMapProps {
  data: PropertyWithMetrics[];
  onMarkerClick?: (property: PropertyWithMetrics) => void;
  lifecycle?: LifecycleMap;
  priceChanges?: PriceChangeMap;
}

const MONTREAL_CENTER: [number, number] = [45.5017, -73.5673];
const DEFAULT_ZOOM = 10;

// Pre-create one icon per color bucket (cached, not per-marker)
const ICON_GREEN = L.divIcon({
  className: '',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
  popupAnchor: [0, -14],
  html: '<div style="width:24px;height:24px;border-radius:50%;background:#22c55e;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);"></div>',
});
const ICON_YELLOW = L.divIcon({
  className: '',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
  popupAnchor: [0, -14],
  html: '<div style="width:24px;height:24px;border-radius:50%;background:#eab308;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);"></div>',
});
const ICON_RED = L.divIcon({
  className: '',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
  popupAnchor: [0, -14],
  html: '<div style="width:24px;height:24px;border-radius:50%;background:#ef4444;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);"></div>',
});

function getIcon(score: number): L.DivIcon {
  if (score >= 70) return ICON_GREEN;
  if (score >= 50) return ICON_YELLOW;
  return ICON_RED;
}

function getMarkerColor(score: number): string {
  if (score >= 70) return '#22c55e';
  if (score >= 50) return '#eab308';
  return '#ef4444';
}

/** Inner component that adjusts bounds when markers change */
function FitBounds({ positions }: { positions: [number, number][] }) {
  const map = useMap();

  useEffect(() => {
    if (positions.length === 0) return;
    if (positions.length === 1) {
      map.setView(positions[0], 14);
      return;
    }
    const bounds = L.latLngBounds(positions.map(([lat, lng]) => [lat, lng]));
    map.fitBounds(bounds, { padding: [40, 40] });
  }, [map, positions]);

  return null;
}

export function PropertyMap({ data, onMarkerClick }: PropertyMapProps) {
  const { t, locale } = useTranslation();

  const geocodedProperties = useMemo(
    () => data.filter((p) => p.listing.latitude != null && p.listing.longitude != null),
    [data],
  );

  const positions = useMemo<[number, number][]>(
    () => geocodedProperties.map((p) => [p.listing.latitude!, p.listing.longitude!]),
    [geocodedProperties],
  );

  if (geocodedProperties.length === 0) {
    return (
      <div className="flex items-center justify-center h-[600px] rounded-md border bg-muted/30">
        <p className="text-muted-foreground">{t('search.noGeocodedListings')}</p>
      </div>
    );
  }

  return (
    <div className="h-[600px] rounded-md border overflow-hidden">
      <MapContainer
        center={MONTREAL_CENTER}
        zoom={DEFAULT_ZOOM}
        className="h-full w-full"
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds positions={positions} />
        {geocodedProperties.map((property) => {
          const { listing, metrics } = property;
          return (
            <Marker
              key={listing.id}
              position={[listing.latitude!, listing.longitude!]}
              icon={getIcon(metrics.score)}
            >
              <Popup>
                <div className="min-w-[200px] max-w-[260px] text-sm">
                  <div className="font-semibold text-base leading-tight mb-1">
                    {listing.address}
                  </div>
                  <div className="text-muted-foreground text-xs mb-2">{listing.city}</div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium">{formatPrice(listing.price, locale)}</span>
                    <span
                      className="inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium text-white"
                      style={{ backgroundColor: getMarkerColor(metrics.score) }}
                    >
                      {metrics.score.toFixed(0)}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground space-y-0.5">
                    {metrics.cap_rate != null && (
                      <div>Cap rate: {formatPercent(metrics.cap_rate)}</div>
                    )}
                    <div>{t('propertyTypes.' + listing.property_type)}</div>
                  </div>
                  <button
                    className="mt-2 w-full text-center text-xs font-medium text-primary hover:underline cursor-pointer bg-transparent border-0 p-0"
                    onClick={(e) => {
                      e.stopPropagation();
                      onMarkerClick?.(property);
                    }}
                  >
                    {t('search.viewDetails')}
                  </button>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}
