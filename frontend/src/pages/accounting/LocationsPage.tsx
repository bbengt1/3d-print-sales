import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, MapPin, Truck, Boxes, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { getApiErrorMessage } from '@/lib/apiError';

interface Location { id: string; code: string; name: string; kind: string | null; active: boolean }
interface Transfer { id: string; from_location_id: string; to_location_id: string; status: string; created_at: string }
interface Kit { id: string; kit_product_id: string; component_count: number }

function LocationsTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<Location[]>({ queryKey: ['locations'], queryFn: () => api.get('/inventory/locations').then((r) => r.data) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ code: '', name: '', kind: 'warehouse' });
  const save = async () => {
    try {
      await api.post('/inventory/locations', form);
      toast.success('Created');
      qc.invalidateQueries({ queryKey: ['locations'] });
      setOpen(false); setForm({ code: '', name: '', kind: 'warehouse' });
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  const remove = async (id: string) => {
    try { await api.delete(`/inventory/locations/${id}`); qc.invalidateQueries({ queryKey: ['locations'] }); toast.success('Removed'); }
    catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  const cols: Column<Location>[] = [
    { key: 'c', header: 'Code', cell: (r) => <span className="font-mono">{r.code}</span> },
    { key: 'n', header: 'Name', cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'k', header: 'Kind', cell: (r) => r.kind || '—' },
    { key: 'a', header: 'Active', cell: (r) => (r.active ? 'yes' : 'no') },
    { key: 'x', header: '', width: '60px', cell: (r) => <Button size="icon" variant="ghost" onClick={() => remove(r.id)}><Trash2 className="h-4 w-4" /></Button> },
  ];
  return (
    <div className="space-y-3">
      <Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />New location</Button>
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>New location</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Code</Label><Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></div>
            <div><Label>Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div>
              <Label>Kind</Label>
              <select className="mt-1 block w-full rounded-md border bg-background px-2 py-2 text-sm" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
                <option value="warehouse">warehouse</option><option value="shop">shop</option><option value="staging">staging</option>
              </select>
            </div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={save}>Create</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function TransfersTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<Transfer[]>({ queryKey: ['inv-transfers'], queryFn: () => api.get('/inventory/transfers').then((r) => r.data) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ from_location_id: '', to_location_id: '', notes: '' });
  const save = async () => {
    try {
      await api.post('/inventory/transfers', { ...form, lines: [] });
      toast.success('Transfer created');
      qc.invalidateQueries({ queryKey: ['inv-transfers'] });
      setOpen(false);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  const action = async (id: string, verb: string) => {
    try { await api.post(`/inventory/transfers/${id}/${verb}`); qc.invalidateQueries({ queryKey: ['inv-transfers'] }); toast.success(verb); }
    catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  const cols: Column<Transfer>[] = [
    { key: 'f', header: 'From', cell: (r) => r.from_location_id.slice(0, 8) },
    { key: 't', header: 'To', cell: (r) => r.to_location_id.slice(0, 8) },
    { key: 'd', header: 'Created', cell: (r) => new Date(r.created_at).toLocaleString() },
    { key: 's', header: 'Status', cell: (r) => <span className="capitalize">{r.status}</span> },
    { key: 'a', header: '', width: '180px', cell: (r) => (
      <div className="flex justify-end gap-1">
        {r.status === 'pending' && <Button size="sm" variant="outline" onClick={() => action(r.id, 'ship')}>Ship</Button>}
        {r.status === 'in_transit' && <Button size="sm" variant="outline" onClick={() => action(r.id, 'receive')}>Receive</Button>}
        {r.status !== 'received' && r.status !== 'cancelled' && <Button size="sm" variant="ghost" onClick={() => action(r.id, 'cancel')}>Cancel</Button>}
      </div>
    ) },
  ];
  return (
    <div className="space-y-3">
      <Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />New transfer</Button>
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>New transfer</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><Label>From location ID</Label><Input value={form.from_location_id} onChange={(e) => setForm({ ...form, from_location_id: e.target.value })} /></div>
              <div><Label>To location ID</Label><Input value={form.to_location_id} onChange={(e) => setForm({ ...form, to_location_id: e.target.value })} /></div>
            </div>
            <div><Label>Notes</Label><Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={save}>Create</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function KitsTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<Kit[]>({ queryKey: ['kits'], queryFn: () => api.get('/kits').then((r) => Array.isArray(r.data) ? r.data : r.data.items ?? []) });
  const [editing, setEditing] = useState<string | null>(null);
  const [components, setComponents] = useState<{ component_product_id: string; quantity: string }[]>([]);
  const [productId, setProductId] = useState('');

  const openEditor = async (kp: string) => {
    setEditing(kp); setProductId(kp);
    try {
      const r = await api.get(`/kits/${kp}`);
      setComponents((r.data.components ?? []).map((c: any) => ({ component_product_id: c.component_product_id, quantity: String(c.quantity) })));
    } catch { setComponents([]); }
  };

  const openNew = () => { setEditing('new'); setProductId(''); setComponents([{ component_product_id: '', quantity: '1' }]); };

  const save = async () => {
    if (!productId) return toast.error('Kit product ID required');
    try {
      await api.put(`/kits/${productId}`, { components: components.map((c) => ({ component_product_id: c.component_product_id, quantity: Number(c.quantity) })) });
      toast.success('Saved');
      qc.invalidateQueries({ queryKey: ['kits'] });
      setEditing(null);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };

  const cols: Column<Kit>[] = [
    { key: 'p', header: 'Kit product', cell: (r) => r.kit_product_id.slice(0, 12) },
    { key: 'c', header: 'Components', numeric: true, cell: (r) => r.component_count },
    { key: 'a', header: '', width: '100px', cell: (r) => <Button size="sm" variant="outline" onClick={() => openEditor(r.kit_product_id)}>Edit</Button> },
  ];
  return (
    <div className="space-y-3">
      <Button onClick={openNew}><Plus className="mr-2 h-4 w-4" />Define kit</Button>
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.kit_product_id} loading={isLoading} />
      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>{editing === 'new' ? 'Define kit' : 'Edit kit'}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            {editing === 'new' && <div><Label>Kit product ID</Label><Input value={productId} onChange={(e) => setProductId(e.target.value)} /></div>}
            <div className="space-y-2">
              <Label>Components</Label>
              {components.map((c, i) => (
                <div key={i} className="grid grid-cols-12 gap-2">
                  <Input className="col-span-9" placeholder="Component product ID" value={c.component_product_id} onChange={(e) => setComponents((cs) => cs.map((x, idx) => idx === i ? { ...x, component_product_id: e.target.value } : x))} />
                  <Input className="col-span-2" type="number" min={1} value={c.quantity} onChange={(e) => setComponents((cs) => cs.map((x, idx) => idx === i ? { ...x, quantity: e.target.value } : x))} />
                  <Button className="col-span-1" size="sm" variant="ghost" onClick={() => setComponents((cs) => cs.filter((_, idx) => idx !== i))}>×</Button>
                </div>
              ))}
              <Button size="sm" variant="outline" onClick={() => setComponents((cs) => [...cs, { component_product_id: '', quantity: '1' }])}>+ Add component</Button>
            </div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button><Button onClick={save}>Save</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function LocationsPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Locations · Transfers · Kits" description="Multi-location inventory and product kits" />
      <Tabs defaultValue="locations">
        <TabsList>
          <TabsTrigger value="locations"><MapPin className="mr-2 h-4 w-4" />Locations</TabsTrigger>
          <TabsTrigger value="transfers"><Truck className="mr-2 h-4 w-4" />Transfers</TabsTrigger>
          <TabsTrigger value="kits"><Boxes className="mr-2 h-4 w-4" />Kits</TabsTrigger>
        </TabsList>
        <TabsContent value="locations" className="mt-4"><LocationsTab /></TabsContent>
        <TabsContent value="transfers" className="mt-4"><TransfersTab /></TabsContent>
        <TabsContent value="kits" className="mt-4"><KitsTab /></TabsContent>
      </Tabs>
    </div>
  );
}
