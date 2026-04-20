import { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { ChevronLeft, X } from 'lucide-react';
import Header from './Header';
import Footer from './Footer';
import { useAuthStore } from '@/store/auth';
import { cn } from '@/lib/utils';
import WorkspaceLocalNav from './WorkspaceLocalNav';
import QueryErrorBoundary from '@/components/ui/QueryErrorBoundary';
import { getVisibleWorkspaces, isWorkspaceLinkActive } from './workspaces';

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuthStore();
  const location = useLocation();
  const visibleWorkspaces = getVisibleWorkspaces(user?.role);

  return (
    <div className="flex h-full flex-col">
      <nav className="space-y-1 px-1">
        {visibleWorkspaces.map(({ key, to, label, icon: Icon, matchPrefixes }) => (
          <NavLink
            key={key}
            to={to}
            onClick={onNavigate}
            className={() =>
              cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors no-underline',
                isWorkspaceLinkActive(location.pathname, matchPrefixes)
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground'
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

export default function Layout() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="min-h-screen flex flex-col bg-background text-sm text-foreground">
      <Header onOpenMobileNav={() => setMobileNavOpen(true)} />

      <div className="mx-auto flex-1 w-full max-w-[96rem] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="flex min-h-full gap-6 lg:gap-8">
          <aside className="hidden w-80 shrink-0 xl:block">
            <div className="sticky top-24 rounded-md border border-border bg-card p-2 shadow-xs">
              <SidebarContent />
            </div>
          </aside>

          <main className="min-w-0 flex-1 space-y-5">
            <WorkspaceLocalNav />
            <QueryErrorBoundary>
              <Outlet />
            </QueryErrorBoundary>
          </main>
        </div>
      </div>

      {mobileNavOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <button
            type="button"
            className="absolute inset-0 bg-black/50"
            aria-label="Close navigation menu"
            onClick={() => setMobileNavOpen(false)}
          />

          <aside className="relative flex h-full w-full max-w-sm flex-col border-r border-border bg-card shadow-xl">
            <div className="flex items-center justify-between border-b border-border px-4 py-4">
              <div>
                <p className="text-sm font-semibold">Workspaces</p>
                <p className="text-xs text-muted-foreground">Jump to the right operating context</p>
              </div>
              <button
                onClick={() => setMobileNavOpen(false)}
                className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-accent"
                aria-label="Close navigation menu"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto py-4">
              <SidebarContent onNavigate={() => setMobileNavOpen(false)} />
            </div>

            <div className="border-t border-border p-3">
              <button
                onClick={() => setMobileNavOpen(false)}
                className="flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent"
              >
                <ChevronLeft className="h-4 w-4" />
                Close menu
              </button>
            </div>
          </aside>
        </div>
      )}

      <Footer />
    </div>
  );
}
