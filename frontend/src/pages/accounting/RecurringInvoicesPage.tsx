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
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { getApiErrorMessage } from '@/lib/apiError';

interface RI {
  id: string;
  name: string;
  customer_id: string;
  cadence: string;
  interval_count: number;
  next_run_on: string;
  auto_email: boolean;
  active: boolean;
  last_error: string | null;
}

interface LineDraft { description: string; quantity: string; unit_price: string }
const empty = {
  name: '',
  customer_id: '',
  cadence: 'monthly',
  interval_count: '1',
  start_on: new Date().toISOString().slice(0, 10),
  due_in_days: '30',
  auto_email: false,
  lines: [{ description: '', quantity: '1', unit_price: '0' }] as LineDraft[],
};

export default function RecurringInvoicesPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<RI[]>({ queryKey: ['recurring-invoices'], queryFn: () => api.get('/recurring-invoices').then((r) => r.data) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  const setLine = (i: number, p: Partial<LineDraft>) => setForm((f) => ({ ...f, lines: f.lines.map((l, idx) => (idx === i ? { ...l, ...p } : l)) }));

  const save = async () => {
    if (!form.name || !form.customer_id) return toast.error('Name + customer required');
    setSaving(true);
    try {
      await api.post('/recurring-invoices', {
        name: form.name,
        customer_id: form.customer_id,
        cadence: form.cadence,
        interval_count: Number(form.interval_count),
        start_on: form.start_on,
        next_run_on: form.start_on,
        due_in_days: Number(form.due_in_days),
        auto_email: form.auto_email,
        line_items_template: form.lines,
      });
      toast.success('Created');
      qc.invalidateQueries({ queryKey: ['recurring-invoices'] });
      setOpen(false); setForm(empty);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
    finally { setSaving(false); }
  };

  const action = async (id: string, verb: string) => {
    try {
      await api.post(`/recurring-invoices/${id}/${verb}`);
      toast.success(verb);
      qc.invalidateQueries({ queryKey: ['recurring-invoices'] });
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };

  const remove = async (id: string) => {
    try {
      await api.delete(`/recurring-invoices/${id}`);
      toast.success('Removed');
      qc.invalidateQueries({ queryKey: ['recurring-invoices'] });
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };

  const cols: Column<RI>[] = [
    { key: 'n', header: 'Name', cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'c', header: 'Cadence', cell: (r) => `every ${r.interval_count} ${r.cadence}` },
    { key: 'next', header: 'Next run', cell: (r) => r.next_run_on },
    { key: 'e', header: 'Auto-email', cell: (r) => (r.auto_email ? 'yes' : 'no') },
    { key: 'a', header: 'Active', cell: (r) => (r.active ? 'yes' : 'no') },
    { key: 'err', header: 'Last error', cell: (r) => r.last_error || '—' },
    { key: 'x', header: '', width: '180px', cell: (r) => (
      <div className="flex justify-end gap-1">
        <Button size="icon" variant="ghost" onClick={() => action(r.id, 'run-now')} aria-label="Run now"><Play className="h-4 w-4" /></Button>
        <Button size="icon" variant="ghost" onClick={() => action(r.id, 'skip-next')} aria-label="Skip next"><SkipForward className="h-4 w-4" /></Button>
        <Button size="icon" variant="ghost" onClick={() => remove(r.id)} aria-label="Delete"><Trash2 className="h-4 w-4" /></Button>
      </div>
    ) },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Recurring invoices" description="Auto-generate invoices on a schedule, optionally email" actions={<Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />New rule</Button>} />
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>New recurring invoice</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
              <div><Label>Customer ID</Label><Input value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })} /></div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label>Cadence</Label>
                <select className="mt-1 block w-full rounded-md border bg-background px-2 py-2 text-sm" value={form.cadence} onChange={(e) => setForm({ ...form, cadence: e.target.value })}>
                  <option value="weekly">weekly</option>
                  <option value="monthly">monthly</option>
                  <option value="quarterly">quarterly</option>
                  <option value="yearly">yearly</option>
                </select>
              </div>
              <div><Label>Every</Label><Input type="number" min={1} value={form.interval_count} onChange={(e) => setForm({ ...form, interval_count: e.target.value })} /></div>
              <div><Label>Start on</Label><Input type="date" value={form.start_on} onChange={(e) => setForm({ ...form, start_on: e.target.value })} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Due in (days)</Label><Input type="number" value={form.due_in_days} onChange={(e) => setForm({ ...form, due_in_days: e.target.value })} /></div>
              <div className="flex items-end gap-2"><input type="checkbox" id="auto" checked={form.auto_email} onChange={(e) => setForm({ ...form, auto_email: e.target.checked })} /><Label htmlFor="auto">Auto-email</Label></div>
            </div>
            <div className="space-y-2">
              <Label>Lines</Label>
              {form.lines.map((line, i) => (
                <div key={i} className="grid grid-cols-12 gap-2">
                  <Input className="col-span-7" placeholder="Description" value={line.description} onChange={(e) => setLine(i, { description: e.target.value })} />
                  <Input className="col-span-2" value={line.quantity} onChange={(e) => setLine(i, { quantity: e.target.value })} />
                  <Input className="col-span-3" type="number" step="0.01" value={line.unit_price} onChange={(e) => setLine(i, { unit_price: e.target.value })} />
                </div>
              ))}
              <Button size="sm" variant="outline" onClick={() => setForm((f) => ({ ...f, lines: [...f.lines, { description: '', quantity: '1', unit_price: '0' }] }))}>+ Add line</Button>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Create'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
