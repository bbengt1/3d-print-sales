import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Plus, Mail } from 'lucide-react';
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

interface Quote {
  id: string;
  quote_number: string;
  customer_name: string | null;
  issue_date: string;
  expiry_date: string | null;
  total: number;
  status: string;
}

interface LineDraft { description: string; quantity: number; unit_price: string }

const empty = { customer_name: '', issue_date: new Date().toISOString().slice(0, 10), expiry_date: '', notes: '', lines: [{ description: '', quantity: 1, unit_price: '0' }] as LineDraft[] };

export default function QuotesPage() {
  const qc = useQueryClient();
  const list = useListQuery<Quote>({ resource: 'quotes' });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const [emailing, setEmailing] = useState<Quote | null>(null);
  const [emailTo, setEmailTo] = useState('');

  const setLine = (i: number, p: Partial<LineDraft>) => setForm((f) => ({ ...f, lines: f.lines.map((l, idx) => (idx === i ? { ...l, ...p } : l)) }));

  const save = async () => {
    if (!form.customer_name) return toast.error('Customer required');
    setSaving(true);
    try {
      await api.post('/quotes', { ...form, expiry_date: form.expiry_date || null, notes: form.notes || null });
      toast.success('Quote created');
      qc.invalidateQueries({ queryKey: ['quotes'] });
      setOpen(false); setForm(empty);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
    finally { setSaving(false); }
  };

  const sendEmail = async () => {
    if (!emailing) return;
    try {
      await api.post(`/quotes/${emailing.id}/send-email`, { to_email: emailTo || null });
      toast.success('Email queued');
      setEmailing(null); setEmailTo('');
    } catch (err) { toast.error(getApiErrorMessage(err, 'Email failed')); }
  };

  const columns: Column<Quote>[] = [
    { key: 'n', header: 'Quote #', cell: (r) => <span className="font-medium">{r.quote_number}</span> },
    { key: 'c', header: 'Customer', cell: (r) => r.customer_name || '—' },
    { key: 'd', header: 'Issued', cell: (r) => r.issue_date },
    { key: 'e', header: 'Expires', cell: (r) => r.expiry_date || '—' },
    { key: 't', header: 'Total', numeric: true, cell: (r) => `$${Number(r.total).toFixed(2)}` },
    { key: 's', header: 'Status', cell: (r) => <span className="capitalize">{r.status}</span> },
    { key: 'a', header: '', width: '80px', cell: (r) => <Button size="icon" variant="ghost" onClick={() => setEmailing(r)}><Mail className="h-4 w-4" /></Button> },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Quotes" description="Customer quotes with email send" actions={<Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />New quote</Button>} />
      <DataTable data={list.data} columns={columns} rowKey={(r) => r.id} loading={list.isLoading} />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>New quote</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Customer name</Label><Input value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Issue</Label><Input type="date" value={form.issue_date} onChange={(e) => setForm({ ...form, issue_date: e.target.value })} /></div>
              <div><Label>Expires</Label><Input type="date" value={form.expiry_date} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} /></div>
            </div>
            <div className="space-y-2">
              <Label>Lines</Label>
              {form.lines.map((line, i) => (
                <div key={i} className="grid grid-cols-12 gap-2">
                  <Input className="col-span-7" placeholder="Description" value={line.description} onChange={(e) => setLine(i, { description: e.target.value })} />
                  <Input className="col-span-2" type="number" min={1} value={line.quantity} onChange={(e) => setLine(i, { quantity: Number(e.target.value) })} />
                  <Input className="col-span-3" type="number" step="0.01" value={line.unit_price} onChange={(e) => setLine(i, { unit_price: e.target.value })} />
                </div>
              ))}
              <Button size="sm" variant="outline" onClick={() => setForm((f) => ({ ...f, lines: [...f.lines, { description: '', quantity: 1, unit_price: '0' }] }))}>+ Add line</Button>
            </div>
            <div><Label>Notes</Label><Textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Create'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(emailing)} onOpenChange={(o) => !o && setEmailing(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Email quote {emailing?.quote_number}</DialogTitle></DialogHeader>
          <div><Label>To (override)</Label><Input value={emailTo} onChange={(e) => setEmailTo(e.target.value)} /></div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEmailing(null)}>Cancel</Button>
            <Button onClick={sendEmail}>Send</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
