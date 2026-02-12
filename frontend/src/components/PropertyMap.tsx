'use client';

import { useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useTranslation } from '@/i18n/LanguageContext';
import { formatPrice, formatPercent, formatNumber } from '@/lib/formatters';
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

  // Keep a ref to avoid stale closures inside Leaflet Popup content
  const onMarkerClickRef = useRef(onMarkerClick);
  useEffect(() => { onMarkerClickRef.current = onMarkerClick; }, [onMarkerClick]);
  const dataRef = useRef(data);
  useEffect(() => { dataRef.current = data; }, [data]);

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
          const photoUrl = listing.photo_urls?.[0];
          return (
            <Marker
              key={listing.id}
              position={[listing.latitude!, listing.longitude!]}
              icon={getIcon(metrics.score)}
            >
              <Popup>
                <div style={{ minWidth: 240, maxWidth: 280, fontSize: 13, lineHeight: 1.4 }}>
                  {/* Photo */}
                  {photoUrl && (
                    <div style={{ margin: '-1px -1px 8px -1px', borderRadius: '4px 4px 0 0', overflow: 'hidden' }}>
                      <img
                        src={photoUrl}
                        alt={listing.address}
                        style={{ width: '100%', height: 120, objectFit: 'cover', display: 'block' }}
                        loading="lazy"
                      />
                    </div>
                  )}

                  {/* Address + Score badge */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 4 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: 14, lineHeight: 1.3 }}>
                        {listing.address}
                      </div>
                      <div style={{ color: '#888', fontSize: 11, marginTop: 2 }}>
                        {listing.city} · MLS {listing.id}
                      </div>
                    </div>
                    <div
                      style={{
                        flexShrink: 0,
                        width: 36,
                        height: 36,
                        borderRadius: '50%',
                        backgroundColor: getMarkerColor(metrics.score),
                        color: 'white',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 700,
                        fontSize: 13,
                      }}
                    >
                      {metrics.score.toFixed(0)}
                    </div>
                  </div>

                  {/* Price */}
                  <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 6 }}>
                    {formatPrice(listing.price, locale)}
                  </div>

                  {/* Key stats row */}
                  <div style={{ display: 'flex', gap: 10, fontSize: 11, color: '#666', marginBottom: 4 }}>
                    <span>{listing.bedrooms} {t('houses.bedrooms')}</span>
                    <span>{listing.bathrooms} {t('common.baths')}</span>
                    {listing.sqft != null && (
                      <span>{formatNumber(listing.sqft, locale as 'en' | 'fr')} {t('common.sqft')}</span>
                    )}
                  </div>

                  {/* Walk / Transit scores + Cap rate */}
                  <div style={{ display: 'flex', gap: 10, fontSize: 11, color: '#666', flexWrap: 'wrap' }}>
                    {listing.walk_score != null && (
                      <span>Walk {listing.walk_score}</span>
                    )}
                    {listing.transit_score != null && (
                      <span>Transit {listing.transit_score}</span>
                    )}
                    {metrics.cap_rate != null && (
                      <span>Cap {formatPercent(metrics.cap_rate)}</span>
                    )}
                    {listing.lot_sqft != null && (
                      <span>Lot {formatNumber(listing.lot_sqft, locale as 'en' | 'fr')}</span>
                    )}
                  </div>

                  {/* View Details button */}
                  <button
                    style={{
                      marginTop: 8,
                      width: '100%',
                      padding: '6px 0',
                      fontSize: 12,
                      fontWeight: 600,
                      color: '#2563eb',
                      backgroundColor: '#eff6ff',
                      border: '1px solid #bfdbfe',
                      borderRadius: 4,
                      cursor: 'pointer',
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      // Use ref to avoid stale closure
                      const current = dataRef.current.find((p) => p.listing.id === listing.id);
                      onMarkerClickRef.current?.(current ?? property);
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
