'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Building2, BarChart3, Bell, Calculator, Briefcase } from 'lucide-react';
import { cn } from '@/lib/utils';

const navigation = [
  { name: 'Search', href: '/search', icon: Building2 },
  { name: 'Compare', href: '/compare', icon: BarChart3 },
  { name: 'Calculator', href: '/calculator', icon: Calculator },
  { name: 'Alerts', href: '/alerts', icon: Bell },
  { name: 'Portfolio', href: '/portfolio', icon: Briefcase },
];

export function Header() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center">
        <div className="mr-4 flex">
          <Link href="/" className="mr-6 flex items-center space-x-2">
            <Building2 className="h-6 w-6 text-primary" />
            <span className="hidden font-bold sm:inline-block">
              HouseMktAnalyzr
            </span>
          </Link>
          <nav className="flex items-center space-x-6 text-sm font-medium">
            {navigation.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-1.5 transition-colors hover:text-foreground/80',
                    isActive ? 'text-foreground' : 'text-foreground/60'
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  <span className="hidden md:inline">{item.name}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </div>
    </header>
  );
}
