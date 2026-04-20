import { Link, useNavigate } from 'react-router-dom';
import { Moon, Sun, Printer, LogOut, Menu, User } from 'lucide-react';
import { useAuthStore } from '@/store/auth';
import { useTheme } from '@/hooks/useTheme';
import { Button } from '@/components/ui/Button';

interface HeaderProps {
  onOpenMobileNav?: () => void;
}

export default function Header({ onOpenMobileNav }: HeaderProps) {
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
