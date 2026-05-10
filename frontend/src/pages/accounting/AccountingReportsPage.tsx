import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download } from 'lucide-react';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs';

interface TBRow { account_id: string; account_code: string; account_name: string; debit: number; credit: number }

function TrialBalanceTab() {
  const [asOf, setAsOf] = useState(new Date().toISOString().slice(0, 10));
  const { data, isLoading } = useQuery<{ rows: TBRow[]; total_debit: number; total_credit: number }>({
    queryKey: ['trial-balance', asOf],
    queryFn: () => api.get('/reports/trial-balance', { params: { as_of_date: asOf } }).then((r) => r.data),
  });
  const csv = () => {
    const token = localStorage.getItem('token');
    const url = `/api/v1/reports/trial-balance.csv?as_of_date=${asOf}`;
    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((r) => r.blob())
      .then((b) => { const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = `trial-balance-${asOf}.csv`; a.click(); });
  };
  return (
    <div className="space-y-3">
      <div className="flex items-end gap-2 rounded-lg border bg-card p-3">
        <div><Label>As of</Label><Input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} /></div>
        <Button variant="outline" onClick={csv}><Download className="mr-2 h-4 w-4" />CSV</Button>
      </div>
      {isLoading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : (
        <div className="overflow-x-auto rounded-lg border bg-card">
          <table className="w-full text-sm">
            <thead className="bg-muted/40">
              <tr><th className="px-3 py-2 text-left">Code</th><th className="px-3 py-2 text-left">Account</th><th className="px-3 py-2 text-right">Debit</th><th className="px-3 py-2 text-right">Credit</th></tr>
            </thead>
            <tbody>
              {(data?.rows ?? []).map((r) => (
                <tr key={r.account_id} className="border-t">
                  <td className="px-3 py-1.5 font-mono">{r.account_code}</td>
                  <td className="px-3 py-1.5">{r.account_name}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{Number(r.debit).toFixed(2)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{Number(r.credit).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
            {data && (
              <tfoot className="bg-muted/20 font-medium">
                <tr><td colSpan={2} className="px-3 py-2">Totals</td><td className="px-3 py-2 text-right tabular-nums">{Number(data.total_debit).toFixed(2)}</td><td className="px-3 py-2 text-right tabular-nums">{Number(data.total_credit).toFixed(2)}</td></tr>
              </tfoot>
            )}
          </table>
        </div>
      )}
    </div>
  );
}

function ReceiptsPaymentsTab() {
  const [start, setStart] = useState(new Date(Date.now() - 30 * 86400_000).toISOString().slice(0, 10));
  const [end, setEnd] = useState(new Date().toISOString().slice(0, 10));
  const csv = () => {
    const token = localStorage.getItem('token');
    const url = `/api/v1/reports/receipts-payments-summary.csv?start_date=${start}&end_date=${end}`;
    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((r) => r.blob())
      .then((b) => { const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = `receipts-payments-${start}-${end}.csv`; a.click(); });
  };
  return (
    <div className="space-y-3">
      <div className="flex items-end gap-2 rounded-lg border bg-card p-3">
        <div><Label>Start</Label><Input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></div>
        <div><Label>End</Label><Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></div>
        <Button onClick={csv}><Download className="mr-2 h-4 w-4" />Download CSV</Button>
      </div>
      <div className="rounded-lg border bg-card p-4 text-sm text-muted-foreground">Receipts & Payments summary is exported as CSV.</div>
    </div>
  );
}

function ARAgingTab() {
  const { data, isLoading } = useQuery<any>({ queryKey: ['ar-aging'], queryFn: () => api.get('/reports/ar-aging').then((r) => r.data) });
  return (
    <div className="rounded-lg border bg-card p-4">
      {isLoading ? <div className="text-sm text-muted-foreground">Loading…</div> : <pre className="overflow-auto text-xs">{JSON.stringify(data, null, 2)}</pre>}
    </div>
  );
}

function APAgingTab() {
  const { data, isLoading } = useQuery<any>({ queryKey: ['ap-aging'], queryFn: () => api.get('/reports/ap-aging').then((r) => r.data) });
  return (
    <div className="rounded-lg border bg-card p-4">
      {isLoading ? <div className="text-sm text-muted-foreground">Loading…</div> : <pre className="overflow-auto text-xs">{JSON.stringify(data, null, 2)}</pre>}
    </div>
  );
}

export default function AccountingReportsPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Reports" description="Trial balance, receipts/payments, AR/AP aging" />
      <Tabs defaultValue="tb">
        <TabsList>
          <TabsTrigger value="tb">Trial balance</TabsTrigger>
          <TabsTrigger value="rp">Receipts & payments</TabsTrigger>
          <TabsTrigger value="ar">AR aging</TabsTrigger>
          <TabsTrigger value="ap">AP aging</TabsTrigger>
        </TabsList>
        <TabsContent value="tb" className="mt-4"><TrialBalanceTab /></TabsContent>
        <TabsContent value="rp" className="mt-4"><ReceiptsPaymentsTab /></TabsContent>
        <TabsContent value="ar" className="mt-4"><ARAgingTab /></TabsContent>
        <TabsContent value="ap" className="mt-4"><APAgingTab /></TabsContent>
      </Tabs>
    </div>
  );
}
