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
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { getApiErrorMessage } from '@/lib/apiError';

interface Division { id: string; code: string; name: string; active: boolean }
interface Project { id: string; code: string; name: string; division_id: string | null; active: boolean }
interface Budget { id: string; account_id: string; year: number; month: number; amount: number }
interface CFDef { id: string; scope: string; field_name: string; label: string; field_type: string; required: boolean; active: boolean }

function DivisionsTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<Division[]>({ queryKey: ['divisions'], queryFn: () => api.get('/divisions').then((r) => r.data) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ code: '', name: '' });
  const save = async () => {
    try { await api.post('/divisions', form); toast.success('Created'); qc.invalidateQueries({ queryKey: ['divisions'] }); setOpen(false); setForm({ code: '', name: '' }); }
    catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  const cols: Column<Division>[] = [
    { key: 'c', header: 'Code', cell: (r) => <span className="font-mono">{r.code}</span> },
    { key: 'n', header: 'Name', cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'a', header: 'Active', cell: (r) => (r.active ? 'yes' : 'no') },
  ];
  return (
    <div className="space-y-3">
      <Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />New division</Button>
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>New division</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Code</Label><Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></div>
            <div><Label>Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={save}>Create</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ProjectsTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<Project[]>({ queryKey: ['projects'], queryFn: () => api.get('/projects').then((r) => r.data) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ code: '', name: '', division_id: '' });
  const save = async () => {
    try { await api.post('/projects', { ...form, division_id: form.division_id || null }); toast.success('Created'); qc.invalidateQueries({ queryKey: ['projects'] }); setOpen(false); setForm({ code: '', name: '', division_id: '' }); }
    catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  const cols: Column<Project>[] = [
    { key: 'c', header: 'Code', cell: (r) => <span className="font-mono">{r.code}</span> },
    { key: 'n', header: 'Name', cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'd', header: 'Division', cell: (r) => (r.division_id || '—').slice(0, 8) },
    { key: 'a', header: 'Active', cell: (r) => (r.active ? 'yes' : 'no') },
  ];
  return (
    <div className="space-y-3">
      <Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />New project</Button>
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>New project</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Code</Label><Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></div>
            <div><Label>Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div><Label>Division ID (opt.)</Label><Input value={form.division_id} onChange={(e) => setForm({ ...form, division_id: e.target.value })} /></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={save}>Create</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function BudgetsTab() {
  const qc = useQueryClient();
  const [year, setYear] = useState(new Date().getFullYear());
  const { data, isLoading } = useQuery<Budget[]>({ queryKey: ['budgets', year], queryFn: () => api.get('/budgets', { params: { year } }).then((r) => r.data) });
  const [form, setForm] = useState({ account_id: '', year: String(new Date().getFullYear()), month: '1', amount: '0' });
  const upsert = async () => {
    try {
      await api.post('/budgets/upsert', [{ account_id: form.account_id, year: Number(form.year), month: Number(form.month), amount: form.amount }]);
      toast.success('Saved');
      qc.invalidateQueries({ queryKey: ['budgets'] });
      setForm({ ...form, account_id: '', amount: '0' });
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  const remove = async (id: string) => {
    try { await api.delete(`/budgets/${id}`); qc.invalidateQueries({ queryKey: ['budgets'] }); toast.success('Removed'); }
    catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  const cols: Column<Budget>[] = [
    { key: 'a', header: 'Account', cell: (r) => r.account_id.slice(0, 8) },
    { key: 'y', header: 'Year', numeric: true, cell: (r) => r.year },
    { key: 'm', header: 'Month', numeric: true, cell: (r) => r.month },
    { key: 'amt', header: 'Amount', numeric: true, cell: (r) => `$${Number(r.amount).toFixed(2)}` },
    { key: 'x', header: '', width: '60px', cell: (r) => <Button size="icon" variant="ghost" onClick={() => remove(r.id)}><Trash2 className="h-4 w-4" /></Button> },
  ];
  return (
    <div className="space-y-3">
      <div className="flex items-end gap-2 rounded-lg border bg-card p-3">
        <div><Label>Year filter</Label><Input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} /></div>
      </div>
      <div className="flex flex-wrap items-end gap-2 rounded-lg border bg-card p-3">
        <div><Label>Account ID</Label><Input value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })} /></div>
        <div><Label>Year</Label><Input type="number" value={form.year} onChange={(e) => setForm({ ...form, year: e.target.value })} /></div>
        <div><Label>Month</Label><Input type="number" min={1} max={12} value={form.month} onChange={(e) => setForm({ ...form, month: e.target.value })} /></div>
        <div><Label>Amount</Label><Input type="number" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} /></div>
        <Button onClick={upsert}>Upsert</Button>
      </div>
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />
    </div>
  );
}

function CustomFieldsTab() {
  const qc = useQueryClient();
  const [scope, setScope] = useState('customer');
  const { data, isLoading } = useQuery<CFDef[]>({ queryKey: ['cf-defs', scope], queryFn: () => api.get(`/custom-fields/${scope}`).then((r) => r.data) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ scope: 'customer', field_name: '', label: '', field_type: 'text', required: false });
  const save = async () => {
    try { await api.post('/custom-fields', form); toast.success('Created'); qc.invalidateQueries({ queryKey: ['cf-defs'] }); setOpen(false); }
    catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  const cols: Column<CFDef>[] = [
    { key: 'f', header: 'Field name', cell: (r) => <span className="font-mono">{r.field_name}</span> },
    { key: 'l', header: 'Label', cell: (r) => r.label },
    { key: 't', header: 'Type', cell: (r) => r.field_type },
    { key: 'r', header: 'Required', cell: (r) => (r.required ? 'yes' : 'no') },
    { key: 'a', header: 'Active', cell: (r) => (r.active ? 'yes' : 'no') },
  ];
  return (
    <div className="space-y-3">
      <div className="flex items-end gap-2">
        <div>
          <Label>Scope</Label>
          <select className="mt-1 block rounded-md border bg-background px-2 py-2 text-sm" value={scope} onChange={(e) => setScope(e.target.value)}>
            {['customer','vendor','product','material','supply','invoice','quote','sale','bill'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <Button onClick={() => { setForm({ ...form, scope }); setOpen(true); }}><Plus className="mr-2 h-4 w-4" />New field</Button>
      </div>
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>New custom field</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Field name</Label><Input value={form.field_name} onChange={(e) => setForm({ ...form, field_name: e.target.value })} /></div>
            <div><Label>Label</Label><Input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} /></div>
            <div>
              <Label>Type</Label>
              <select className="mt-1 block w-full rounded-md border bg-background px-2 py-2 text-sm" value={form.field_type} onChange={(e) => setForm({ ...form, field_type: e.target.value })}>
                <option value="text">text</option><option value="number">number</option><option value="date">date</option><option value="boolean">boolean</option><option value="select">select</option>
              </select>
            </div>
            <div className="flex items-center gap-2"><input id="req" type="checkbox" checked={form.required} onChange={(e) => setForm({ ...form, required: e.target.checked })} /><Label htmlFor="req">Required</Label></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={save}>Create</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function BatchOpsTab() {
  const [scope, setScope] = useState('customer');
  const [ids, setIds] = useState('');
  const run = async (verb: 'deactivate' | 'activate' | 'delete') => {
    try {
      const arr = ids.split(',').map((s) => s.trim()).filter(Boolean);
      const res = await api.post(`/batch/${scope}/${verb}`, { ids: arr });
      toast.success(`Processed: ${res.data?.processed ?? arr.length}`);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  return (
    <div className="space-y-3 rounded-lg border bg-card p-4">
      <div>
        <Label>Scope</Label>
        <select className="mt-1 block rounded-md border bg-background px-2 py-2 text-sm" value={scope} onChange={(e) => setScope(e.target.value)}>
          {['customer','vendor','product','material','supply'].map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <div><Label>IDs (comma-separated)</Label><Input value={ids} onChange={(e) => setIds(e.target.value)} /></div>
      <div className="flex gap-2">
        <Button variant="outline" onClick={() => run('deactivate')}>Deactivate</Button>
        <Button variant="outline" onClick={() => run('activate')}>Activate</Button>
        <Button variant="destructive" onClick={() => run('delete')}>Delete</Button>
      </div>
    </div>
  );
}

export default function MasterDataPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Master data" description="Divisions, projects, budgets, custom fields, batch operations" />
      <Tabs defaultValue="divisions">
        <TabsList>
          <TabsTrigger value="divisions">Divisions</TabsTrigger>
          <TabsTrigger value="projects">Projects</TabsTrigger>
          <TabsTrigger value="budgets">Budgets</TabsTrigger>
          <TabsTrigger value="custom-fields">Custom fields</TabsTrigger>
          <TabsTrigger value="batch">Batch ops</TabsTrigger>
        </TabsList>
        <TabsContent value="divisions" className="mt-4"><DivisionsTab /></TabsContent>
        <TabsContent value="projects" className="mt-4"><ProjectsTab /></TabsContent>
        <TabsContent value="budgets" className="mt-4"><BudgetsTab /></TabsContent>
        <TabsContent value="custom-fields" className="mt-4"><CustomFieldsTab /></TabsContent>
        <TabsContent value="batch" className="mt-4"><BatchOpsTab /></TabsContent>
      </Tabs>
    </div>
  );
}
