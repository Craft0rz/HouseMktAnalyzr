'use client';

import { Calculator } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function CalculatorPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Investment Calculator</h1>
        <p className="text-muted-foreground">
          Run quick what-if scenarios for investment properties.
        </p>
      </div>

      <Card>
        <CardHeader>
          <Calculator className="h-10 w-10 text-muted-foreground" />
          <CardTitle className="mt-4">Coming in Phase 07-03</CardTitle>
        </CardHeader>
        <CardContent>
          <CardDescription>
            Quick investment calculator with mortgage, cash flow, and ROI calculations
            will be implemented in the property search phase.
          </CardDescription>
        </CardContent>
      </Card>
    </div>
  );
}
