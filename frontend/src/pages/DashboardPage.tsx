import { useQuery } from '@tanstack/react-query';
import { BarChart3, Package, DollarSign, TrendingUp, Layers, Award } from 'lucide-react';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import api from '@/api/client';
import { formatCurrency, formatPercent } from '@/lib/utils';
import type { DashboardSummary, RevenueDataPoint, MaterialUsageDataPoint, ProfitMarginDataPoint } from '@/types';

const COLORS = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#ddd6fe'];

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

  const { data: materialData } = useQuery<MaterialUsageDataPoint[]>({
    queryKey: ['dashboard', 'materials'],
    queryFn: () => api.get('/dashboard/charts/materials').then((r) => r.data),
  });

  const { data: marginData } = useQuery<ProfitMarginDataPoint[]>({
    queryKey: ['dashboard', 'margins'],
    queryFn: () => api.get('/dashboard/charts/profit-margins').then((r) => r.data),
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
                <Tooltip formatter={(v: number) => formatCurrency(v)} contentStyle={{ backgroundColor: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }} />
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
                <Pie data={materialData} dataKey="count" nameKey="material" cx="50%" cy="50%" outerRadius={100} label={({ material, count }) => `${material} (${count})`}>
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
                <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} contentStyle={{ backgroundColor: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }} />
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
