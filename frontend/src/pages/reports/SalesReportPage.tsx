import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import api from '@/api/client';
import { formatCurrency } from '@/lib/utils';
import ReportControls from '@/components/ui/ReportControls';
import { SkeletonTable } from '@/components/ui/Skeleton';
import type { SalesReport } from '@/types';

export default function SalesReportPage() {
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [period, setPeriod] = useState('monthly');

  const { data, isLoading } = useQuery<SalesReport>({
    queryKey: ['report', 'sales', dateFrom, dateTo, period],
    queryFn: () =>
      api
        .get('/reports/sales', {
          params: {
            date_from: dateFrom || undefined,
            date_to: dateTo || undefined,
            period,
          },
        })
        .then((r) => r.data),
  });

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Sales Report</h2>

      <ReportControls
        dateFrom={dateFrom}
        dateTo={dateTo}
        period={period}
        csvUrl="/reports/sales/csv"
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
        onPeriodChange={setPeriod}
      />

      {isLoading ? (
        <SkeletonTable rows={5} cols={5} />
      ) : !data ? null : (
        <div className="space-y-8">
          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Total Orders</p>
              <p className="text-3xl font-bold mt-1">{data.total_orders}</p>
            </div>
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Gross Sales</p>
              <p className="text-3xl font-bold mt-1">{formatCurrency(data.gross_sales)}</p>
            </div>
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Item COGS</p>
              <p className="text-3xl font-bold mt-1">{formatCurrency(data.item_cogs)}</p>
            </div>
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Gross Profit</p>
              <p className={`text-3xl font-bold mt-1 ${data.gross_profit >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                {formatCurrency(data.gross_profit)}
              </p>
            </div>
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Platform Fees + Shipping</p>
              <p className="text-3xl font-bold mt-1">{formatCurrency(data.platform_fees + data.shipping_costs)}</p>
            </div>
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Contribution Margin</p>
              <p className={`text-3xl font-bold mt-1 ${data.contribution_margin >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                {formatCurrency(data.contribution_margin)}
              </p>
            </div>
          </div>

          {/* Revenue over time chart */}
          {data.period_data.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-6">
              <h3 className="text-lg font-semibold mb-4">Revenue Over Time</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={data.period_data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="period" tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" />
                  <YAxis tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" tickFormatter={(v) => `$${v}`} />
                  <Tooltip formatter={(v: number) => formatCurrency(v)} contentStyle={{ backgroundColor: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }} />
                  <Legend />
                  <Line type="monotone" dataKey="gross_sales" name="Gross Sales" stroke="var(--color-primary)" strokeWidth={2} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="gross_profit" name="Gross Profit" stroke="#22c55e" strokeWidth={2} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="contribution_margin" name="Contribution Margin" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top products */}
            {data.top_products.length > 0 && (
              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-lg font-semibold mb-4">Top Products</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-muted-foreground">
                        <th className="pb-2 font-medium">Product</th>
                        <th className="pb-2 font-medium text-right">Units</th>
                        <th className="pb-2 font-medium text-right">Gross Sales</th>
                        <th className="pb-2 font-medium text-right">Contribution</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.top_products.map((p, i) => (
                        <tr key={i} className="border-b border-border last:border-0">
                          <td className="py-2">{p.description}</td>
                          <td className="py-2 text-right">{p.units_sold}</td>
                          <td className="py-2 text-right">{formatCurrency(p.gross_sales)}</td>
                          <td className={`py-2 text-right ${p.contribution_margin >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                            {formatCurrency(p.contribution_margin)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Channel breakdown */}
            {data.channel_breakdown.length > 0 && (
              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-lg font-semibold mb-4">Channel Breakdown</h3>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={data.channel_breakdown}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="channel_name" tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" />
                    <YAxis tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" tickFormatter={(v) => `$${v}`} />
                    <Tooltip formatter={(v: number) => formatCurrency(v)} contentStyle={{ backgroundColor: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }} />
                    <Legend />
                    <Bar dataKey="gross_sales" name="Gross Sales" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="contribution_margin" name="Contribution Margin" fill="#22c55e" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-muted-foreground">
                        <th className="pb-2 font-medium">Channel</th>
                        <th className="pb-2 font-medium text-right">Orders</th>
                        <th className="pb-2 font-medium text-right">Gross Sales</th>
                        <th className="pb-2 font-medium text-right">Gross Profit</th>
                        <th className="pb-2 font-medium text-right">Fees</th>
                        <th className="pb-2 font-medium text-right">Shipping</th>
                        <th className="pb-2 font-medium text-right">Contribution</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.channel_breakdown.map((ch, i) => (
                        <tr key={i} className="border-b border-border last:border-0">
                          <td className="py-2">{ch.channel_name}</td>
                          <td className="py-2 text-right">{ch.order_count}</td>
                          <td className="py-2 text-right">{formatCurrency(ch.gross_sales)}</td>
                          <td className="py-2 text-right">{formatCurrency(ch.gross_profit)}</td>
                          <td className="py-2 text-right text-muted-foreground">{formatCurrency(ch.platform_fees)}</td>
                          <td className="py-2 text-right text-muted-foreground">{formatCurrency(ch.shipping_costs)}</td>
                          <td className="py-2 text-right">{formatCurrency(ch.contribution_margin)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
