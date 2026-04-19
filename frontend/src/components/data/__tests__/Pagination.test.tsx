import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Pagination from '@/components/data/Pagination';

describe('Pagination', () => {
  it('shows "Showing N–M of T" for a mid-range page', () => {
    render(<Pagination page={1} pageSize={25} total={100} onPageChange={() => {}} />);
    // page=1 (0-indexed) = rows 26-50
    expect(screen.getByText(/Showing 26–50 of 100/)).toBeTruthy();
  });

  it('shows "No results" when total is 0', () => {
    render(<Pagination page={0} pageSize={25} total={0} onPageChange={() => {}} />);
    expect(screen.getByText('No results')).toBeTruthy();
  });

  it('disables first/prev on page 0', () => {
    render(<Pagination page={0} pageSize={25} total={100} onPageChange={() => {}} />);
    expect(screen.getByLabelText('First page').hasAttribute('disabled')).toBe(true);
    expect(screen.getByLabelText('Previous page').hasAttribute('disabled')).toBe(true);
  });

  it('disables next/last on final page', () => {
    render(<Pagination page={3} pageSize={25} total={100} onPageChange={() => {}} />);
    expect(screen.getByLabelText('Next page').hasAttribute('disabled')).toBe(true);
    expect(screen.getByLabelText('Last page').hasAttribute('disabled')).toBe(true);
  });

  it('calls onPageChange with correct indices', () => {
    const onPageChange = vi.fn();
    render(<Pagination page={1} pageSize={10} total={100} onPageChange={onPageChange} />);
    fireEvent.click(screen.getByLabelText('First page'));
    expect(onPageChange).toHaveBeenCalledWith(0);

    fireEvent.click(screen.getByLabelText('Previous page'));
    expect(onPageChange).toHaveBeenCalledWith(0);

    fireEvent.click(screen.getByLabelText('Next page'));
    expect(onPageChange).toHaveBeenCalledWith(2);

    fireEvent.click(screen.getByLabelText('Last page'));
    expect(onPageChange).toHaveBeenCalledWith(9); // 100/10 = 10 pages, last index = 9
  });

  it('shows page-size select when onPageSizeChange is provided', () => {
    const onPageSizeChange = vi.fn();
    render(
      <Pagination
        page={0}
        pageSize={25}
        total={100}
        onPageChange={() => {}}
        onPageSizeChange={onPageSizeChange}
      />,
    );
    const sel = screen.getByLabelText('Rows per page') as HTMLSelectElement;
    expect(sel).toBeTruthy();
    fireEvent.change(sel, { target: { value: '50' } });
    expect(onPageSizeChange).toHaveBeenCalledWith(50);
  });
});
