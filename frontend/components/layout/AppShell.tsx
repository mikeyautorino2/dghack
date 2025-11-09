'use client';

import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentSport = searchParams.get('sport');

  // Determine active tab based on URL
  const isHomePage = pathname === '/';
  const activeTab = isHomePage
    ? (currentSport?.toUpperCase() || 'NBA') // Default to NBA on homepage
    : null;

  return (
    <div className="min-h-screen bg-bg-primary text-text-primary">
      {/* Navigation */}
      <nav className="border-b border-border-subtle bg-bg-primary/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link href="/" className="text-xl font-semibold tracking-tight hover:text-text-secondary transition-colors">
              degenstock
            </Link>

            {/* Sport filter tabs - only show on homepage */}
            {isHomePage && (
              <div className="flex gap-2">
                <TabButton href="/?sport=NBA" active={activeTab === 'NBA'}>
                  NBA
                </TabButton>
                <TabButton href="/?sport=NFL" active={activeTab === 'NFL'}>
                  NFL
                </TabButton>
              </div>
            )}
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
