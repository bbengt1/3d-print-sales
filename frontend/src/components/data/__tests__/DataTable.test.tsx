import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DataTable, type Column } from '@/components/data/DataTable';

interface Row {
  id: string;
  name: string;
  amount: number;
}

const rows: Row[] = [
  { id: '1', name: 'Alpha', amount: 100 },
  { id: '2', name: 'Beta', amount: 250 },
  { id: '3', name: 'Gamma', amount: 42 },
];

const columns: Column<Row>[] = [
  { key: 'name', header: 'Name', sortable: true, cell: (r) => r.name },
  { key: 'amount', header: 'Amount', sortable: true, numeric: true, cell: (r) => String(r.amount) },
];

describe('DataTable', () => {
  it('renders all rows and column headers', () => {
    render(<DataTable data={rows} columns={columns} rowKey={(r) => r.id} />);
    expect(screen.getByText('Name')).toBeTruthy();
    expect(screen.getByText('Amount')).toBeTruthy();
    expect(screen.getByText('Alpha')).toBeTruthy();
    expect(screen.getByText('Beta')).toBeTruthy();
    expect(screen.getByText('Gamma')).toBeTruthy();
  });

  it('shows empty state when data is empty', () => {
    render(
      <DataTable
        data={[]}
        columns={columns}
        rowKey={(r) => r.id}
        emptyState="Nothing here yet"
      />,
    );
    expect(screen.getByText('Nothing here yet')).toBeTruthy();
  });

  it('cycles sort state asc → desc → unsorted when a sortable header is clicked', () => {
    const onSortChange = vi.fn();
    const { rerender } = render(
      <DataTable data={rows} columns={columns} rowKey={(r) => r.id} onSortChange={onSortChange} />,
    );

    fireEvent.click(screen.getByText('Name'));
    expect(onSortChange).toHaveBeenCalledWith('name', 'asc');

    rerender(
      <DataTable
        data={rows}
        columns={columns}
        rowKey={(r) => r.id}
        onSortChange={onSortChange}
        sortKey="name"
        sortDir="asc"
      />,
    );
    fireEvent.click(screen.getByText('Name'));
    expect(onSortChange).toHaveBeenCalledWith('name', 'desc');

    rerender(
      <DataTable
        data={rows}
        columns={columns}
        rowKey={(r) => r.id}
        onSortChange={onSortChange}
        sortKey="name"
        sortDir="desc"
      />,
    );
    fireEvent.click(screen.getByText('Name'));
    expect(onSortChange).toHaveBeenCalledWith('', null);
  });

  it('toggles selection on a single row', () => {
    const onSelectedChange = vi.fn();
    render(
      <DataTable
        data={rows}
        columns={columns}
        rowKey={(r) => r.id}
        selectable
        selected={new Set()}
        onSelectedChange={onSelectedChange}
      />,
    );
    const rowCheckboxes = screen.getAllByLabelText(/Select row|Deselect row/);
    fireEvent.click(rowCheckboxes[0]);
    expect(onSelectedChange).toHaveBeenCalledWith(new Set(['1']));
  });

  it('select-all toggle selects every row then deselects', () => {
    const onSelectedChange = vi.fn();
    const { rerender } = render(
      <DataTable
        data={rows}
        columns={columns}
        rowKey={(r) => r.id}
        selectable
        selected={new Set()}
        onSelectedChange={onSelectedChange}
      />,
    );
    const headerCheckbox = screen.getByLabelText('Select all rows');
    fireEvent.click(headerCheckbox);
    expect(onSelectedChange).toHaveBeenCalledWith(new Set(['1', '2', '3']));

    // Now render with all selected, header should be checked and clicking should clear
    onSelectedChange.mockClear();
    rerender(
      <DataTable
        data={rows}
        columns={columns}
        rowKey={(r) => r.id}
        selectable
        selected={new Set(['1', '2', '3'])}
        onSelectedChange={onSelectedChange}
      />,
    );
    fireEvent.click(screen.getByLabelText('Deselect all rows'));
    expect(onSelectedChange).toHaveBeenCalledWith(new Set());
  });

  it('calls onRowClick when a row is clicked (but not when a checkbox is clicked)', () => {
    const onRowClick = vi.fn();
    const onSelectedChange = vi.fn();
    render(
      <DataTable
        data={rows}
        columns={columns}
        rowKey={(r) => r.id}
        onRowClick={onRowClick}
        selectable
        selected={new Set()}
        onSelectedChange={onSelectedChange}
      />,
    );

    // Clicking the cell triggers rowClick
    fireEvent.click(screen.getByText('Alpha'));
    expect(onRowClick).toHaveBeenCalledWith(rows[0]);

    // Clicking a checkbox does NOT trigger rowClick
    onRowClick.mockClear();
    const rowCheckbox = screen.getAllByLabelText(/Select row|Deselect row/)[1];
    fireEvent.click(rowCheckbox);
    expect(onRowClick).not.toHaveBeenCalled();
  });

  it('renders loading skeleton rows', () => {
    const { container } = render(
      <DataTable data={[]} columns={columns} rowKey={(r) => r.id} loading />,
    );
    const skeletons = container.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });
});
