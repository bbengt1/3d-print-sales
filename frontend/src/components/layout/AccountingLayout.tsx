import { NavLink, Outlet } from 'react-router-dom';
import {
  Banknote,
  Building2,
  ClipboardList,
  CreditCard,
  FileMinus,
  FileText,
  Layers,
  MapPin,
  Receipt,
  RefreshCw,
  Repeat,
  ScrollText,
  Truck,
  Wallet,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Link {
  to: string;
  label: string;
  icon: LucideIcon;
}

const links: Link[] = [
  { to: '/accounting/invoices', label: 'Invoices', icon: FileText },
  { to: '/accounting/quotes', label: 'Quotes', icon: ScrollText },
  { to: '/accounting/sales-orders', label: 'Sales orders', icon: ClipboardList },
  { to: '/accounting/purchase-orders', label: 'Purchase orders', icon: ClipboardList },
  { to: '/accounting/delivery-notes', label: 'Delivery notes', icon: Truck },
  { to: '/accounting/credit-notes', label: 'Credit notes', icon: FileMinus },
  { to: '/accounting/debit-notes', label: 'Debit notes', icon: FileMinus },
  { to: '/accounting/recurring-invoices', label: 'Recurring invoices', icon: Repeat },
  { to: '/accounting/banking', label: 'Banking', icon: Banknote },
  { to: '/accounting/expense-claims', label: 'Expense claims', icon: Wallet },
  { to: '/accounting/fixed-assets', label: 'Fixed assets', icon: Building2 },
  { to: '/accounting/intangibles', label: 'Intangibles', icon: Layers },
  { to: '/accounting/production-orders', label: 'Production orders', icon: RefreshCw },
  { to: '/accounting/locations', label: 'Locations', icon: MapPin },
  { to: '/accounting/reports', label: 'Reports', icon: Receipt },
  { to: '/accounting/foundations', label: 'Foundations', icon: CreditCard },
  { to: '/accounting/master-data', label: 'Master data', icon: ClipboardList },
];

export default function AccountingLayout() {
  return (
    <div className="flex gap-8">
      <aside className="hidden md:block w-56 shrink-0">
        <nav className="sticky top-24 space-y-1">
          <h3 className="mb-3 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Accounting
          </h3>
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium no-underline transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="mb-6 flex w-full gap-1 overflow-x-auto pb-2 md:hidden">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2 whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium no-underline transition-colors',
                isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-accent'
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </div>
      <div className="min-w-0 flex-1">
        <Outlet />
      </div>
    </div>
  );
}
