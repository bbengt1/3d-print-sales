import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import api from '@/api/client';
import { formatCurrency, formatPercent } from '@/lib/utils';
import ReportControls from '@/components/ui/ReportControls';
import { SkeletonTable } from '@/components/ui/Skeleton';
import type { PLReport } from '@/types';

const formatTooltipCurrency = (value: string | number | readonly (string | number)[] | undefined) => {
  const normalized = Array.isArray(value) ? value[0] : value;
  return formatCurrency(Number(normalized ?? 0));
};

export default function PLReportPage() {
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [period, setPeriod] = useState('monthly');

  const { data, isLoading } = useQuery<PLReport>({
    queryKey: ['report', 'pl', dateFrom, dateTo, period],
    queryFn: () =>
      api
        .get('/reports/pl', {
          params: {
            date_from: dateFrom || undefined,
            date_to: dateTo || undefined,
            period,
          },
        })
        .then((r) => r.data),
  });

  const s = data?.summary;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Profit & Loss</h2>

      <ReportControls
        dateFrom={dateFrom}
        dateTo={dateTo}
        period={period}
        csvUrl="/reports/pl/csv"
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
        onPeriodChange={setPeriod}
      />

      {isLoading ? (
        <SkeletonTable rows={5} cols={4} />
      ) : !data || !s ? null : (
        <div className="space-y-8">
          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Realized Sales Revenue</p>
              <p className="text-2xl font-bold mt-1">{formatCurrency(s.total_revenue)}</p>
              <p className="text-xs text-muted-foreground mt-1">
                Sales basis only: {formatCurrency(s.sales_revenue)}
              </p>
            </div>
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Total Costs</p>
              <p className="text-2xl font-bold mt-1">{formatCurrency(s.total_costs)}</p>
            </div>
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Gross Profit</p>
              <p className={`text-2xl font-bold mt-1 ${s.gross_profit >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                {formatCurrency(s.gross_profit)}
              </p>
            </div>
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Profit Margin</p>
              <p className={`text-2xl font-bold mt-1 ${s.profit_margin_pct >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                {formatPercent(s.profit_margin_pct)}
              </p>
            </div>
          </div>

          <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4 text-sm text-amber-900 dark:text-amber-100">
            <p className="font-medium">Reporting basis: sales-realized revenue</p>
            <p className="mt-1">{s.production_estimate_note}</p>
            <p className="mt-1">Operational production estimate shown separately: {formatCurrency(s.operational_production_estimate)}</p>
          </div>

          {/* Cost breakdown */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Cost Breakdown</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
              {[
                { label: 'Materials', value: s.material_costs },
                { label: 'Labor', value: s.labor_costs },
                { label: 'Machine', value: s.machine_costs },
                { label: 'Overhead', value: s.overhead_costs },
                { label: 'Platform Fees', value: s.platform_fees },
                { label: 'Shipping', value: s.shipping_costs },
              ].map(({ label, value }) => (
                <div key={label} className="text-center">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="text-lg font-semibold mt-1">{formatCurrency(value)}</p>
                  {s.total_costs > 0 && (
                    <p className="text-xs text-muted-foreground">{((value / s.total_costs) * 100).toFixed(0)}%</p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Trend chart */}
          {data.period_data.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-6">
              <h3 className="text-lg font-semibold mb-4">P&L Trend</h3>
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={data.period_data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="period" tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" />
                  <YAxis tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" tickFormatter={(v) => `$${v}`} />
                  <Tooltip formatter={formatTooltipCurrency} contentStyle={{ backgroundColor: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }} />
                  <Legend />
                  <Bar dataKey="sales_revenue" name="Sales Revenue" stackId="rev" fill="#8b5cf6" />
                  <Bar dataKey="operational_production_estimate" name="Operational Production Estimate" fill="#6366f1" />
                  <Bar dataKey="material_costs" name="Materials" stackId="cost" fill="#f87171" />
                  <Bar dataKey="labor_costs" name="Labor" stackId="cost" fill="#fb923c" />
                  <Bar dataKey="machine_costs" name="Machine" stackId="cost" fill="#fbbf24" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Period table */}
          {data.period_data.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-6">
              <h3 className="text-lg font-semibold mb-4">Period Detail</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-muted-foreground">
                      <th className="px-3 py-2 font-medium">Period</th>
                      <th className="px-3 py-2 font-medium text-right">Sales Rev</th>
                      <th className="px-3 py-2 font-medium text-right">Prod Estimate</th>
                      <th className="px-3 py-2 font-medium text-right">Materials</th>
                      <th className="px-3 py-2 font-medium text-right">Labor</th>
                      <th className="px-3 py-2 font-medium text-right">Machine</th>
                      <th className="px-3 py-2 font-medium text-right">Overhead</th>
                      <th className="px-3 py-2 font-medium text-right">Fees</th>
                      <th className="px-3 py-2 font-medium text-right">Gross Profit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.period_data.map((row) => (
                      <tr key={row.period} className="border-b border-border last:border-0 hover:bg-accent/50">
                        <td className="px-3 py-2 font-medium">{row.period}</td>
                        <td className="px-3 py-2 text-right">{formatCurrency(row.sales_revenue)}</td>
                        <td className="px-3 py-2 text-right text-muted-foreground">{formatCurrency(row.operational_production_estimate)}</td>
                        <td className="px-3 py-2 text-right">{formatCurrency(row.material_costs)}</td>
                        <td className="px-3 py-2 text-right">{formatCurrency(row.labor_costs)}</td>
                        <td className="px-3 py-2 text-right">{formatCurrency(row.machine_costs)}</td>
                        <td className="px-3 py-2 text-right">{formatCurrency(row.overhead_costs)}</td>
                        <td className="px-3 py-2 text-right">{formatCurrency(row.platform_fees)}</td>
                        <td className={`px-3 py-2 text-right font-semibold ${row.gross_profit >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                          {formatCurrency(row.gross_profit)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
