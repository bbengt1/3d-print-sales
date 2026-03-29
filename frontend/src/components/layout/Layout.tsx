import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { ChevronLeft, Settings, X } from 'lucide-react';
import Header from './Header';
import Footer from './Footer';
import { useAuthStore } from '@/store/auth';
import { cn } from '@/lib/utils';
import { appNavLinks } from './appNav';

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuthStore();

  return (
    <div className="flex h-full flex-col">
      <div className="px-3 pb-3">
        <p className="px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Main Navigation
        </p>
      </div>

      <nav className="space-y-1 px-3">
        {appNavLinks.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors no-underline',
                isActive
                  ? 'bg-primary/10 text-primary shadow-sm'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent'
              )
            }
          >
            <Icon className="w-4 h-4 shrink-0" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {user?.role === 'admin' && (
        <div className="mt-6 border-t border-border px-3 pt-6">
          <NavLink
            to="/admin/settings"
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors no-underline',
                isActive
                  ? 'bg-primary/10 text-primary shadow-sm'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent'
              )
            }
          >
            <Settings className="w-4 h-4 shrink-0" />
            <span>Admin</span>
          </NavLink>
        </div>
      )}
    </div>
  );
}

export default function Layout() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Header onOpenMobileNav={() => setMobileNavOpen(true)} />

      <div className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-8">
        <div className="flex gap-6 lg:gap-8 min-h-full">
          <aside className="hidden md:block w-64 shrink-0">
            <div className="sticky top-24 rounded-2xl border border-border bg-card p-3 shadow-sm">
              <SidebarContent />
            </div>
          </aside>

          <main className="flex-1 min-w-0">
            <Outlet />
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

          <aside className="relative flex h-full w-full max-w-xs flex-col border-r border-border bg-card shadow-xl">
            <div className="flex items-center justify-between border-b border-border px-4 py-4">
              <div>
                <p className="text-sm font-semibold">Navigation</p>
                <p className="text-xs text-muted-foreground">Jump to any section</p>
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
