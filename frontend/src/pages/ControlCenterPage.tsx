import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Boxes,
  ClipboardList,
  DollarSign,
  Package,
  Printer,
  Receipt,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import api from '@/api/client';
import PrinterThumbnail from '@/components/printers/PrinterThumbnail';
import { useAuthStore } from '@/store/auth';
import { cn, formatCurrency, formatPercent } from '@/lib/utils';
import type {
  DashboardSummary,
  FinanceDashboardSummary,
  InventoryAlert,
  PaginatedJobs,
  PaginatedPrinters,
  Printer as PrinterType,
  SalesMetrics,
} from '@/types';

const ATTENTION_STATUSES = new Set(['paused', 'maintenance', 'offline', 'error']);

type ControlCenterRole = 'admin' | 'cashier' | 'floor' | 'inventory' | 'general';

function getControlCenterRole(role: string | null | undefined): ControlCenterRole {
  const value = (role || '').trim().toLowerCase();
  if (value === 'admin' || value === 'owner' || value === 'finance') return 'admin';
  if (['cashier', 'sales', 'retail'].includes(value)) return 'cashier';
  if (['floor', 'operator', 'printer_operator', 'production'].includes(value)) return 'floor';
  if (['inventory', 'warehouse'].includes(value)) return 'inventory';
  return 'general';
}

