import { Link, useNavigate } from 'react-router-dom';
import { Moon, Sun, Printer, LogOut, Menu, Search, User } from 'lucide-react';
import { useAuthStore } from '@/store/auth';
import { useTheme } from '@/hooks/useTheme';
import { Button } from '@/components/ui/Button';

interface HeaderProps {
  onOpenMobileNav?: () => void;
  onOpenCommandPalette?: () => void;
}

export default function Header({ onOpenMobileNav, onOpenCommandPalette }: HeaderProps) {
  const { dark, toggle } = useTheme();
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-card">
      <div className="mx-auto max-w-[96rem] px-4 sm:px-6 lg:px-8">
        <div className="flex min-h-14 items-center justify-between gap-4 py-2">
          <div className="flex min-w-0 items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={onOpenMobileNav}
              className="md:hidden"
              aria-label="Open navigation menu"
            >
              <Menu className="w-5 h-5" />
            </Button>

            <Link to="/control-center" className="flex min-w-0 items-center gap-3 no-underline">
              <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <Printer className="h-4 w-4 shrink-0" />
              </div>
              <span className="block truncate font-display text-lg font-semibold text-foreground">
                3D Print Sales
              </span>
            </Link>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {onOpenCommandPalette ? (
              <button
                type="button"
                onClick={onOpenCommandPalette}
                aria-label="Open command palette"
                title="Search (⌘K)"
                className="hidden min-w-[240px] items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted md:flex"
              >
                <Search className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="flex-1 text-left">Search…</span>
                <kbd className="rounded border border-border bg-card px-1.5 py-0.5 text-[10px] font-medium">
                  ⌘K
                </kbd>
              </button>
            ) : null}
            {onOpenCommandPalette ? (
              <Button
                variant="ghost"
                size="icon"
                onClick={onOpenCommandPalette}
                aria-label="Open command palette"
                className="md:hidden"
              >
                <Search className="h-5 w-5" />
              </Button>
            ) : null}
            <Button
              variant="ghost"
              size="icon"
              onClick={toggle}
              aria-label="Toggle theme"
            >
              {dark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </Button>

            {user && (
              <div className="hidden min-w-0 max-w-[280px] items-center gap-3 px-2 py-1 text-sm text-muted-foreground sm:flex">
                <div className="flex h-8 w-8 items-center justify-center rounded-md bg-muted/60 text-foreground">
                  <User className="h-4 w-4 shrink-0" />
                </div>
                <div className="min-w-0">
                  <span className="block truncate font-medium text-foreground">{user.full_name}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {user.role}
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleLogout}
                  aria-label="Logout"
                  title="Sign out"
                >
                  <LogOut className="w-4 h-4" />
                </Button>
              </div>
            )}

            {user && (
              <Button
                variant="ghost"
                size="icon"
                onClick={handleLogout}
                className="sm:hidden"
                aria-label="Logout"
                title="Sign out"
              >
                <LogOut className="w-5 h-5" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
