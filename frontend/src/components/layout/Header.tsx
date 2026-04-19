import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Moon, Sun, Printer, LogOut, Menu, User } from 'lucide-react';
import { useAuthStore } from '@/store/auth';
import { useTheme } from '@/hooks/useTheme';
import { getWorkspaceForPath } from './workspaces';

interface HeaderProps {
  onOpenMobileNav?: () => void;
}

export default function Header({ onOpenMobileNav }: HeaderProps) {
  const { dark, toggle } = useTheme();
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const workspace = getWorkspaceForPath(location.pathname);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-[color:var(--color-shell)] backdrop-blur-xl">
      <div className="mx-auto max-w-[96rem] px-4 sm:px-6 lg:px-8">
        <div className="flex min-h-18 items-center justify-between gap-4 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <button
              onClick={onOpenMobileNav}
              className="rounded-xl border border-border bg-card/70 p-2 text-muted-foreground transition-colors hover:text-foreground md:hidden"
              aria-label="Open navigation menu"
            >
              <Menu className="w-5 h-5" />
            </button>

            <Link to="/control-center" className="flex min-w-0 items-center gap-3 no-underline">
              <div className="flex h-11 w-11 items-center justify-center rounded-md border border-primary/30 bg-primary text-primary-foreground shadow-sm">
                <Printer className="h-5 w-5 shrink-0" />
              </div>
              <div className="min-w-0">
                <span className="block truncate font-display text-lg font-semibold text-foreground">
                  3D Print Sales
                </span>
                <span className="block truncate text-xs uppercase tracking-[0.22em] text-muted-foreground">
                  {workspace.label}
                </span>
              </div>
            </Link>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <button
              onClick={toggle}
              className="rounded-xl border border-border bg-card/70 p-2 text-muted-foreground transition-colors hover:text-foreground"
              aria-label="Toggle theme"
            >
              {dark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>

            {user && (
              <div className="hidden min-w-0 max-w-[280px] items-center gap-3 rounded-md border border-border bg-card/70 px-3 py-2 text-sm text-muted-foreground sm:flex">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-background/80 text-foreground">
                  <User className="h-4 w-4 shrink-0" />
                </div>
                <div className="min-w-0">
                  <span className="block truncate font-medium text-foreground">{user.full_name}</span>
                  <span className="block truncate text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    {user.role}
                  </span>
                </div>
                <button
                  onClick={handleLogout}
                  className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-destructive"
                  aria-label="Logout"
                  title="Sign out"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            )}

            {user && (
              <button
                onClick={handleLogout}
                className="rounded-xl border border-border bg-card/70 p-2 text-muted-foreground transition-colors hover:text-destructive sm:hidden"
                aria-label="Logout"
                title="Sign out"
              >
                <LogOut className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
