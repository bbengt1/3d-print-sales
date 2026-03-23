import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { BarChart3, Package, DollarSign, TrendingUp, Layers, Award, AlertTriangle, ShoppingCart } from 'lucide-react';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import api from '@/api/client';
import { formatCurrency, formatPercent } from '@/lib/utils';
import type { DashboardSummary, FinanceDashboardSummary, RevenueDataPoint, MaterialUsageDataPoint, ProfitMarginDataPoint, InventoryAlert, SalesMetrics } from '@/types';

const COLORS = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#ddd6fe'];
const formatTooltipCurrency = (value: string | number | readonly (string | number)[] | undefined) => {
  const normalized = Array.isArray(value) ? value[0] : value;
  return formatCurrency(Number(normalized ?? 0));
};
const formatTooltipPercent = (value: string | number | readonly (string | number)[] | undefined) => {
  const normalized = Array.isArray(value) ? value[0] : value;
  return `${Number(normalized ?? 0).toFixed(1)}%`;
};

function StatCard({ icon: Icon, label, value, sub }: {
  icon: React.ElementType; label: string; value: string; sub?: string;
}) {
  return (
    <div className="bg-card border border-border rounded-lg p-6 flex items-start gap-4">
      <div className="p-3 rounded-lg bg-primary/10 text-primary">
        <Icon className="w-6 h-6" />
      </div>
      <div>
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold mt-1">{value}</p>
        {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
      </div>
    </div>
  );
}

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

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-card border border-border rounded-lg p-6 h-28 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold">Dashboard</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        <StatCard icon={BarChart3} label="Total Jobs" value={String(data.total_jobs)} />
        <StatCard icon={Package} label="Total Pieces" value={String(data.total_pieces)} />
        <StatCard icon={DollarSign} label="Total Revenue" value={formatCurrency(data.total_revenue)} />
        <StatCard icon={Layers} label="Total Costs" value={formatCurrency(data.total_costs)} />
        <StatCard icon={TrendingUp} label="Net Profit" value={formatCurrency(data.total_net_profit)}
          sub={`Avg margin: ${formatPercent(data.avg_margin_pct)}`} />
        <StatCard icon={Award} label="Top Material" value={data.top_material || 'N/A'}
          sub={`Avg profit/piece: ${formatCurrency(data.avg_profit_per_piece)}`} />
      </div>

      {/* Inventory Alerts */}
      {alerts && alerts.length > 0 && (
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400" />
            <h3 className="font-semibold text-amber-800 dark:text-amber-300">Low Stock Alerts</h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {alerts.map((a) => (
              <Link
                key={`${a.type}-${a.id}`}
                to={a.type === 'product' ? `/products/${a.id}` : '/materials'}
                className="flex items-center justify-between bg-white/60 dark:bg-white/5 rounded-md px-3 py-2 text-sm hover:bg-white/80 dark:hover:bg-white/10 transition-colors"
              >
                <div>
                  <p className="font-medium">{a.name}</p>
                  <p className="text-xs text-muted-foreground">{a.type === 'product' ? a.sku : 'Material'}</p>
                </div>
                <span className="text-amber-600 dark:text-amber-400 font-bold">{a.current_stock}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Finance Metrics */}
      {financeData && (
        <div>
          <h2 className="text-xl font-semibold mb-4">Finance Overview</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard icon={DollarSign} label="Cash on Hand" value={formatCurrency(financeData.cash_on_hand)} />
            <StatCard icon={TrendingUp} label="Current Month Net Income" value={formatCurrency(financeData.current_month_net_income)} />
            <StatCard icon={BarChart3} label="Unpaid Invoices" value={formatCurrency(financeData.unpaid_invoices)} />
            <StatCard icon={Layers} label="Unpaid Bills" value={formatCurrency(financeData.unpaid_bills)} />
            <StatCard icon={Package} label="Inventory Asset Value" value={formatCurrency(financeData.inventory_asset_value)} />
            <StatCard icon={AlertTriangle} label="Tax Payable" value={formatCurrency(financeData.tax_payable)} />
            <StatCard icon={ShoppingCart} label="Payouts in Transit" value={formatCurrency(financeData.payouts_in_transit)} />
          </div>
        </div>
      )}

      {/* Sales Metrics */}
      {salesMetrics && salesMetrics.total_sales > 0 && (
        <div>
          <h2 className="text-xl font-semibold mb-4">Sales Overview</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <StatCard icon={ShoppingCart} label="Total Orders" value={String(salesMetrics.total_sales)} />
            <StatCard icon={DollarSign} label="Gross Sales" value={formatCurrency(salesMetrics.gross_sales)} />
            <StatCard icon={Layers} label="Item COGS" value={formatCurrency(salesMetrics.item_cogs)} />
            <StatCard icon={TrendingUp} label="Gross Profit" value={formatCurrency(salesMetrics.gross_profit)} />
            <StatCard icon={DollarSign} label="Platform Fees + Shipping" value={formatCurrency(salesMetrics.platform_fees + salesMetrics.shipping_costs)} />
            <StatCard icon={BarChart3} label="Contribution Margin" value={formatCurrency(salesMetrics.contribution_margin)}
              sub={salesMetrics.refund_count > 0 ? `${salesMetrics.refund_count} refund(s)` : 'Net profit pending overhead allocation'} />
          </div>
          {salesMetrics.revenue_by_channel.length > 1 && (
            <div className="mt-4 bg-card border border-border rounded-lg p-6">
              <h3 className="text-lg font-semibold mb-4">Revenue by Channel</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={salesMetrics.revenue_by_channel}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="channel_name" tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" />
                  <YAxis tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" tickFormatter={(v) => `$${v}`} />
                  <Tooltip formatter={formatTooltipCurrency} contentStyle={{ backgroundColor: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }} />
                  <Bar dataKey="gross_sales" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue Over Time */}
        <div className="bg-card border border-border rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Revenue Over Time</h3>
          {revenueData && revenueData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={revenueData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" />
                <YAxis tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" tickFormatter={(v) => `$${v}`} />
                <Tooltip formatter={formatTooltipCurrency} contentStyle={{ backgroundColor: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }} />
                <Line type="monotone" dataKey="revenue" stroke="var(--color-primary)" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-muted-foreground text-sm py-12 text-center">No revenue data yet</p>
          )}
        </div>

        {/* Material Usage */}
        <div className="bg-card border border-border rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Material Usage</h3>
          {materialData && materialData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={materialData} dataKey="count" nameKey="material" cx="50%" cy="50%" outerRadius={100} label={(props) => `${String(props.name ?? '')} (${String(props.value ?? 0)})`}>
                  {materialData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-muted-foreground text-sm py-12 text-center">No material data yet</p>
          )}
        </div>

        {/* Profit Margins */}
        <div className="bg-card border border-border rounded-lg p-6 lg:col-span-2">
          <h3 className="text-lg font-semibold mb-4">Profit Margin by Job</h3>
          {marginData && marginData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={marginData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="product" tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" />
                <YAxis tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" tickFormatter={(v) => `${v}%`} />
                <Tooltip formatter={formatTooltipPercent} contentStyle={{ backgroundColor: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }} />
                <Bar dataKey="margin" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-muted-foreground text-sm py-12 text-center">No margin data yet</p>
          )}
        </div>
      </div>
    </div>
  );
}
