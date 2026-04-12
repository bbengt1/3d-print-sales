import {
  BarChart3,
  Blocks,
  ClipboardList,
  Gauge,
  type LucideIcon,
  Package,
  Printer,
  Receipt,
  Settings,
} from 'lucide-react';

export type WorkspaceRole =
  | 'admin'
  | 'cashier'
  | 'floor'
  | 'inventory'
  | 'catalog'
  | 'analyst'
  | 'general';

export interface WorkspaceLocalLink {
  to: string;
  label: string;
  matchPrefixes?: string[];
}

export interface WorkspaceDefinition {
  key: string;
  label: string;
  description: string;
  to: string;
  icon: LucideIcon;
  roles: WorkspaceRole[];
  matchPrefixes: string[];
  localLinks: WorkspaceLocalLink[];
}

export const workspaces: WorkspaceDefinition[] = [
  {
    key: 'control-center',
    label: 'Control Center',
    description: 'Shift priorities, alerts, and business pulse.',
    to: '/control-center',
    icon: Gauge,
    roles: ['admin', 'cashier', 'floor', 'inventory', 'catalog', 'analyst', 'general'],
    matchPrefixes: ['/', '/control-center'],
    localLinks: [
      { to: '/control-center', label: 'Overview', matchPrefixes: ['/', '/control-center'] },
      { to: '/dashboard', label: 'Classic Dashboard', matchPrefixes: ['/dashboard'] },
    ],
  },
  {
    key: 'print-floor',
    label: 'Print Floor',
    description: 'Printers, telemetry, and live floor operations.',
    to: '/print-floor',
    icon: Printer,
    roles: ['admin', 'floor', 'general'],
    matchPrefixes: ['/print-floor', '/printers'],
    localLinks: [
      { to: '/print-floor', label: 'Fleet Overview', matchPrefixes: ['/print-floor', '/printers'] },
      { to: '/print-floor/printers/new', label: 'Add Printer', matchPrefixes: ['/print-floor/printers/new', '/printers/new'] },
    ],
  },
  {
    key: 'sell',
    label: 'Sell',
    description: 'Counter checkout, retail flow, and sales activity.',
    to: '/sell',
    icon: Receipt,
    roles: ['admin', 'cashier', 'general'],
    matchPrefixes: ['/sell', '/pos', '/sales'],
    localLinks: [
      { to: '/sell', label: 'POS Register', matchPrefixes: ['/sell', '/pos'] },
      { to: '/sell/sales', label: 'Sales Inbox', matchPrefixes: ['/sell/sales', '/sales'] },
      { to: '/sell/channels', label: 'Channels', matchPrefixes: ['/sell/channels', '/sales/channels'] },
    ],
  },
  {
    key: 'stock',
    label: 'Stock',
    description: 'Inventory movement, exceptions, and materials.',
    to: '/stock',
    icon: Blocks,
    roles: ['admin', 'inventory', 'floor', 'general'],
    matchPrefixes: ['/stock', '/inventory', '/materials'],
    localLinks: [
      { to: '/stock', label: 'Exceptions', matchPrefixes: ['/stock', '/inventory'] },
      { to: '/stock/materials', label: 'Materials', matchPrefixes: ['/stock/materials', '/materials'] },
    ],
  },
  {
    key: 'product-studio',
    label: 'Product Studio',
    description: 'Catalog, pricing, and product authoring.',
    to: '/product-studio',
    icon: Package,
    roles: ['admin', 'catalog', 'inventory', 'general'],
    matchPrefixes: ['/product-studio', '/products', '/calculator', '/rates'],
    localLinks: [
      { to: '/product-studio', label: 'Products', matchPrefixes: ['/product-studio', '/products'] },
      { to: '/product-studio/calculator', label: 'Calculator', matchPrefixes: ['/product-studio/calculator', '/calculator'] },
      { to: '/product-studio/rates', label: 'Rates', matchPrefixes: ['/product-studio/rates', '/rates'] },
    ],
  },
  {
    key: 'orders',
    label: 'Orders',
    description: 'Jobs, customers, and fulfillment-facing work.',
    to: '/orders',
    icon: ClipboardList,
    roles: ['admin', 'cashier', 'floor', 'catalog', 'general'],
    matchPrefixes: ['/orders', '/jobs', '/customers'],
    localLinks: [
      { to: '/orders', label: 'Queue', matchPrefixes: ['/orders'] },
      { to: '/orders/jobs', label: 'Jobs', matchPrefixes: ['/orders/jobs', '/jobs'] },
      { to: '/orders/customers', label: 'Customers', matchPrefixes: ['/orders/customers', '/customers'] },
    ],
  },
  {
    key: 'insights',
    label: 'Insights',
    description: 'Reports, trends, and financial visibility.',
    to: '/insights',
    icon: BarChart3,
    roles: ['admin', 'analyst', 'general'],
    matchPrefixes: ['/insights', '/reports'],
    localLinks: [
      { to: '/insights', label: 'Reports', matchPrefixes: ['/insights', '/reports'] },
    ],
  },
  {
    key: 'admin',
    label: 'Admin',
    description: 'Settings, users, and data export.',
    to: '/admin',
    icon: Settings,
    roles: ['admin'],
    matchPrefixes: ['/admin'],
    localLinks: [
      { to: '/admin/settings', label: 'Settings', matchPrefixes: ['/admin/settings'] },
      { to: '/admin/users', label: 'Users', matchPrefixes: ['/admin/users'] },
      { to: '/admin/cameras', label: 'Cameras', matchPrefixes: ['/admin/cameras'] },
      { to: '/admin/data', label: 'Data Export', matchPrefixes: ['/admin/data'] },
    ],
  },
];

function normalizeRole(role: string | null | undefined): WorkspaceRole {
  const value = (role || '').trim().toLowerCase();

  if (value === 'admin') return 'admin';
  if (['cashier', 'sales', 'retail'].includes(value)) return 'cashier';
  if (['floor', 'operator', 'printer_operator', 'production'].includes(value)) return 'floor';
  if (['inventory', 'warehouse'].includes(value)) return 'inventory';
  if (['catalog', 'product_manager', 'product'].includes(value)) return 'catalog';
  if (['analyst', 'finance', 'owner'].includes(value)) return 'analyst';
  return 'general';
}

export function getVisibleWorkspaces(role: string | null | undefined) {
  const normalized = normalizeRole(role);
  if (normalized === 'admin') return workspaces;
  return workspaces.filter((workspace) => workspace.roles.includes(normalized) || workspace.roles.includes('general'));
}

export function getWorkspaceForPath(pathname: string) {
  const match = workspaces.find((workspace) =>
    workspace.matchPrefixes.some((prefix) => (prefix === '/' ? pathname === '/' : pathname.startsWith(prefix)))
  );
  return match ?? workspaces[0];
}

export function isWorkspaceLinkActive(pathname: string, prefixes: string[]) {
  return prefixes.some((prefix) => (prefix === '/' ? pathname === '/' : pathname.startsWith(prefix)));
}
