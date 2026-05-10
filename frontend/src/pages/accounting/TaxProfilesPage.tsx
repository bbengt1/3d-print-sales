import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { getApiErrorMessage } from '@/lib/apiError';

interface Component { id?: string; name: string; rate: string; apply_order: number }
interface TaxProfile {
  id: string;
  name: string;
  jurisdiction: string;
  tax_rate: number;
  is_compound: boolean;
  is_reverse_charge: boolean;
  components?: Component[];
}

const empty = { name: '', jurisdiction: '', tax_rate: '0', is_compound: false, is_reverse_charge: false, components: [] as Component[] };

export default function TaxProfilesPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<TaxProfile[]>({ queryKey: ['tax-profiles'], queryFn: () => api.get('/tax/profiles').then((r) => r.data) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  const setComponent = (i: number, p: Partial<Component>) => setForm((f) => ({ ...f, components: f.components.map((c, idx) => idx === i ? { ...c, ...p } : c) }));

  const save = async () => {
    if (!form.name) return toast.error('Name required');
    setSaving(true);
    try {
      await api.post('/tax/profiles', {
        name: form.name,
        jurisdiction: form.jurisdiction,
        tax_rate: form.tax_rate,
        is_compound: form.is_compound,
        is_reverse_charge: form.is_reverse_charge,
        components: form.components.map((c) => ({ name: c.name, rate: c.rate, apply_order: c.apply_order })),
      });
      toast.success('Created');
      qc.invalidateQueries({ queryKey: ['tax-profiles'] });
      setOpen(false); setForm(empty);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
    finally { setSaving(false); }
  };

  const cols: Column<TaxProfile>[] = [
    { key: 'n', header: 'Name', cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'j', header: 'Jurisdiction', cell: (r) => r.jurisdiction },
    { key: 'r', header: 'Rate', numeric: true, cell: (r) => `${Number(r.tax_rate).toFixed(3)}%` },
    { key: 'c', header: 'Compound', cell: (r) => (r.is_compound ? 'yes' : 'no') },
    { key: 'rc', header: 'Reverse-charge', cell: (r) => (r.is_reverse_charge ? 'yes' : 'no') },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Tax profiles" description="Single-rate, compound (e.g. GST+QST), and reverse-charge profiles" actions={<Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />New profile</Button>} />
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>New tax profile</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
              <div><Label>Jurisdiction</Label><Input value={form.jurisdiction} onChange={(e) => setForm({ ...form, jurisdiction: e.target.value })} /></div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div><Label>Top-level rate %</Label><Input type="number" step="0.001" value={form.tax_rate} onChange={(e) => setForm({ ...form, tax_rate: e.target.value })} /></div>
              <div className="flex items-end gap-2"><input id="comp" type="checkbox" checked={form.is_compound} onChange={(e) => setForm({ ...form, is_compound: e.target.checked })} /><Label htmlFor="comp">Compound</Label></div>
              <div className="flex items-end gap-2"><input id="rc" type="checkbox" checked={form.is_reverse_charge} onChange={(e) => setForm({ ...form, is_reverse_charge: e.target.checked })} /><Label htmlFor="rc">Reverse-charge</Label></div>
            </div>
            {form.is_compound && (
              <div className="space-y-2">
                <Label>Components (e.g. GST 5%, QST 9.975%)</Label>
                {form.components.map((c, i) => (
                  <div key={i} className="grid grid-cols-12 gap-2">
                    <Input className="col-span-5" placeholder="Component name" value={c.name} onChange={(e) => setComponent(i, { name: e.target.value })} />
                    <Input className="col-span-3" type="number" step="0.001" placeholder="Rate %" value={c.rate} onChange={(e) => setComponent(i, { rate: e.target.value })} />
                    <Input className="col-span-3" type="number" placeholder="Apply order" value={c.apply_order} onChange={(e) => setComponent(i, { apply_order: Number(e.target.value) })} />
                    <Button className="col-span-1" size="sm" variant="ghost" onClick={() => setForm((f) => ({ ...f, components: f.components.filter((_, idx) => idx !== i) }))}><Trash2 className="h-4 w-4" /></Button>
                  </div>
                ))}
                <Button size="sm" variant="outline" onClick={() => setForm((f) => ({ ...f, components: [...f.components, { name: '', rate: '0', apply_order: f.components.length }] }))}>+ Add component</Button>
              </div>
            )}
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
