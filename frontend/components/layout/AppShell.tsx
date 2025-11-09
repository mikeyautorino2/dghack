'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-bg-primary text-text-primary">
      {/* Navigation */}
      <nav className="border-b border-border-subtle bg-bg-primary/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link href="/" className="text-xl font-semibold tracking-tight hover:text-text-secondary transition-colors">
              Betting Analytics
            </Link>

            {/* Sport filter tabs */}
            <div className="flex gap-2">
              <TabButton href="/" active={pathname === '/'}>
                All
              </TabButton>
              <TabButton href="/?sport=NBA" active={pathname === '/' && false}>
                NBA
              </TabButton>
              <TabButton href="/?sport=NFL" active={pathname === '/' && false}>
                NFL
              </TabButton>
            </div>
          </div>

          {/* Live indicator */}
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-accent-home rounded-full animate-pulse" />
            <span className="text-sm text-text-tertiary">
              Live Prices
            </span>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-6 py-12">
        {children}
      </main>
    </div>
  );
}

function TabButton({
  href,
  active,
  children
}: {
  href: string;
  active?: boolean;
  children: React.ReactNode
}) {
  return (
    <Link
      href={href}
      className={`
        px-4 py-1.5 rounded-lg text-sm font-medium transition-colors
        ${active
          ? 'bg-bg-tertiary text-text-primary'
          : 'text-text-tertiary hover:text-text-primary hover:bg-bg-secondary'
        }
      `}
    >
      {children}
    </Link>
  );
}
