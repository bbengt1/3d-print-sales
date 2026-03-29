import {
  BarChart3,
  Boxes,
  Calculator,
  DollarSign,
  Gauge,
  Package,
  Printer,
  ShoppingCart,
  Users,
  ClipboardList,
  type LucideIcon,
} from 'lucide-react';

export interface AppNavLink {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

export const appNavLinks: AppNavLink[] = [
  { to: '/', label: 'Dashboard', icon: Gauge, end: true },
  { to: '/jobs', label: 'Jobs', icon: ClipboardList },
  { to: '/printers', label: 'Printers', icon: Printer },
  { to: '/materials', label: 'Materials', icon: Boxes },
  { to: '/rates', label: 'Rates', icon: DollarSign },
  { to: '/products', label: 'Products', icon: Package },
  { to: '/inventory', label: 'Inventory', icon: Package },
  { to: '/sales', label: 'Sales', icon: ShoppingCart },
  { to: '/customers', label: 'Customers', icon: Users },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
  { to: '/calculator', label: 'Calculator', icon: Calculator },
];
