import { useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { Command } from 'cmdk';
import {
  BarChart3,
  Box,
  Boxes,
  Calculator,
  Camera,
  ClipboardList,
  FileText,
  Gauge,
  LayoutDashboard,
  Package,
  Printer,
  Receipt,
  ReceiptText,
  ScanLine,
  Settings,
  Sparkles,
  UsersRound,
} from 'lucide-react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/Dialog';
import { cn } from '@/lib/utils';

interface CommandItemDef {
  id: string;
  label: string;
  /** Search keywords in addition to the label (slugs, abbreviations). */
  keywords?: string[];
  icon?: ReactNode;
  /** Keyboard shortcut hint to render on the right (e.g. `'G S'`). */
  shortcut?: string;
  to?: string;
  action?: () => void;
}

interface CommandGroupDef {
  heading: string;
  items: CommandItemDef[];
}

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  groups: CommandGroupDef[];
}

/**
 * cmdk-backed command palette that renders inside a Radix Dialog. Use
 * `useCommandPalette()` below to get a ready-wired instance + keyboard
 * shortcut handlers; mount at the app shell level.
 */
export default function CommandPalette({ open, onOpenChange, groups }: CommandPaletteProps) {
  const navigate = useNavigate();

  const runItem = (item: CommandItemDef) => {
    onOpenChange(false);
    if (item.action) item.action();
    else if (item.to) navigate(item.to);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg" className="gap-0 p-0" hideClose>
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <Command
          loop
          className="flex w-full flex-col overflow-hidden rounded-lg"
          filter={(value, search, keywords) => {
            const needle = search.trim().toLowerCase();
            if (!needle) return 1;
            const haystack = [value, ...(keywords ?? [])].join(' ').toLowerCase();
            return haystack.includes(needle) ? 1 : 0;
          }}
        >
          <div className="flex items-center gap-2 border-b border-border px-3 py-3">
            <ScanLine className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <Command.Input
              placeholder="Search pages, actions, reports…"
              className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
              autoFocus
            />
          </div>
          <Command.List className="max-h-[60vh] overflow-y-auto px-2 py-2 text-sm">
            <Command.Empty className="py-8 text-center text-sm text-muted-foreground">
              No matches.
            </Command.Empty>
            {groups.map((group) => (
              <Command.Group
                key={group.heading}
                heading={group.heading}
                className={cn(
                  '[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2',
                  '[&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground',
                )}
              >
                {group.items.map((item) => (
                  <Command.Item
                    key={item.id}
                    value={`${group.heading} ${item.label}`}
                    keywords={item.keywords}
                    onSelect={() => runItem(item)}
                    className={cn(
                      'flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5',
                      'data-[selected=true]:bg-muted data-[selected=true]:text-foreground',
                      'aria-disabled:cursor-not-allowed aria-disabled:opacity-50',
                    )}
                  >
                    {item.icon ? (
                      <span className="shrink-0 text-muted-foreground">{item.icon}</span>
                    ) : null}
                    <span className="flex-1 truncate">{item.label}</span>
                    {item.shortcut ? (
                      <kbd className="ml-auto shrink-0 rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                        {item.shortcut}
                      </kbd>
                    ) : null}
                  </Command.Item>
                ))}
              </Command.Group>
            ))}
          </Command.List>
          <div className="flex items-center justify-between border-t border-border bg-muted/40 px-3 py-2 text-[10px] text-muted-foreground">
            <span>
              <kbd className="rounded border border-border bg-card px-1">↑ ↓</kbd> to navigate
              <span className="mx-2">·</span>
              <kbd className="rounded border border-border bg-card px-1">↵</kbd> to select
              <span className="mx-2">·</span>
              <kbd className="rounded border border-border bg-card px-1">esc</kbd> to close
            </span>
            <span>
              Open with <kbd className="rounded border border-border bg-card px-1">⌘K</kbd>
            </span>
          </div>
        </Command>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Default command palette content wired to the app's workspaces, common
 * CRUD actions, and reports. Extend or replace in `AppCommandPalette`.
 */
export function useDefaultCommandGroups(): CommandGroupDef[] {
  return [
    {
      heading: 'Workspaces',
      items: [
        { id: 'ws-control', label: 'Control Center', keywords: ['overview', 'home'], icon: <Gauge className="h-4 w-4" />, to: '/control-center' },
        { id: 'ws-dashboard', label: 'Classic Dashboard', keywords: ['kpi', 'metrics'], icon: <LayoutDashboard className="h-4 w-4" />, to: '/dashboard' },
        { id: 'ws-orders', label: 'Orders', keywords: ['jobs', 'queue'], icon: <ClipboardList className="h-4 w-4" />, shortcut: 'G O', to: '/orders' },
        { id: 'ws-sell', label: 'Sell · POS register', keywords: ['pos', 'cart', 'checkout'], icon: <Receipt className="h-4 w-4" />, shortcut: 'G S', to: '/sell' },
        { id: 'ws-stock', label: 'Stock', keywords: ['inventory', 'reconcile'], icon: <Boxes className="h-4 w-4" />, shortcut: 'G I', to: '/stock' },
        { id: 'ws-print-floor', label: 'Print Floor', keywords: ['printers', 'telemetry'], icon: <Printer className="h-4 w-4" />, shortcut: 'G P', to: '/print-floor' },
        { id: 'ws-product-studio', label: 'Product Studio', keywords: ['products', 'catalog'], icon: <Package className="h-4 w-4" />, to: '/product-studio' },
        { id: 'ws-insights', label: 'AI Insights', keywords: ['ai', 'recommendations'], icon: <Sparkles className="h-4 w-4" />, to: '/insights' },
        { id: 'ws-calculator', label: 'Cost Calculator', keywords: ['estimate'], icon: <Calculator className="h-4 w-4" />, to: '/calculator' },
      ],
    },
    {
      heading: 'Quick actions',
      items: [
        { id: 'new-job', label: 'Create new job', keywords: ['add', 'job', 'orders'], icon: <ClipboardList className="h-4 w-4" />, to: '/orders/jobs/new' },
        { id: 'new-sale', label: 'Create new sale', keywords: ['add', 'sell'], icon: <Receipt className="h-4 w-4" />, to: '/sell/sales/new' },
        { id: 'open-pos', label: 'Open POS register', keywords: ['checkout'], icon: <ScanLine className="h-4 w-4" />, to: '/sell' },
        { id: 'sales-list', label: 'View sales', icon: <ReceiptText className="h-4 w-4" />, to: '/sell/sales' },
        { id: 'customers-list', label: 'View customers', icon: <UsersRound className="h-4 w-4" />, to: '/orders/customers' },
        { id: 'products-list', label: 'View products', icon: <Box className="h-4 w-4" />, to: '/product-studio/products' },
        { id: 'materials-list', label: 'View materials', icon: <Package className="h-4 w-4" />, to: '/stock/materials' },
      ],
    },
    {
      heading: 'Reports',
      items: [
        { id: 'report-sales', label: 'Sales report', icon: <BarChart3 className="h-4 w-4" />, to: '/reports/sales' },
        { id: 'report-inventory', label: 'Inventory report', icon: <Boxes className="h-4 w-4" />, to: '/reports/inventory' },
        { id: 'report-pl', label: 'Profit & Loss', icon: <FileText className="h-4 w-4" />, to: '/reports/pl' },
      ],
    },
    {
      heading: 'Admin',
      items: [
        { id: 'admin-settings', label: 'Admin settings', icon: <Settings className="h-4 w-4" />, to: '/admin/settings' },
        { id: 'admin-users', label: 'Users', icon: <UsersRound className="h-4 w-4" />, to: '/admin/users' },
        { id: 'admin-cameras', label: 'Cameras', icon: <Camera className="h-4 w-4" />, to: '/admin/cameras' },
      ],
    },
  ];
}

/**
 * Hook that wires up the default shortcut behavior:
 * - Cmd/Ctrl + K: toggle palette
 * - `g s` / `g o` / `g p` / `g i` sequences (like Gmail / GitHub): navigate
 *   to Sell / Orders / Print Floor / Stock respectively
 *
 * Returns the `open` state + setter so the caller can mount the palette.
 */
export function useCommandPaletteShortcuts(): {
  open: boolean;
  setOpen: (open: boolean) => void;
} {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    let gPressed = false;
    let gTimeout: number | null = null;

    const clearG = () => {
      gPressed = false;
      if (gTimeout) {
        window.clearTimeout(gTimeout);
        gTimeout = null;
      }
    };

    const isTypingTarget = (target: EventTarget | null) =>
      target instanceof HTMLElement &&
      (target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.isContentEditable);

    const handleKeyDown = (event: KeyboardEvent) => {
      // Cmd/Ctrl + K toggles the palette from anywhere
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setOpen((o) => !o);
        clearG();
        return;
      }

      if (isTypingTarget(event.target)) return;

      // "g" prefix initiates a navigation sequence
      if (event.key === 'g' && !event.metaKey && !event.ctrlKey && !event.altKey) {
        gPressed = true;
        if (gTimeout) window.clearTimeout(gTimeout);
        gTimeout = window.setTimeout(clearG, 1200);
        return;
      }

      if (gPressed) {
        const dest: Record<string, string> = {
          s: '/sell',
          o: '/orders',
          p: '/print-floor',
          i: '/stock',
          c: '/control-center',
          d: '/dashboard',
        };
        const target = dest[event.key.toLowerCase()];
        if (target) {
          event.preventDefault();
          clearG();
          navigate(target);
          return;
        }
        clearG();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      clearG();
    };
  }, [navigate]);

  return { open, setOpen };
}
