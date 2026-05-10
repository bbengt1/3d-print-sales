import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
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
import { getApiErrorMessage } from '@/lib/apiError';

interface Claim {
  id: string;
  claim_number: string;
  payer_name: string;
  incurred_on: string;
  total_amount: number;
  status: string;
}

interface LineDraft { description: string; amount: string; expense_account_id: string }
const empty = { payer_name: '', incurred_on: new Date().toISOString().slice(0, 10), notes: '', lines: [{ description: '', amount: '0', expense_account_id: '' }] as LineDraft[] };

export default function ExpenseClaimsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<Claim[]>({ queryKey: ['expense-claims'], queryFn: () => api.get('/expense-claims').then((r) => r.data) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  const setLine = (i: number, p: Partial<LineDraft>) => setForm((f) => ({ ...f, lines: f.lines.map((l, idx) => (idx === i ? { ...l, ...p } : l)) }));

  const save = async () => {
    if (!form.payer_name) return toast.error('Payer required');
    setSaving(true);
    try {
      await api.post('/expense-claims', { ...form, notes: form.notes || null });
      toast.success('Claim created');
      qc.invalidateQueries({ queryKey: ['expense-claims'] });
      setOpen(false); setForm(empty);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
    finally { setSaving(false); }
  };

  const action = async (id: string, verb: string) => {
    try {
      await api.post(`/expense-claims/${id}/${verb}`);
      toast.success(verb);
      qc.invalidateQueries({ queryKey: ['expense-claims'] });
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };

  const cols: Column<Claim>[] = [
    { key: 'n', header: 'Claim #', cell: (r) => <span className="font-medium">{r.claim_number}</span> },
    { key: 'p', header: 'Payer', cell: (r) => r.payer_name },
    { key: 'd', header: 'Incurred', cell: (r) => r.incurred_on },
    { key: 't', header: 'Total', numeric: true, cell: (r) => `$${Number(r.total_amount).toFixed(2)}` },
    { key: 's', header: 'Status', cell: (r) => <span className="capitalize">{r.status}</span> },
    { key: 'a', header: '', width: '260px', cell: (r) => (
      <div className="flex justify-end gap-1">
        {r.status === 'draft' && <Button size="sm" variant="outline" onClick={() => action(r.id, 'submit')}>Submit</Button>}
        {r.status === 'submitted' && <Button size="sm" variant="outline" onClick={() => action(r.id, 'approve')}>Approve</Button>}
        {r.status === 'approved' && <Button size="sm" variant="outline" onClick={() => action(r.id, 'reimburse')}>Reimburse</Button>}
        {r.status !== 'cancelled' && r.status !== 'reimbursed' && <Button size="sm" variant="ghost" onClick={() => action(r.id, 'cancel')}>Cancel</Button>}
      </div>
    ) },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Expense claims" description="Owner-paid reimbursable expenses (posts to 2300)" actions={<Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />New claim</Button>} />
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>New expense claim</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Payer name</Label><Input value={form.payer_name} onChange={(e) => setForm({ ...form, payer_name: e.target.value })} /></div>
              <div><Label>Incurred on</Label><Input type="date" value={form.incurred_on} onChange={(e) => setForm({ ...form, incurred_on: e.target.value })} /></div>
            </div>
            <div><Label>Notes</Label><Textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
            <div className="space-y-2">
              <Label>Lines</Label>
              {form.lines.map((line, i) => (
                <div key={i} className="grid grid-cols-12 gap-2">
                  <Input className="col-span-6" placeholder="Description" value={line.description} onChange={(e) => setLine(i, { description: e.target.value })} />
                  <Input className="col-span-3" type="number" step="0.01" value={line.amount} onChange={(e) => setLine(i, { amount: e.target.value })} />
                  <Input className="col-span-3" placeholder="Expense acct ID" value={line.expense_account_id} onChange={(e) => setLine(i, { expense_account_id: e.target.value })} />
                </div>
              ))}
              <Button size="sm" variant="outline" onClick={() => setForm((f) => ({ ...f, lines: [...f.lines, { description: '', amount: '0', expense_account_id: '' }] }))}>+ Add line</Button>
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
