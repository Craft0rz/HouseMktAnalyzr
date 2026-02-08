'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { ThemeProvider } from 'next-themes';
import { useState, type ReactNode } from 'react';
import { AuthProvider } from './auth-context';
import { ComparisonProvider } from './comparison-context';
import { PortfolioProvider } from './portfolio-context';
import { LanguageProvider } from '@/i18n/LanguageContext';

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '';

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
          <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
            <AuthProvider>
              <PortfolioProvider>
                <ComparisonProvider>
                  {children}
                </ComparisonProvider>
              </PortfolioProvider>
            </AuthProvider>
          </GoogleOAuthProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </LanguageProvider>
  );
}
