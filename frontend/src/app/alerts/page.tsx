'use client';

import { Bell } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function AlertsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Alerts</h1>
        <p className="text-muted-foreground">
          Manage your saved search alerts and notification preferences.
        </p>
      </div>

      <Card>
        <CardHeader>
          <Bell className="h-10 w-10 text-muted-foreground" />
          <CardTitle className="mt-4">Coming in Phase 07-04</CardTitle>
        </CardHeader>
        <CardContent>
          <CardDescription>
            Alert management UI with create, edit, and delete functionality
            will be implemented alongside the comparison features.
          </CardDescription>
        </CardContent>
      </Card>
    </div>
  );
}
