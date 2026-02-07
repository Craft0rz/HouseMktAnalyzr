'use client';

import { Briefcase } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function PortfolioPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Portfolio</h1>
        <p className="text-muted-foreground">
          Track your investment properties and monitor performance.
        </p>
      </div>

      <Card>
        <CardHeader>
          <Briefcase className="h-10 w-10 text-muted-foreground" />
          <CardTitle className="mt-4">Coming in Phase 07-06</CardTitle>
        </CardHeader>
        <CardContent>
          <CardDescription>
            Portfolio tracking with purchase price, current value, ROI history,
            and rent tracking will be implemented in the final phase.
          </CardDescription>
        </CardContent>
      </Card>
    </div>
  );
}
