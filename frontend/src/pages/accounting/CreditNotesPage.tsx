import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Textarea } from '@/components/ui/Textarea';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { useListQuery } from '@/hooks/useListQuery';
import { getApiErrorMessage } from '@/lib/apiError';

interface CN {
  id: string;
  note_number: string;
  customer_id: string | null;
  customer_name: string | null;
  issue_date: string;
  total_amount: number;
  status: string;
  reason: string | null;
}

interface LineDraft { description: string; quantity: string; unit_price: string }

const empty = { customer_name: '', issue_date: new Date().toISOString().slice(0, 10), reason: '', lines: [{ description: '', quantity: '1', unit_price: '0' }] as LineDraft[] };

export default function CreditNotesPage() {
  const qc = useQueryClient();
  const list = useListQuery<CN>({ resource: 'credit-notes' });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const [applying, setApplying] = useState<CN | null>(null);
  const [applyTo, setApplyTo] = useState({ invoice_id: '', amount: '' });

  const setLine = (i: number, p: Partial<LineDraft>) => setForm((f) => ({ ...f, lines: f.lines.map((l, idx) => (idx === i ? { ...l, ...p } : l)) }));

  const save = async () => {
    if (!form.customer_name) return toast.error('Customer required');
    setSaving(true);
    try {
      await api.post('/credit-notes', { ...form, reason: form.reason || null });
      toast.success('Credit note created');
      qc.invalidateQueries({ queryKey: ['credit-notes'] });
      setOpen(false); setForm(empty);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
    finally { setSaving(false); }
  };

  const action = async (id: string, verb: string, body?: any) => {
    try {
      await api.post(`/credit-notes/${id}/${verb}`, body);
      toast.success(verb);
      qc.invalidateQueries({ queryKey: ['credit-notes'] });
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };

  const apply = async () => {
    if (!applying) return;
    await action(applying.id, 'apply', { invoice_id: applyTo.invoice_id, amount: applyTo.amount });
    setApplying(null);
  };

  const cols: Column<CN>[] = [
    { key: 'n', header: 'CN #', cell: (r) => <span className="font-medium">{r.note_number}</span> },
    { key: 'c', header: 'Customer', cell: (r) => r.customer_name || '—' },
    { key: 'd', header: 'Issued', cell: (r) => r.issue_date },
    { key: 't', header: 'Total', numeric: true, cell: (r) => `$${Number(r.total_amount).toFixed(2)}` },
    { key: 's', header: 'Status', cell: (r) => <span className="capitalize">{r.status}</span> },
    { key: 'a', header: '', width: '220px', cell: (r) => (
      <div className="flex justify-end gap-1">
        {r.status === 'draft' && <Button size="sm" variant="outline" onClick={() => action(r.id, 'issue')}>Issue</Button>}
        {r.status === 'issued' && <Button size="sm" variant="outline" onClick={() => { setApplying(r); setApplyTo({ invoice_id: '', amount: String(r.total_amount) }); }}>Apply</Button>}
        {r.status !== 'voided' && <Button size="sm" variant="ghost" onClick={() => action(r.id, 'void')}>Void</Button>}
      </div>
    ) },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Credit notes" description="Customer refunds/credits applied to invoices" actions={<Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />New credit note</Button>} />
      <DataTable data={list.data} columns={cols} rowKey={(r) => r.id} loading={list.isLoading} />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>New credit note</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Customer name</Label><Input value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} /></div>
            <div><Label>Issue date</Label><Input type="date" value={form.issue_date} onChange={(e) => setForm({ ...form, issue_date: e.target.value })} /></div>
            <div><Label>Reason</Label><Textarea rows={2} value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} /></div>
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

      <Dialog open={Boolean(applying)} onOpenChange={(o) => !o && setApplying(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Apply credit note</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Invoice ID</Label><Input value={applyTo.invoice_id} onChange={(e) => setApplyTo({ ...applyTo, invoice_id: e.target.value })} /></div>
            <div><Label>Amount</Label><Input type="number" step="0.01" value={applyTo.amount} onChange={(e) => setApplyTo({ ...applyTo, amount: e.target.value })} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setApplying(null)}>Cancel</Button>
            <Button onClick={apply}>Apply</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
