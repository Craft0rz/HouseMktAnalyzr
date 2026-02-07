'use client';

import { Loader2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';

interface LoadingCardProps {
  message?: string;
  description?: string;
  progress?: number;
  showProgress?: boolean;
}

export function LoadingCard({
  message = 'Loading...',
  description,
  progress,
  showProgress = false,
}: LoadingCardProps) {
  return (
    <Card>
      <CardContent className="py-6">
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <span className="font-medium">{message}</span>
          </div>
          {showProgress && progress !== undefined && (
            <Progress value={progress} className="h-2" />
          )}
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
