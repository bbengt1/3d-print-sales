import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  Award,
  BarChart3,
  DollarSign,
  Layers,
  Package,
  ShoppingCart,
  TrendingUp,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from 'recharts';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import { KPI, KPIStrip } from '@/components/layout/KPIStrip';
import { ChartTooltip, chartCategoricalPalette } from '@/components/charts/ChartTooltip';
import EmptyState from '@/components/ui/EmptyState';
import { Callout } from '@/components/ui/Callout';
import { SkeletonCard } from '@/components/ui/Skeleton';
import PrinterThumbnail from '@/components/printers/PrinterThumbnail';
import { formatCurrency, formatPercent } from '@/lib/utils';
import type {
  DashboardSummary,
  FinanceDashboardSummary,
  InventoryAlert,
  MaterialUsageDataPoint,
  PaginatedPrinters,
  Printer,
  ProfitMarginDataPoint,
  RevenueDataPoint,
  SalesMetrics,
} from '@/types';

const formatTooltipCurrency = (value: string | number | readonly (string | number)[] | undefined) => {
  const normalized = Array.isArray(value) ? value[0] : value;
  return formatCurrency(Number(normalized ?? 0));
};
const formatTooltipPercent = (value: string | number | readonly (string | number)[] | undefined) => {
  const normalized = Array.isArray(value) ? value[0] : value;
  return `${Number(normalized ?? 0).toFixed(1)}%`;
};
const formatDuration = (seconds: number | null | undefined) => {
  if (seconds == null || Number.isNaN(seconds)) return '—';
  const total = Math.max(0, Math.round(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
};
const formatLayer = (printer: Printer) => {
  if (printer.monitor_current_layer == null && printer.monitor_total_layers == null) return '—';
  if (printer.monitor_current_layer != null && printer.monitor_total_layers != null)
    return `${printer.monitor_current_layer}/${printer.monitor_total_layers}`;
  return String(printer.monitor_current_layer ?? printer.monitor_total_layers ?? '—');
};

export default function DashboardPage() {
  const { data, isLoading } = useQuery<DashboardSummary>({
    queryKey: ['dashboard'],
    queryFn: () => api.get('/dashboard/summary').then((r) => r.data),
  });

  const { data: revenueData } = useQuery<RevenueDataPoint[]>({
    queryKey: ['dashboard', 'revenue'],
    queryFn: () => api.get('/dashboard/charts/revenue').then((r) => r.data),
  });

  const { data: financeData } = useQuery<FinanceDashboardSummary>({
    queryKey: ['dashboard', 'finance-summary'],
    queryFn: () => api.get('/dashboard/finance-summary').then((r) => r.data),
  });

  const { data: materialData } = useQuery<MaterialUsageDataPoint[]>({
    queryKey: ['dashboard', 'materials'],
    queryFn: () => api.get('/dashboard/charts/materials').then((r) => r.data),
  });

  const { data: marginData } = useQuery<ProfitMarginDataPoint[]>({
    queryKey: ['dashboard', 'margins'],
    queryFn: () => api.get('/dashboard/charts/profit-margins').then((r) => r.data),
  });

  const { data: alerts } = useQuery<InventoryAlert[]>({
    queryKey: ['inventory', 'alerts'],
    queryFn: () => api.get('/inventory/alerts').then((r) => r.data),
  });

  const { data: salesMetrics } = useQuery<SalesMetrics>({
    queryKey: ['sales', 'metrics'],
    queryFn: () => api.get('/sales/metrics').then((r) => r.data),
  });

  const { data: printersData } = useQuery<PaginatedPrinters>({
    queryKey: ['dashboard', 'printers-live'],
    queryFn: () => api.get('/printers', { params: { is_active: true, limit: 6 } }).then((r) => r.data),
    refetchInterval: 10000,
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Dashboard" description="Live snapshot of jobs, revenue, inventory, and printers." />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} rows={1} />
          ))}
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Live snapshot of jobs, revenue, inventory, and printers."
      />

      <KPIStrip columns={3}>
        <KPI icon={<BarChart3 className="h-4 w-4" />} label="Total jobs" value={data.total_jobs.toLocaleString()} href="/orders/jobs" />
        <KPI icon={<Package className="h-4 w-4" />} label="Total pieces" value={data.total_pieces.toLocaleString()} href="/orders/jobs" />
        <KPI
          icon={<DollarSign className="h-4 w-4" />}
          label="Total revenue"
          value={formatCurrency(data.total_revenue)}
          href="/sell/sales"
          sparkline={revenueData?.map((d) => d.revenue) || []}
        />
        <KPI icon={<Layers className="h-4 w-4" />} label="Total costs" value={formatCurrency(data.total_costs)} href="/reports/pl" />
        <KPI
          icon={<TrendingUp className="h-4 w-4" />}
          label="Net profit"
          value={formatCurrency(data.total_net_profit)}
          sub={`Avg margin ${formatPercent(data.avg_margin_pct)}`}
          tone={data.total_net_profit >= 0 ? 'success' : 'destructive'}
          href="/reports/pl"
        />
        <KPI
          icon={<Award className="h-4 w-4" />}
          label="Top material"
          value={data.top_material || '—'}
          sub={`Avg profit/piece ${formatCurrency(data.avg_profit_per_piece)}`}
          href="/stock/materials"
        />
      </KPIStrip>

      {/* Inventory Alerts */}
      {alerts && alerts.length > 0 ? (
        <Callout
          tone="warning"
          icon={<AlertTriangle className="h-4 w-4" aria-hidden="true" />}
          title="Low stock alerts"
        >
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {alerts.map((a) => (
              <Link
                key={`${a.type}-${a.id}`}
                to={a.type === 'product' ? `/products/${a.id}` : '/materials'}
                className="flex items-center justify-between rounded-md bg-card px-3 py-2 text-sm no-underline transition-colors hover:bg-muted"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-foreground">{a.name}</p>
                  <p className="truncate text-xs text-muted-foreground">{a.type === 'product' ? a.sku : 'Material'}</p>
                </div>
                <span className="shrink-0 font-semibold tabular-nums text-amber-700 dark:text-amber-300">
                  {a.current_stock}
                </span>
              </Link>
            ))}
          </div>
        </Callout>
      ) : null}

      {printersData?.items?.length ? (
        <section className="rounded-md border border-border bg-card p-6 shadow-xs">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold">Printer live board</h2>
              <p className="mt-0.5 text-sm text-muted-foreground">
                Monitored printers, progress, layers, ETA, and Moonraker socket freshness.
              </p>
            </div>
            <Link to="/printers" className="text-sm text-primary no-underline hover:underline">
              Open printers
            </Link>
          </div>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
            {printersData.items.map((printer) => (
              <Link
                key={printer.id}
                to={`/printers/${printer.id}`}
                className="rounded-md border border-border bg-background p-4 no-underline transition-colors hover:bg-muted"
              >
                <div className="flex gap-3">
                  <PrinterThumbnail
                    src={printer.current_print_thumbnail_url}
                    alt={printer.current_print_name ? `${printer.current_print_name} thumbnail` : `${printer.name} current print thumbnail`}
                    className="h-24 w-24 shrink-0"
                    imgClassName="object-cover"
                    fallbackLabel="No thumb"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate font-semibold text-foreground">{printer.name}</p>
                        <p
                          className="truncate text-xs text-muted-foreground"
                          title={`${printer.monitor_provider || 'static'} · ${printer.monitor_status || printer.status}`}
                        >
                          {printer.monitor_provider || 'static'} · {printer.monitor_status || printer.status}
                        </p>
                      </div>
                      <span className="text-sm font-semibold tabular-nums text-foreground">
                        {printer.monitor_progress_percent != null ? `${printer.monitor_progress_percent.toFixed(0)}%` : '—'}
                      </span>
                    </div>
                    <div className="mt-3 space-y-1 text-sm text-muted-foreground">
                      <p className="truncate" title={printer.current_print_name || 'No active file'}>
                        {printer.current_print_name || 'No active file'}
                      </p>
                      <p
                        className="truncate"
                        title={`Layer ${formatLayer(printer)} · Remaining ${formatDuration(printer.monitor_remaining_seconds)}`}
                      >
                        Layer {formatLayer(printer)} · Remaining {formatDuration(printer.monitor_remaining_seconds)}
                      </p>
                      <p
                        className="truncate"
                        title={
                          printer.monitor_provider === 'moonraker'
                            ? printer.monitor_ws_connected
                              ? 'WebSocket live'
                              : 'Polling fallback'
                            : 'HTTP polling / static'
                        }
                      >
                        {printer.monitor_provider === 'moonraker'
                          ? printer.monitor_ws_connected
                            ? 'WebSocket live'
                            : 'Polling fallback'
                          : 'HTTP polling / static'}
                      </p>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      {/* Finance Metrics */}
      {financeData ? (
        <section>
          <h2 className="mb-3 text-base font-semibold">Finance overview</h2>
          <KPIStrip columns={4}>
            <KPI icon={<DollarSign className="h-4 w-4" />} label="Cash on hand" value={formatCurrency(financeData.cash_on_hand)} href="/reports/pl" />
            <KPI
              icon={<TrendingUp className="h-4 w-4" />}
              label="Month net income"
              value={formatCurrency(financeData.current_month_net_income)}
              tone={financeData.current_month_net_income >= 0 ? 'success' : 'destructive'}
              href="/reports/pl"
            />
            <KPI icon={<BarChart3 className="h-4 w-4" />} label="Unpaid invoices" value={formatCurrency(financeData.unpaid_invoices)} href="/sell/sales" />
            <KPI icon={<Layers className="h-4 w-4" />} label="Unpaid bills" value={formatCurrency(financeData.unpaid_bills)} />
            <KPI icon={<Package className="h-4 w-4" />} label="Inventory asset value" value={formatCurrency(financeData.inventory_asset_value)} href="/stock" />
            <KPI
              icon={<AlertTriangle className="h-4 w-4" />}
              label="Tax payable"
              value={formatCurrency(financeData.tax_payable)}
              tone={financeData.tax_payable > 0 ? 'warning' : 'default'}
            />
            <KPI icon={<ShoppingCart className="h-4 w-4" />} label="Payouts in transit" value={formatCurrency(financeData.payouts_in_transit)} />
          </KPIStrip>
        </section>
      ) : null}

      {/* Sales Metrics */}
      {salesMetrics && salesMetrics.total_sales > 0 ? (
        <section>
          <h2 className="mb-3 text-base font-semibold">Sales overview</h2>
          <KPIStrip columns={3}>
            <KPI icon={<ShoppingCart className="h-4 w-4" />} label="Total orders" value={salesMetrics.total_sales.toLocaleString()} href="/sell/sales" />
            <KPI icon={<DollarSign className="h-4 w-4" />} label="Gross sales" value={formatCurrency(salesMetrics.gross_sales)} href="/sell/sales" />
            <KPI icon={<Layers className="h-4 w-4" />} label="Item COGS" value={formatCurrency(salesMetrics.item_cogs)} href="/reports/pl" />
            <KPI
              icon={<TrendingUp className="h-4 w-4" />}
              label="Gross profit"
              value={formatCurrency(salesMetrics.gross_profit)}
              tone={salesMetrics.gross_profit >= 0 ? 'success' : 'destructive'}
              href="/reports/pl"
            />
            <KPI
              icon={<DollarSign className="h-4 w-4" />}
              label="Platform fees + shipping"
              value={formatCurrency(salesMetrics.platform_fees + salesMetrics.shipping_costs)}
              href="/reports/sales"
            />
            <KPI
              icon={<BarChart3 className="h-4 w-4" />}
              label="Contribution margin"
              value={formatCurrency(salesMetrics.contribution_margin)}
              sub={salesMetrics.refund_count > 0 ? `${salesMetrics.refund_count} refund(s)` : 'Net pending overhead allocation'}
              href="/reports/pl"
            />
          </KPIStrip>

          {salesMetrics.revenue_by_channel.length > 1 ? (
            <div className="mt-4 rounded-md border border-border bg-card p-6 shadow-xs">
              <h3 className="mb-4 text-base font-semibold">Revenue by channel</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={salesMetrics.revenue_by_channel}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="channel_name" tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" />
                  <YAxis tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" tickFormatter={(v) => `$${v}`} />
                  <ChartTooltip formatter={formatTooltipCurrency} />
                  <Bar dataKey="gross_sales" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Revenue Over Time */}
        <div className="rounded-md border border-border bg-card p-6 shadow-xs">
          <h3 className="mb-4 text-base font-semibold">Revenue over time</h3>
          {revenueData && revenueData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={revenueData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" />
                <YAxis tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" tickFormatter={(v) => `$${v}`} />
                <ChartTooltip formatter={formatTooltipCurrency} />
                <Line type="monotone" dataKey="revenue" stroke="var(--color-primary)" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState
              icon="reports"
              title="No revenue data yet"
              description="Complete a sale to populate this chart."
            />
          )}
        </div>

        {/* Material Usage */}
        <div className="rounded-md border border-border bg-card p-6 shadow-xs">
          <h3 className="mb-4 text-base font-semibold">Material usage</h3>
          {materialData && materialData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={materialData}
                  dataKey="count"
                  nameKey="material"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label={(props) => `${String(props.name ?? '')} (${String(props.value ?? 0)})`}
                >
                  {materialData.map((_, i) => (
                    <Cell key={i} fill={chartCategoricalPalette[i % chartCategoricalPalette.length]} />
                  ))}
                </Pie>
                <ChartTooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState
              icon="materials"
              title="No material data yet"
              description="Log a job to see material usage distribution."
            />
          )}
        </div>

        {/* Profit Margins */}
        <div className="rounded-md border border-border bg-card p-6 shadow-xs lg:col-span-2">
          <h3 className="mb-4 text-base font-semibold">Profit margin by job</h3>
          {marginData && marginData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={marginData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="product" tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" />
                <YAxis tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" tickFormatter={(v) => `${v}%`} />
                <ChartTooltip formatter={formatTooltipPercent} />
                <Bar dataKey="margin" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState
              icon="reports"
              title="No margin data yet"
              description="Complete jobs with cost + price data to see per-job profitability."
            />
          )}
        </div>
      </div>
    </div>
  );
}
