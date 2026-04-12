import { NavLink, Outlet, Navigate } from 'react-router-dom';
import { Settings, Users, Download } from 'lucide-react';
import { useAuthStore } from '@/store/auth';
import { cn } from '@/lib/utils';

const adminLinks = [
  { to: '/admin/settings', label: 'Settings', icon: Settings },
  { to: '/admin/users', label: 'Users', icon: Users },
  { to: '/admin/data', label: 'Data Export', icon: Download },
];

export default function AdminLayout() {
  const { user } = useAuthStore();

  if (user?.role !== 'admin') {
    return <Navigate to="/control-center" replace />;
  }

  return (
    <div className="flex gap-8">
      <aside className="hidden md:block w-56 shrink-0">
        <nav className="sticky top-24 space-y-1">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 px-3">
            Administration
          </h3>
          {adminLinks.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors no-underline',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                )
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Mobile nav */}
      <div className="md:hidden flex gap-1 mb-6 overflow-x-auto pb-2 w-full">
        {adminLinks.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap transition-colors no-underline',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-accent'
              )
            }
          >
            <Icon className="w-4 h-4" />
            {label}
          </NavLink>
        ))}
      </div>

      <div className="flex-1 min-w-0">
        <Outlet />
      </div>
    </div>
  );
}
