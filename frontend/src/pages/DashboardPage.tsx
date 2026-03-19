import { useQuery } from '@tanstack/react-query';
import { BarChart3, Package, DollarSign, TrendingUp, Layers, Award } from 'lucide-react';
import api from '@/api/client';
import { formatCurrency, formatPercent } from '@/lib/utils';
import type { DashboardSummary } from '@/types';

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

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-card border border-border rounded-lg p-6 h-28 animate-pulse" />
        ))}
      </div>
    );
  }

  if (!data) return null;

  return (
    <div>
      <h1 className="text-3xl font-bold mb-8">Dashboard</h1>
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
    </div>
  );
}
