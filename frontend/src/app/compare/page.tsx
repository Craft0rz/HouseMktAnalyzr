'use client';

import { BarChart3 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function ComparePage() {
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
          <CardTitle className="mt-4">Coming in Phase 07-04</CardTitle>
        </CardHeader>
        <CardContent>
          <CardDescription>
            Side-by-side property comparison with investment metrics, score breakdowns,
            and visual analysis will be implemented in the next phase.
          </CardDescription>
        </CardContent>
      </Card>
    </div>
  );
}
