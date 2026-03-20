import { NavLink, Outlet } from 'react-router-dom';
import { cn } from '@/lib/utils';

const tabs = [
  { to: '/reports/inventory', label: 'Inventory' },
  { to: '/reports/sales', label: 'Sales' },
  { to: '/reports/pl', label: 'Profit & Loss' },
];

export default function ReportsLayout() {
  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Reports</h1>

      {/* Sub-navigation tabs */}
      <div className="border-b border-border mb-6">
        <nav className="flex gap-1 -mb-px">
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) =>
                cn(
                  'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors no-underline',
                  isActive
                    ? 'border-primary text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
                )
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </div>

      <Outlet />
    </div>
  );
}
