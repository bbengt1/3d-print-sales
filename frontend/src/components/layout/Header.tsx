import { Link, useNavigate } from 'react-router-dom';
import { Moon, Sun, Printer, LogOut, Menu, Settings, User } from 'lucide-react';
import { useAuthStore } from '@/store/auth';
import { useTheme } from '@/hooks/useTheme';

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
    <header className="border-b border-border bg-card/95 backdrop-blur sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={onOpenMobileNav}
              className="md:hidden p-2 rounded-md hover:bg-accent transition-colors text-muted-foreground"
              aria-label="Open navigation menu"
            >
              <Menu className="w-5 h-5" />
            </button>

            <Link to="/" className="flex items-center gap-2 text-primary font-bold text-xl no-underline min-w-0">
              <Printer className="w-6 h-6 shrink-0" />
              <span className="truncate">3D Print Sales</span>
            </Link>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {user?.role === 'admin' && (
              <Link
                to="/admin/settings"
                className="hidden sm:inline-flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium no-underline text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              >
                <Settings className="w-4 h-4" />
                Admin
              </Link>
            )}

            <button
              onClick={toggle}
              className="p-2 rounded-md hover:bg-accent transition-colors text-muted-foreground"
              aria-label="Toggle theme"
            >
              {dark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>

            {user && (
              <div className="hidden sm:flex items-center gap-2 text-sm text-muted-foreground border-l border-border pl-3 ml-1 min-w-0 max-w-[220px]">
                <User className="w-4 h-4 shrink-0" />
                <span className="truncate">{user.full_name}</span>
                <button
                  onClick={handleLogout}
                  className="p-1.5 rounded-md hover:bg-accent transition-colors text-muted-foreground hover:text-destructive"
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
                className="sm:hidden p-2 rounded-md hover:bg-accent transition-colors text-muted-foreground"
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
