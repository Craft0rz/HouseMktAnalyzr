'use client';

import { Building2, TrendingUp, Calculator, Bell } from 'lucide-react';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

const features = [
  {
    title: 'Property Search',
    description: 'Search multi-family properties across Greater Montreal with real-time data from Centris.',
    icon: Building2,
    href: '/',
    color: 'text-blue-500',
  },
  {
    title: 'Investment Analysis',
    description: 'Calculate cap rates, cash flow, ROI and more with our comprehensive analysis tools.',
    icon: TrendingUp,
    href: '/compare',
    color: 'text-green-500',
  },
  {
    title: 'Quick Calculator',
    description: 'Run quick what-if scenarios with our investment calculator.',
    icon: Calculator,
    href: '/calculator',
    color: 'text-purple-500',
  },
  {
    title: 'Smart Alerts',
    description: 'Get notified when properties matching your investment criteria hit the market.',
    icon: Bell,
    href: '/alerts',
    color: 'text-orange-500',
  },
];

export default function Home() {
  return (
    <div className="space-y-8">
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold tracking-tight">
          Find Your Next Investment Property
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          Analyze multi-family properties in Greater Montreal. Compare cap rates,
          cash flow, and ROI to find the best investment opportunities.
        </p>
        <div className="flex gap-4 justify-center pt-4">
          <Button size="lg" asChild>
            <Link href="/">
              <Building2 className="mr-2 h-5 w-5" />
              Search Properties
            </Link>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <Link href="/calculator">
              <Calculator className="mr-2 h-5 w-5" />
              Quick Calculator
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {features.map((feature) => (
          <Link key={feature.href} href={feature.href}>
            <Card className="h-full transition-colors hover:bg-muted/50">
              <CardHeader>
                <feature.icon className={`h-10 w-10 ${feature.color}`} />
                <CardTitle className="mt-4">{feature.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription>{feature.description}</CardDescription>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Getting Started</CardTitle>
          <CardDescription>
            Make sure the FastAPI backend is running to use this application.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-sm text-muted-foreground">
            Start the backend server:
          </p>
          <pre className="bg-muted p-4 rounded-lg text-sm overflow-x-auto">
            <code>
              cd HouseMktAnalyzr{'\n'}
              set PYTHONPATH=src{'\n'}
              python -m uvicorn backend.app.main:app --reload
            </code>
          </pre>
          <p className="text-sm text-muted-foreground mt-4">
            API documentation available at{' '}
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline"
            >
              http://localhost:8000/docs
            </a>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