function formatDuration(seconds: number | null | undefined) {
  if (seconds == null || Number.isNaN(seconds)) return '—';
  const total = Math.max(0, Math.round(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function formatLayer(printer: PrinterType) {
  if (printer.monitor_current_layer == null && printer.monitor_total_layers == null) return '—';
  if (printer.monitor_current_layer != null && printer.monitor_total_layers != null) {
    return `${printer.monitor_current_layer}/${printer.monitor_total_layers}`;
  }
  return String(printer.monitor_current_layer ?? printer.monitor_total_layers ?? '—');
}

function ModuleCard({
  title,
  description,
  action,
  children,
  tone = 'default',
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  tone?: 'default' | 'warning' | 'success';
}) {
  return (
    <section
      className={cn(
        'rounded-lg border p-5 shadow-md backdrop-blur',
        tone === 'warning' && 'border-amber-300/60 bg-amber-50/90 dark:border-amber-500/30 dark:bg-amber-500/10',
        tone === 'success' && 'border-emerald-300/60 bg-emerald-50/90 dark:border-emerald-500/30 dark:bg-emerald-500/10',
        tone === 'default' && 'border-border bg-card/85'
      )}
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-foreground">{title}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function PriorityStat({
  icon: Icon,
  label,
  value,
  subtext,
  emphasis = 'default',
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  subtext?: string;
  emphasis?: 'default' | 'warning' | 'success';
}) {
  return (
    <div className="rounded-md border border-border bg-card/80 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            {label}
          </p>
          <p
            className={cn(
              'mt-3 text-3xl font-semibold',
              emphasis === 'warning' && 'text-amber-600 dark:text-amber-300',
              emphasis === 'success' && 'text-emerald-600 dark:text-emerald-300',
              emphasis === 'default' && 'text-foreground'
            )}
          >
            {value}
          </p>
          {subtext ? <p className="mt-1 text-sm text-muted-foreground">{subtext}</p> : null}
        </div>
        <div className="flex h-11 w-11 items-center justify-center rounded-md bg-primary/12 text-primary">
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

function ActionLink({ to, label }: { to: string; label: string }) {
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-2 rounded-full border border-border bg-background/70 px-4 py-2 text-sm font-medium text-foreground no-underline transition-colors hover:border-primary/30 hover:text-primary"
    >
      {label}
      <ArrowRight className="h-4 w-4" />
    </Link>
  );
}

export default function ControlCenterPage() {
  const { user } = useAuthStore();
  const roleMode = getControlCenterRole(user?.role);

  const { data: summary } = useQuery<DashboardSummary>({
    queryKey: ['dashboard'],
    queryFn: () => api.get('/dashboard/summary').then((r) => r.data),
  });

  const { data: financeData } = useQuery<FinanceDashboardSummary>({
    queryKey: ['dashboard', 'finance-summary'],
    queryFn: () => api.get('/dashboard/finance-summary').then((r) => r.data),
  });

  const { data: alerts = [] } = useQuery<InventoryAlert[]>({
    queryKey: ['inventory', 'alerts'],
    queryFn: () => api.get('/inventory/alerts').then((r) => r.data),
  });

  const { data: salesMetrics } = useQuery<SalesMetrics>({
    queryKey: ['sales', 'metrics'],
    queryFn: () => api.get('/sales/metrics').then((r) => r.data),
  });

  const { data: printersData } = useQuery<PaginatedPrinters>({
    queryKey: ['dashboard', 'printers-live'],
    queryFn: () => api.get('/printers', { params: { is_active: true, limit: 8 } }).then((r) => r.data),
    refetchInterval: 10000,
  });

  const { data: draftJobsData } = useQuery<PaginatedJobs>({
    queryKey: ['jobs', 'control-center-drafts'],
    queryFn: () => api.get('/jobs', { params: { status: 'draft', limit: 12 } }).then((r) => r.data),
  });

  const printers = printersData?.items || [];
  const draftJobs = draftJobsData?.items || [];

  const attentionPrinters = useMemo(
    () => printers.filter((printer) => ATTENTION_STATUSES.has(printer.monitor_status || printer.status)),
    [printers]
  );

  const busyPrinters = useMemo(
    () => printers.filter((printer) => (printer.monitor_status || printer.status) === 'printing'),
    [printers]
  );

  const unassignedDraftJobs = useMemo(
    () => draftJobs.filter((job) => !job.printer_id),
    [draftJobs]
  );

  const blockerAlerts = alerts.slice(0, 6);
  const roleHeadline = {
    admin: 'Owner and admin focus',
    cashier: 'Cashier focus',
    floor: 'Print-floor focus',
    inventory: 'Inventory focus',
    general: 'Operations focus',
  }[roleMode];

  const roleDescription = {
    admin: 'Monitor urgent exceptions first, then scan revenue, inventory value, and open production risk.',
    cashier: 'Keep checkout moving, watch stock blockers, and stay close to the POS lane.',
    floor: 'Use this page to spot machine exceptions, draft jobs needing assignment, and printing progress.',
    inventory: 'Prioritize stock blockers, reconciliation pressure, and products drifting below reorder points.',
    general: 'Start from urgent work, then move into the workspace that matches your next task.',
  }[roleMode];

  const quickActions = {
    admin: [
      { to: '/print-floor', label: 'Open Print Floor' },
      { to: '/sell', label: 'Open Sell Workspace' },
      { to: '/stock', label: 'Open Stock Workspace' },
    ],
    cashier: [
      { to: '/sell', label: 'Open POS Register' },
      { to: '/sell/sales', label: 'Review Sales' },
      { to: '/orders/customers', label: 'Customers' },
    ],
    floor: [
      { to: '/print-floor', label: 'Open Printer Wall' },
      { to: '/orders', label: 'Review Draft Jobs' },
      { to: '/stock', label: 'Check Stock Risk' },
    ],
    inventory: [
      { to: '/stock', label: 'Open Stock Workspace' },
      { to: '/stock/materials', label: 'Review Materials' },
      { to: '/product-studio', label: 'Review Products' },
    ],
    general: [
      { to: '/print-floor', label: 'Print Floor' },
      { to: '/sell', label: 'Sell' },
      { to: '/stock', label: 'Stock' },
    ],
  }[roleMode];

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-lg border border-border bg-[linear-gradient(135deg,rgba(8,17,31,0.98),rgba(17,34,53,0.96))] px-6 py-6 text-white shadow-md">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.32em] text-cyan-200/75">
              {roleHeadline}
            </p>
            <h1 className="mt-3 text-3xl font-semibold md:text-4xl">
              Control Center
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-200/82 md:text-base">
              {roleDescription}
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              {quickActions.map((action) => (
                <Link
                  key={action.to}
                  to={action.to}
                  className="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground no-underline shadow-sm transition-transform hover:-translate-y-0.5"
                >
                  {action.label}
                </Link>
              ))}
              <Link
                to="/dashboard"
                className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/8 px-4 py-2 text-sm font-medium text-white no-underline transition-colors hover:bg-white/12"
              >
                Classic Dashboard
              </Link>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
            <PriorityStat
              icon={AlertTriangle}
              label="Needs Attention"
              value={String(attentionPrinters.length + blockerAlerts.length)}
              subtext={`${attentionPrinters.length} printers • ${blockerAlerts.length} stock blockers`}
              emphasis={attentionPrinters.length + blockerAlerts.length > 0 ? 'warning' : 'success'}
            />
            <PriorityStat
              icon={ClipboardList}
              label="Draft Queue"
              value={String(unassignedDraftJobs.length)}
              subtext="Draft jobs without printer assignment"
              emphasis={unassignedDraftJobs.length > 0 ? 'warning' : 'default'}
            />
          </div>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
        <PriorityStat
          icon={Printer}
          label="Printing Now"
          value={String(busyPrinters.length)}
          subtext={`${printers.length} active printers in view`}
          emphasis={busyPrinters.length > 0 ? 'success' : 'default'}
        />
        <PriorityStat
          icon={Boxes}
          label="Low-Stock Blockers"
          value={String(alerts.length)}
          subtext={alerts.length ? 'Products or materials below reorder point' : 'No stock blockers right now'}
          emphasis={alerts.length ? 'warning' : 'success'}
        />
        <PriorityStat
          icon={Receipt}
          label="Sales Pulse"
          value={salesMetrics ? formatCurrency(salesMetrics.gross_sales) : '—'}
          subtext={salesMetrics ? `${salesMetrics.total_sales} orders • AOV ${formatCurrency(salesMetrics.avg_order_value)}` : 'Sales metrics unavailable'}
        />
        <PriorityStat
          icon={DollarSign}
          label="Business Pulse"
          value={financeData ? formatCurrency(financeData.current_month_net_income) : '—'}
          subtext={financeData ? `Inventory asset ${formatCurrency(financeData.inventory_asset_value)}` : 'Finance summary unavailable'}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <div className="space-y-6">
          {(roleMode === 'floor' || roleMode === 'admin' || roleMode === 'general') && (
            <ModuleCard
              title="Print-floor priorities"
              description="Machine conditions and print progress that need fast operational awareness."
              action={<ActionLink to="/print-floor" label="Open Print Floor" />}
              tone={attentionPrinters.length > 0 ? 'warning' : 'default'}
            >
              {!printers.length ? (
                <p className="text-sm text-muted-foreground">No active printers are available.</p>
              ) : (
                <div className="grid gap-3 lg:grid-cols-2">
                  {printers.slice(0, 4).map((printer) => {
                    const needsAttention = ATTENTION_STATUSES.has(printer.monitor_status || printer.status);
                    return (
                      <Link
                        key={printer.id}
                        to={`/print-floor/printers/${printer.id}`}
                        className={cn(
                          'grid grid-cols-[88px_minmax(0,1fr)] gap-4 rounded-md border p-3 no-underline transition-colors',
                          needsAttention
                            ? 'border-amber-300/70 bg-amber-50/80 dark:border-amber-500/30 dark:bg-amber-500/10'
                            : 'border-border bg-background/70 hover:border-primary/30'
                        )}
                      >
                        <PrinterThumbnail
                          src={printer.current_print_thumbnail_url}
                          alt={printer.current_print_name || `${printer.name} thumbnail`}
                          className="h-[88px] w-[88px] rounded-md"
                          imgClassName="object-cover"
                          fallbackLabel="No view"
                        />
                        <div className="min-w-0">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate font-semibold text-foreground">{printer.name}</p>
                              <p className="truncate text-xs uppercase tracking-[0.16em] text-muted-foreground">
                                {printer.monitor_status || printer.status}
                              </p>
                            </div>
                            <span className="text-sm font-semibold text-foreground">
                              {printer.monitor_progress_percent != null ? `${printer.monitor_progress_percent.toFixed(0)}%` : '—'}
                            </span>
                          </div>
                          <p className="mt-2 truncate text-sm text-muted-foreground">
                            {printer.current_print_name || 'No active print'}
                          </p>
                          <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                            <p>Layer {formatLayer(printer)}</p>
                            <p>ETA {formatDuration(printer.monitor_remaining_seconds)}</p>
                            <p>{printer.location || 'No bay assigned'}</p>
                            <p>{printer.monitor_ws_connected ? 'Socket live' : 'Polling'}</p>
                          </div>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              )}
            </ModuleCard>
          )}

          {(roleMode === 'cashier' || roleMode === 'admin' || roleMode === 'general') && (
            <ModuleCard
              title="Retail and sales pulse"
              description="Keep counter checkout moving and watch order mix without leaving the landing page."
              action={<ActionLink to="/sell" label="Open Sell Workspace" />}
            >
              {salesMetrics ? (
                <div className="grid gap-3 md:grid-cols-3">
                  <PriorityStat
                    icon={Receipt}
                    label="Orders"
                    value={String(salesMetrics.total_sales)}
                    subtext={`${salesMetrics.total_units_sold} units sold`}
                  />
                  <PriorityStat
                    icon={TrendingUp}
                    label="Contribution"
                    value={formatCurrency(salesMetrics.contribution_margin)}
                    subtext={
                      salesMetrics.refund_count > 0
                        ? `${salesMetrics.refund_count} refunds • ${formatPercent(salesMetrics.refund_rate)} rate`
                        : 'No refunds recorded'
                    }
                  />
                  <PriorityStat
                    icon={BarChart3}
                    label="Avg Order"
                    value={formatCurrency(salesMetrics.avg_order_value)}
                    subtext={salesMetrics.payment_method_breakdown[0] ? `Top method ${salesMetrics.payment_method_breakdown[0].payment_method}` : 'Payment mix unavailable'}
                  />
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Sales metrics are unavailable.</p>
              )}
            </ModuleCard>
          )}

          {(roleMode === 'inventory' || roleMode === 'admin' || roleMode === 'general') && (
            <ModuleCard
              title="Stock blockers"
              description="Products and materials drifting below reorder points or creating near-term operational risk."
              action={<ActionLink to="/stock" label="Open Stock Workspace" />}
              tone={blockerAlerts.length ? 'warning' : 'success'}
            >
              {!blockerAlerts.length ? (
                <p className="text-sm text-muted-foreground">No low-stock blockers are currently open.</p>
              ) : (
                <div className="grid gap-3 md:grid-cols-2">
                  {blockerAlerts.map((alert) => (
                    <Link
                      key={`${alert.type}-${alert.id}`}
                      to={alert.type === 'product' ? `/product-studio/products/${alert.id}` : '/stock/materials'}
                      className="flex items-center justify-between rounded-md border border-border bg-background/70 px-4 py-3 text-sm no-underline transition-colors hover:border-primary/30"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium text-foreground">{alert.name}</p>
                        <p className="truncate text-xs uppercase tracking-[0.14em] text-muted-foreground">
                          {alert.type === 'product' ? alert.sku || 'Product' : 'Material'}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold text-amber-600 dark:text-amber-300">{alert.current_stock}</p>
                        <p className="text-xs text-muted-foreground">reorder {alert.reorder_point}</p>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </ModuleCard>
          )}
        </div>

        <div className="space-y-6">
          <ModuleCard
            title="Needs attention now"
            description="The shortest path to urgent work across printing, stock, and queue pressure."
            tone={attentionPrinters.length + unassignedDraftJobs.length + blockerAlerts.length > 0 ? 'warning' : 'success'}
          >
            <div className="space-y-3">
              <div className="rounded-md border border-border bg-background/70 p-4">
                <div className="flex items-center gap-3">
                  <AlertTriangle className="h-5 w-5 text-amber-500" />
                  <div>
                    <p className="font-medium text-foreground">Printers needing attention</p>
                    <p className="text-sm text-muted-foreground">
                      {attentionPrinters.length ? `${attentionPrinters.length} printers are paused, offline, or in error.` : 'No printer exceptions currently open.'}
                    </p>
                  </div>
                </div>
              </div>
              <div className="rounded-md border border-border bg-background/70 p-4">
                <div className="flex items-center gap-3">
                  <Package className="h-5 w-5 text-primary" />
                  <div>
                    <p className="font-medium text-foreground">Draft jobs needing assignment</p>
                    <p className="text-sm text-muted-foreground">
                      {unassignedDraftJobs.length ? `${unassignedDraftJobs.length} draft jobs are still missing a printer.` : 'No unassigned draft jobs.'}
                    </p>
                  </div>
                </div>
              </div>
              <div className="rounded-md border border-border bg-background/70 p-4">
                <div className="flex items-center gap-3">
                  <Sparkles className="h-5 w-5 text-cyan-500" />
                  <div>
                    <p className="font-medium text-foreground">Classic metrics still available</p>
                    <p className="text-sm text-muted-foreground">
                      Jump into the previous dashboard if you need the older chart-heavy overview.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </ModuleCard>

          <ModuleCard
            title="Business pulse"
            description="A compact owner view built from the existing finance and dashboard summaries."
            action={<ActionLink to="/dashboard" label="Classic Dashboard" />}
          >
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <PriorityStat
                  icon={DollarSign}
                  label="Revenue"
                  value={summary ? formatCurrency(summary.total_revenue) : '—'}
                  subtext={summary ? `${summary.total_jobs} jobs • ${summary.total_pieces} pieces` : 'Dashboard summary unavailable'}
                />
                <PriorityStat
                  icon={TrendingUp}
                  label="Net Profit"
                  value={summary ? formatCurrency(summary.total_net_profit) : '—'}
                  subtext={summary ? `Avg margin ${formatPercent(summary.avg_margin_pct)}` : 'Margin unavailable'}
                />
              </div>
              {financeData ? (
                <div className="rounded-md border border-border bg-background/70 p-4">
                  <dl className="grid gap-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <dt className="text-muted-foreground">Inventory asset value</dt>
                      <dd className="font-medium text-foreground">{formatCurrency(financeData.inventory_asset_value)}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <dt className="text-muted-foreground">Cash on hand</dt>
                      <dd className="font-medium text-foreground">{formatCurrency(financeData.cash_on_hand)}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <dt className="text-muted-foreground">Unpaid invoices</dt>
                      <dd className="font-medium text-foreground">{formatCurrency(financeData.unpaid_invoices)}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <dt className="text-muted-foreground">Tax payable</dt>
                      <dd className="font-medium text-foreground">{formatCurrency(financeData.tax_payable)}</dd>
                    </div>
                  </dl>
                </div>
              ) : null}
            </div>
          </ModuleCard>
        </div>
      </div>
    </div>
  );
}
