import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowRight, Package } from 'lucide-react';
import api from '@/api/client';
import PrinterThumbnail from '@/components/printers/PrinterThumbnail';
import PageHeader from '@/components/layout/PageHeader';
import { KPI, KPIStrip } from '@/components/layout/KPIStrip';
import { Button } from '@/components/ui/Button';
import { Callout, calloutToneClasses } from '@/components/ui/Callout';
import EmptyState from '@/components/ui/EmptyState';
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
    admin: 'Monitor urgent exceptions first, then scan revenue, inventory value, and production risk.',
    cashier: 'Keep checkout moving, watch stock blockers, and stay close to the POS lane.',
    floor: 'Spot machine exceptions, draft jobs needing assignment, and printing progress.',
    inventory: 'Prioritize stock blockers, reconciliation pressure, and products below reorder points.',
    general: 'Start from urgent work, then move into the workspace for your next task.',
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

  const needsAttentionCount = attentionPrinters.length + blockerAlerts.length;

  return (
    <div className="space-y-6">
      <PageHeader
        title={roleHeadline || 'Control Center'}
        description={roleDescription}
        actions={
          <>
            {quickActions.map((action) => (
              <Button key={action.to} asChild>
                <Link to={action.to}>{action.label}</Link>
              </Button>
            ))}
            <Button asChild variant="outline">
              <Link to="/dashboard">Classic Dashboard</Link>
            </Button>
          </>
        }
      >
        <KPIStrip columns={4}>
          <KPI
            label="Needs attention"
            value={needsAttentionCount}
            sub={`${attentionPrinters.length} printers • ${blockerAlerts.length} stock blockers`}
            tone={needsAttentionCount > 0 ? 'warning' : 'success'}
          />
          <KPI
            label="Draft queue"
            value={unassignedDraftJobs.length}
            sub="Draft jobs without printer"
            tone={unassignedDraftJobs.length > 0 ? 'warning' : 'default'}
          />
          <KPI
            label="Printing now"
            value={busyPrinters.length}
            sub={`${printers.length} active printers in view`}
            tone={busyPrinters.length > 0 ? 'success' : 'default'}
          />
          <KPI
            label="Low-stock blockers"
            value={alerts.length}
            sub={alerts.length ? 'Below reorder point' : 'No blockers'}
            tone={alerts.length ? 'warning' : 'success'}
          />
        </KPIStrip>
      </PageHeader>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <div className="space-y-6">
          {(roleMode === 'floor' || roleMode === 'admin' || roleMode === 'general') && (() => {
            const content = (
              <>
                <div className="flex items-start justify-between gap-3">
                  <h2 className="text-base font-semibold">Print-floor priorities</h2>
                  <Button asChild variant="outline" size="sm">
                    <Link to="/print-floor">
                      Open Print Floor <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </Button>
                </div>
                {!printers.length ? (
                  <EmptyState compact icon="printers" title="No active printers are available." />
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
                              ? calloutToneClasses.warning
                              : 'border-border bg-background hover:bg-muted'
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
                                <p className="truncate text-xs capitalize text-muted-foreground">
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
              </>
            );
            return attentionPrinters.length > 0 ? (
              <Callout tone="warning"><div className="space-y-4">{content}</div></Callout>
            ) : (
              <section className="rounded-md border border-border bg-card p-5 shadow-xs space-y-4">{content}</section>
            );
          })()}

          {(roleMode === 'cashier' || roleMode === 'admin' || roleMode === 'general') && (
            <section className="rounded-md border border-border bg-card p-5 shadow-xs space-y-4">
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-base font-semibold">Retail and sales pulse</h2>
                <Button asChild variant="outline" size="sm">
                  <Link to="/sell">
                    Open Sell Workspace <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </Button>
              </div>
              {salesMetrics ? (
                <KPIStrip columns={3}>
                  <KPI
                    label="Orders"
                    value={salesMetrics.total_sales}
                    sub={`${salesMetrics.total_units_sold} units sold`}
                  />
                  <KPI
                    label="Contribution"
                    value={formatCurrency(salesMetrics.contribution_margin)}
                    sub={
                      salesMetrics.refund_count > 0
                        ? `${salesMetrics.refund_count} refunds • ${formatPercent(salesMetrics.refund_rate)} rate`
                        : 'No refunds recorded'
                    }
                    tone={salesMetrics.refund_count > 0 ? 'warning' : 'default'}
                  />
                  <KPI
                    label="Avg order"
                    value={formatCurrency(salesMetrics.avg_order_value)}
                    sub={
                      salesMetrics.payment_method_breakdown[0]
                        ? `Top method ${salesMetrics.payment_method_breakdown[0].payment_method}`
                        : 'Payment mix unavailable'
                    }
                  />
                </KPIStrip>
              ) : (
                <p className="text-sm text-muted-foreground">Sales metrics are unavailable.</p>
              )}
            </section>
          )}

          {(roleMode === 'inventory' || roleMode === 'admin' || roleMode === 'general') && (() => {
            const content = (
              <>
                <div className="flex items-start justify-between gap-3">
                  <h2 className="text-base font-semibold">Stock blockers</h2>
                  <Button asChild variant="outline" size="sm">
                    <Link to="/stock">
                      Open Stock Workspace <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </Button>
                </div>
                {!blockerAlerts.length ? (
                  <p className="text-sm text-muted-foreground">No low-stock blockers are currently open.</p>
                ) : (
                  <div className="grid gap-3 md:grid-cols-2">
                    {blockerAlerts.map((alert) => (
                      <Link
                        key={`${alert.type}-${alert.id}`}
                        to={alert.type === 'product' ? `/product-studio/products/${alert.id}` : '/stock/materials'}
                        className="flex items-center justify-between rounded-md border border-border bg-background px-4 py-3 text-sm no-underline transition-colors hover:bg-muted"
                      >
                        <div className="min-w-0">
                          <p className="truncate font-medium text-foreground">{alert.name}</p>
                          <p className="truncate text-xs text-muted-foreground">
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
              </>
            );
            return blockerAlerts.length > 0 ? (
              <Callout tone="warning"><div className="space-y-4">{content}</div></Callout>
            ) : (
              <section className="rounded-md border border-border bg-card p-5 shadow-xs space-y-4">{content}</section>
            );
          })()}
        </div>

        <div className="space-y-6">
          {(() => {
            const hasAttention = attentionPrinters.length + unassignedDraftJobs.length + blockerAlerts.length > 0;
            const content = (
              <>
                <h2 className="text-base font-semibold">Needs attention now</h2>
                <ul className="space-y-3">
                  <li className="flex items-start gap-3">
                    <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
                    <div className="min-w-0">
                      <p className="font-medium text-foreground">Printers needing attention</p>
                      <p className="text-sm text-muted-foreground">
                        {attentionPrinters.length
                          ? `${attentionPrinters.length} printers are paused, offline, or in error.`
                          : 'No printer exceptions currently open.'}
                      </p>
                    </div>
                  </li>
                  <li className="flex items-start gap-3">
                    <Package className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                    <div className="min-w-0">
                      <p className="font-medium text-foreground">Draft jobs needing assignment</p>
                      <p className="text-sm text-muted-foreground">
                        {unassignedDraftJobs.length
                          ? `${unassignedDraftJobs.length} draft jobs are still missing a printer.`
                          : 'No unassigned draft jobs.'}
                      </p>
                    </div>
                  </li>
                </ul>
              </>
            );
            return hasAttention ? (
              <Callout tone="warning"><div className="space-y-4">{content}</div></Callout>
            ) : (
              <section className="rounded-md border border-border bg-card p-5 shadow-xs space-y-4">{content}</section>
            );
          })()}

          <section className="rounded-md border border-border bg-card p-5 shadow-xs space-y-4">
            <h2 className="text-base font-semibold">Business pulse</h2>
            <KPIStrip columns={2}>
              <KPI
                label="Revenue"
                value={summary ? formatCurrency(summary.total_revenue) : '—'}
                sub={summary ? `${summary.total_jobs} jobs • ${summary.total_pieces} pieces` : 'Dashboard summary unavailable'}
              />
              <KPI
                label="Net profit"
                value={summary ? formatCurrency(summary.total_net_profit) : '—'}
                sub={summary ? `Avg margin ${formatPercent(summary.avg_margin_pct)}` : 'Margin unavailable'}
              />
            </KPIStrip>
            {financeData ? (
              <div className="rounded-md border border-border bg-background p-4">
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
          </section>
        </div>
      </div>
    </div>
  );
}
