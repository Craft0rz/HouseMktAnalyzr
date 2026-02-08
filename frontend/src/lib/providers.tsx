'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'next-themes';
import { useState, type ReactNode } from 'react';
import { ComparisonProvider } from './comparison-context';
import { PortfolioProvider } from './portfolio-context';
import { LanguageProvider } from '@/i18n/LanguageContext';

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <LanguageProvider>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
        <QueryClientProvider client={queryClient}>
          <PortfolioProvider>
            <ComparisonProvider>
              {children}
            </ComparisonProvider>
          </PortfolioProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </LanguageProvider>
  );
}
