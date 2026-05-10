import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Play, SkipForward, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { Textarea } from '@/components/ui/Textarea';
import { getApiErrorMessage } from '@/lib/apiError';

interface RJE {
  id: string;
  name: string;
  cadence: string;
  interval_count: number;
  next_run_on: string;
  active: boolean;
}

interface SuspenseLine {
  id: string;
  account_id: string;
  amount: number;
  posted_on: string;
  description: string | null;
}

function RecurringJEsTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<RJE[]>({ queryKey: ['rjes'], queryFn: () => api.get('/accounting/recurring-journal-entries').then((r) => r.data) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: '',
    cadence: 'monthly',
    interval_count: '1',
    start_on: new Date().toISOString().slice(0, 10),
    description: '',
    lines_template: '[{"account_id": "", "amount": "0", "side": "debit"}]',
  });
  const save = async () => {
    if (!form.name) return toast.error('Name required');
    let parsed;
    try { parsed = JSON.parse(form.lines_template); }
    catch { return toast.error('Invalid lines_template JSON'); }
    try {
      await api.post('/accounting/recurring-journal-entries', {
        name: form.name,
        cadence: form.cadence,
        interval_count: Number(form.interval_count),
        start_on: form.start_on,
        next_run_on: form.start_on,
        description: form.description || null,
        lines_template: parsed,
      });
      toast.success('Created');
      qc.invalidateQueries({ queryKey: ['rjes'] });
      setOpen(false);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  const action = async (id: string, verb: string) => {
    try { await api.post(`/accounting/recurring-journal-entries/${id}/${verb}`); qc.invalidateQueries({ queryKey: ['rjes'] }); toast.success(verb); }
    catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  const remove = async (id: string) => {
    try { await api.delete(`/accounting/recurring-journal-entries/${id}`); qc.invalidateQueries({ queryKey: ['rjes'] }); toast.success('Removed'); }
    catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  const cols: Column<RJE>[] = [
    { key: 'n', header: 'Name', cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'c', header: 'Cadence', cell: (r) => `every ${r.interval_count} ${r.cadence}` },
    { key: 'next', header: 'Next run', cell: (r) => r.next_run_on },
    { key: 'a', header: 'Active', cell: (r) => (r.active ? 'yes' : 'no') },
    { key: 'x', header: '', width: '180px', cell: (r) => (
      <div className="flex justify-end gap-1">
        <Button size="icon" variant="ghost" onClick={() => action(r.id, 'run-now')}><Play className="h-4 w-4" /></Button>
        <Button size="icon" variant="ghost" onClick={() => action(r.id, 'skip-next')}><SkipForward className="h-4 w-4" /></Button>
        <Button size="icon" variant="ghost" onClick={() => remove(r.id)}><Trash2 className="h-4 w-4" /></Button>
      </div>
    ) },
  ];
  return (
    <div className="space-y-3">
      <Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />New recurring JE</Button>
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>New recurring journal entry</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label>Cadence</Label>
                <select className="mt-1 block w-full rounded-md border bg-background px-2 py-2 text-sm" value={form.cadence} onChange={(e) => setForm({ ...form, cadence: e.target.value })}>
                  <option value="weekly">weekly</option><option value="monthly">monthly</option><option value="quarterly">quarterly</option><option value="yearly">yearly</option>
                </select>
              </div>
              <div><Label>Every</Label><Input type="number" min={1} value={form.interval_count} onChange={(e) => setForm({ ...form, interval_count: e.target.value })} /></div>
              <div><Label>Start on</Label><Input type="date" value={form.start_on} onChange={(e) => setForm({ ...form, start_on: e.target.value })} /></div>
            </div>
            <div><Label>Description</Label><Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
            <div>
              <Label>Lines template (JSON)</Label>
              <Textarea rows={6} value={form.lines_template} onChange={(e) => setForm({ ...form, lines_template: e.target.value })} className="font-mono text-xs" />
            </div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={save}>Create</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SuspenseTab() {
  const { data, isLoading } = useQuery<SuspenseLine[]>({ queryKey: ['suspense'], queryFn: () => api.get('/accounting/suspense').then((r) => Array.isArray(r.data) ? r.data : r.data.items ?? []) });
  const cols: Column<SuspenseLine>[] = [
    { key: 'd', header: 'Posted', cell: (r) => r.posted_on },
    { key: 'desc', header: 'Description', cell: (r) => r.description || '—' },
    { key: 'a', header: 'Amount', numeric: true, cell: (r) => `$${Number(r.amount).toFixed(2)}` },
    { key: 'id', header: 'Line ID', cell: (r) => <span className="font-mono text-xs">{r.id.slice(0, 12)}…</span> },
  ];
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Open journal lines posted to the Suspense account (1900). Reclassify these to their proper accounts via the journal-entry editor.</p>
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />
    </div>
  );
}

function StartingBalancesTab() {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [json, setJson] = useState('[{"account_id":"","amount":"0","side":"debit"}]');
  const submit = async () => {
    let parsed;
    try { parsed = JSON.parse(json); }
    catch { return toast.error('Invalid JSON'); }
    try {
      await api.post('/accounting/starting-balances', { posted_on: date, lines: parsed });
      toast.success('Starting balances posted');
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  return (
    <div className="space-y-3 rounded-lg border bg-card p-4">
      <div><Label>Posted on</Label><Input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></div>
      <div><Label>Lines (balanced; will offset to OBE 3300)</Label><Textarea rows={10} className="font-mono text-xs" value={json} onChange={(e) => setJson(e.target.value)} /></div>
      <Button onClick={submit}>Post starting balances</Button>
    </div>
  );
}

export default function FoundationsPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Accounting foundations" description="Recurring JEs · Suspense · Starting balances" />
      <Tabs defaultValue="rje">
        <TabsList>
          <TabsTrigger value="rje">Recurring JEs</TabsTrigger>
          <TabsTrigger value="suspense">Suspense</TabsTrigger>
          <TabsTrigger value="sb">Starting balances</TabsTrigger>
        </TabsList>
        <TabsContent value="rje" className="mt-4"><RecurringJEsTab /></TabsContent>
        <TabsContent value="suspense" className="mt-4"><SuspenseTab /></TabsContent>
        <TabsContent value="sb" className="mt-4"><StartingBalancesTab /></TabsContent>
      </Tabs>
    </div>
  );
}
