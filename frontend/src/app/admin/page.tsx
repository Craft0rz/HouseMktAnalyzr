'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Users, Activity, Clock, BarChart3, Shield, Ban, Check, Archive, MapPin, Calendar } from 'lucide-react';
import { toast } from 'sonner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { LoadingCard } from '@/components/LoadingCard';
import { AdminGuard } from '@/components/AdminGuard';
import { adminApi } from '@/lib/api';
import { useTranslation } from '@/i18n/LanguageContext';
import type { AdminDashboardStats, AdminUsersResponse, AdminRemovedListingsResponse } from '@/lib/types';

export default function AdminPage() {
  return (
    <AdminGuard>
      <AdminDashboard />
    </AdminGuard>
  );
}

function AdminDashboard() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [usersPage, setUsersPage] = useState(0);
  const [removedPage, setRemovedPage] = useState(0);

  const { data: stats, isLoading: statsLoading } = useQuery<AdminDashboardStats>({
    queryKey: ['admin', 'stats'],
    queryFn: () => adminApi.stats(),
    refetchInterval: 30_000,
  });

  const { data: usersData, isLoading: usersLoading } = useQuery<AdminUsersResponse>({
    queryKey: ['admin', 'users', usersPage],
    queryFn: () => adminApi.users(50, usersPage * 50),
  });

  const { data: removedData, isLoading: removedLoading } = useQuery<AdminRemovedListingsResponse>({
    queryKey: ['admin', 'removed-listings', removedPage],
    queryFn: () => adminApi.removedListings(removedPage, 50),
    refetchInterval: 60_000,
  });

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      adminApi.updateRole(userId, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin'] });
      toast.success(t('admin.roleUpdated'));
    },
    onError: () => toast.error(t('admin.roleUpdateFailed')),
  });

  const activeMutation = useMutation({
    mutationFn: ({ userId, isActive }: { userId: string; isActive: boolean }) =>
      adminApi.toggleActive(userId, isActive),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin'] });
      toast.success(t('admin.statusUpdated'));
    },
    onError: () => toast.error(t('admin.statusUpdateFailed')),
  });

  if (statsLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">{t('admin.title')}</h1>
          <p className="text-muted-foreground">{t('admin.subtitle')}</p>
        </div>
        <LoadingCard message={t('admin.loading')} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">{t('admin.title')}</h1>
        <p className="text-muted-foreground">{t('admin.subtitle')}</p>
      </div>

      {/* Stat cards */}
      {stats && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardDescription>{t('admin.totalUsers')}</CardDescription>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_users}</div>
              <p className="text-xs text-muted-foreground">
                {stats.users_by_role.map(r => `${r.count} ${r.role}`).join(' / ')}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardDescription>{t('admin.activeUsers24h')}</CardDescription>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.active_users_24h}</div>
              <p className="text-xs text-muted-foreground">{t('admin.uniqueUsers')}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardDescription>{t('admin.requests24h')}</CardDescription>
              <BarChart3 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_requests_24h.toLocaleString()}</div>
              <p className="text-xs text-muted-foreground">
                {t('admin.requests7d', { count: stats.total_requests_7d.toLocaleString() })}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardDescription>{t('admin.avgResponseTime')}</CardDescription>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats.avg_response_ms_24h != null ? `${stats.avg_response_ms_24h}ms` : '-'}
              </div>
              <p className="text-xs text-muted-foreground">{t('admin.last24h')}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Top endpoints */}
      {stats && stats.top_endpoints.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>{t('admin.topEndpoints')}</CardTitle>
            <CardDescription>{t('admin.topEndpointsDesc')}</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('admin.endpoint')}</TableHead>
                  <TableHead className="text-right">{t('admin.requestCount')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stats.top_endpoints.map((ep) => (
                  <TableRow key={ep.endpoint}>
                    <TableCell className="font-mono text-sm">{ep.endpoint}</TableCell>
                    <TableCell className="text-right">{ep.count.toLocaleString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Requests per day chart (simple table) */}
      {stats && stats.requests_per_day.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>{t('admin.requestsPerDay')}</CardTitle>
            <CardDescription>{t('admin.last30Days')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-end gap-1 h-32">
              {stats.requests_per_day.map((d) => {
                const max = Math.max(...stats.requests_per_day.map(x => x.count), 1);
                const pct = (d.count / max) * 100;
                return (
                  <div
                    key={d.day}
                    className="flex-1 bg-primary/80 rounded-t hover:bg-primary transition-colors"
                    style={{ height: `${Math.max(pct, 2)}%` }}
                    title={`${d.day}: ${d.count} requests`}
                  />
                );
              })}
            </div>
            <div className="flex justify-between text-xs text-muted-foreground mt-1">
              <span>{stats.requests_per_day[0]?.day}</span>
              <span>{stats.requests_per_day[stats.requests_per_day.length - 1]?.day}</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent signups */}
      {stats && stats.recent_signups.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>{t('admin.recentSignups')}</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('admin.email')}</TableHead>
                  <TableHead>{t('admin.name')}</TableHead>
                  <TableHead>{t('admin.provider')}</TableHead>
                  <TableHead>{t('admin.role')}</TableHead>
                  <TableHead>{t('admin.joined')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stats.recent_signups.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell className="text-sm">{u.email}</TableCell>
                    <TableCell className="text-sm">{[u.first_name, u.last_name].filter(Boolean).join(' ') || '-'}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{u.auth_provider}</Badge>
                    </TableCell>
                    <TableCell>
                      <RoleBadge role={u.role} />
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(u.created_at).toLocaleDateString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Removed Listings Analytics */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Archive className="h-5 w-5 text-muted-foreground" />
            <div>
              <CardTitle>{t('admin.removedListings')}</CardTitle>
              <CardDescription>{t('admin.removedListingsDesc')}</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {removedLoading ? (
            <LoadingCard message={t('admin.loadingRemoved')} />
          ) : removedData ? (
            <div className="space-y-6">
              {/* Stat cards */}
              <div className="grid gap-4 sm:grid-cols-3">
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <CardDescription>{t('admin.removed7d')}</CardDescription>
                    <Archive className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{removedData.stats.total_removed_7d}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <CardDescription>{t('admin.removed30d')}</CardDescription>
                    <Calendar className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{removedData.stats.total_removed_30d}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <CardDescription>{t('admin.avgDaysOnMarket')}</CardDescription>
                    <Clock className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">
                      {removedData.stats.avg_days_on_market != null
                        ? `${removedData.stats.avg_days_on_market}d`
                        : '-'}
                    </div>
                    <p className="text-xs text-muted-foreground">{t('admin.avgDom')}</p>
                  </CardContent>
                </Card>
              </div>

              {/* Region & Type breakdowns */}
              <div className="grid gap-4 sm:grid-cols-2">
                {removedData.stats.by_region.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium mb-2">{t('admin.byRegion')}</h4>
                    <div className="flex flex-wrap gap-1.5">
                      {removedData.stats.by_region.map((r) => (
                        <Badge key={r.region} variant="secondary" className="gap-1">
                          <MapPin className="h-3 w-3" />
                          {r.region} ({r.count})
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                {removedData.stats.by_property_type.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium mb-2">{t('admin.byPropertyType')}</h4>
                    <div className="flex flex-wrap gap-1.5">
                      {removedData.stats.by_property_type.map((pt) => (
                        <Badge key={pt.property_type ?? 'unknown'} variant="outline">
                          {pt.property_type ?? 'N/A'} ({pt.count})
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Weekly removals chart */}
              {removedData.stats.weekly_removals.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-2">{t('admin.weeklyRemovals')}</h4>
                  <p className="text-xs text-muted-foreground mb-2">{t('admin.last4Weeks')}</p>
                  <div className="flex items-end gap-2 h-24">
                    {removedData.stats.weekly_removals.map((w) => {
                      const max = Math.max(...removedData.stats.weekly_removals.map(x => x.count), 1);
                      const pct = (w.count / max) * 100;
                      const weekLabel = new Date(w.week_start).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
                      return (
                        <div key={w.week_start} className="flex-1 flex flex-col items-center gap-1">
                          <div
                            className="w-full bg-primary/80 rounded-t hover:bg-primary transition-colors"
                            style={{ height: `${Math.max(pct, 4)}%` }}
                            title={`${weekLabel}: ${w.count}`}
                          />
                          <span className="text-[10px] text-muted-foreground">{weekLabel}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Listing table */}
              {removedData.listings.length > 0 ? (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('admin.address')}</TableHead>
                        <TableHead>{t('admin.city')}</TableHead>
                        <TableHead>{t('admin.region')}</TableHead>
                        <TableHead>{t('admin.propertyType')}</TableHead>
                        <TableHead className="text-right">{t('admin.price')}</TableHead>
                        <TableHead>{t('admin.status')}</TableHead>
                        <TableHead className="text-right">{t('admin.dom')}</TableHead>
                        <TableHead>{t('admin.lastSeen')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {removedData.listings.map((l) => (
                        <TableRow key={l.property_id}>
                          <TableCell className="text-sm font-medium">{l.address}</TableCell>
                          <TableCell className="text-sm">{l.city}</TableCell>
                          <TableCell className="text-sm">{l.region ?? '-'}</TableCell>
                          <TableCell className="text-sm">{l.property_type ?? '-'}</TableCell>
                          <TableCell className="text-sm text-right">
                            {l.price != null ? `$${l.price.toLocaleString()}` : '-'}
                          </TableCell>
                          <TableCell>
                            <Badge variant={l.status === 'delisted' ? 'destructive' : 'secondary'}>
                              {l.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-sm text-right">
                            {l.days_on_market != null ? l.days_on_market : '-'}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {l.last_seen_at ? new Date(l.last_seen_at).toLocaleDateString() : '-'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>

                  {removedData.total_count > 50 && (
                    <div className="flex justify-center gap-2 mt-4">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={removedPage === 0}
                        onClick={() => setRemovedPage(p => p - 1)}
                      >
                        {t('admin.previous')}
                      </Button>
                      <span className="flex items-center text-sm text-muted-foreground">
                        {t('admin.pageInfo', {
                          current: removedPage + 1,
                          total: Math.ceil(removedData.total_count / 50),
                        })}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={(removedPage + 1) * 50 >= removedData.total_count}
                        onClick={() => setRemovedPage(p => p + 1)}
                      >
                        {t('admin.next')}
                      </Button>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">{t('admin.noRemovedListings')}</p>
              )}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* User management */}
      <Card>
        <CardHeader>
          <CardTitle>{t('admin.userManagement')}</CardTitle>
          <CardDescription>
            {usersData ? t('admin.totalUsersCount', { count: usersData.total }) : ''}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {usersLoading ? (
            <LoadingCard message={t('admin.loadingUsers')} />
          ) : usersData ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('admin.email')}</TableHead>
                    <TableHead>{t('admin.name')}</TableHead>
                    <TableHead>{t('admin.provider')}</TableHead>
                    <TableHead>{t('admin.role')}</TableHead>
                    <TableHead>{t('admin.status')}</TableHead>
                    <TableHead>{t('admin.joined')}</TableHead>
                    <TableHead>{t('admin.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {usersData.users.map((u) => (
                    <TableRow key={u.id}>
                      <TableCell className="text-sm">{u.email}</TableCell>
                      <TableCell className="text-sm">
                        {[u.first_name, u.last_name].filter(Boolean).join(' ') || '-'}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{u.auth_provider}</Badge>
                      </TableCell>
                      <TableCell>
                        <Select
                          value={u.role}
                          onValueChange={(role) => roleMutation.mutate({ userId: u.id, role })}
                        >
                          <SelectTrigger className="w-24 h-8">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="free">free</SelectItem>
                            <SelectItem value="pro">pro</SelectItem>
                            <SelectItem value="admin">admin</SelectItem>
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell>
                        <Badge variant={u.is_active ? 'default' : 'destructive'}>
                          {u.is_active ? t('admin.active') : t('admin.disabled')}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(u.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            activeMutation.mutate({ userId: u.id, isActive: !u.is_active })
                          }
                          title={u.is_active ? t('admin.disableUser') : t('admin.enableUser')}
                        >
                          {u.is_active ? (
                            <Ban className="h-4 w-4 text-destructive" />
                          ) : (
                            <Check className="h-4 w-4 text-primary" />
                          )}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {usersData.total > 50 && (
                <div className="flex justify-center gap-2 mt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={usersPage === 0}
                    onClick={() => setUsersPage(p => p - 1)}
                  >
                    {t('admin.previous')}
                  </Button>
                  <span className="flex items-center text-sm text-muted-foreground">
                    {t('admin.pageInfo', {
                      current: usersPage + 1,
                      total: Math.ceil(usersData.total / 50),
                    })}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={(usersPage + 1) * 50 >= usersData.total}
                    onClick={() => setUsersPage(p => p + 1)}
                  >
                    {t('admin.next')}
                  </Button>
                </div>
              )}
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

function RoleBadge({ role }: { role: string }) {
  const variant = role === 'admin' ? 'default' : role === 'pro' ? 'secondary' : 'outline';
  return (
    <Badge variant={variant} className="gap-1">
      {role === 'admin' && <Shield className="h-3 w-3" />}
      {role}
    </Badge>
  );
}
