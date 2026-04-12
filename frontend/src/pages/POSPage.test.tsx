import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import POSPage from '@/pages/POSPage';
import api from '@/api/client';

const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock('sonner', () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
  },
}));

vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const apiGet = api.get as unknown as Mock;
const apiPost = api.post as unknown as Mock;

const productsResponse = {
  items: [
    {
      id: 'product-1',
      sku: 'POS-DRAGON-001',
      upc: null,
      name: 'Desk Dragon',
      description: 'Flexible dragon fidget',
      material_id: 'material-1',
      unit_cost: 6,
      unit_price: 15,
      stock_qty: 5,
      reorder_point: 2,
      is_active: true,
      created_at: null,
      updated_at: null,
    },
  ],
  total: 1,
  skip: 0,
  limit: 200,
};

const customersResponse = [
  {
    id: 'customer-1',
    name: 'Morgan Buyer',
    email: 'morgan@example.com',
    phone: null,
    notes: null,
    job_count: 0,
  },
];

function renderPOSPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <POSPage />
      </QueryClientProvider>
    </MemoryRouter>
  );
}

describe('POSPage', () => {
  beforeEach(() => {
    toastSuccess.mockReset();
    toastError.mockReset();
    apiGet.mockReset();
    apiPost.mockReset();

    apiGet.mockImplementation((url: string) => {
      if (url === '/products') {
        return Promise.resolve({ data: productsResponse });
      }
      if (url === '/customers') {
        return Promise.resolve({ data: customersResponse });
      }
      return Promise.reject(new Error(`Unexpected GET ${url}`));
    });
  });

  it('adds items, updates quantities, recalculates totals, and removes cart lines', async () => {
    const user = userEvent.setup();
    renderPOSPage();

    await screen.findByText('Desk Dragon');

    await user.click(screen.getByRole('button', { name: 'Add Desk Dragon to cart' }));

    expect(screen.getByLabelText('Desk Dragon quantity')).toHaveTextContent('1');
    expect(screen.getByText('$15.00 each')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Increase quantity for Desk Dragon' }));

    expect(screen.getByLabelText('Desk Dragon quantity')).toHaveTextContent('2');
    expect(screen.getAllByText('$30.00').length).toBeGreaterThan(0);

    const taxInput = screen.getByLabelText('Tax collected');
    await user.clear(taxInput);
    await user.type(taxInput, '2.5');

    expect(screen.getAllByText('$32.50').length).toBeGreaterThan(0);

    await user.click(screen.getByRole('button', { name: 'Decrease quantity for Desk Dragon' }));

    expect(screen.getByLabelText('Desk Dragon quantity')).toHaveTextContent('1');

    await user.click(screen.getByRole('button', { name: 'Remove Desk Dragon from cart' }));

    expect(screen.getByText('Cart is empty')).toBeInTheDocument();
  });

  it('submits checkout successfully and clears the cart for the next customer', async () => {
    const user = userEvent.setup();
    apiPost.mockResolvedValue({
      data: {
        id: 'sale-1',
        sale_number: 'S-2026-0001',
        total: 17.5,
      },
    });

    renderPOSPage();

    await screen.findByText('Desk Dragon');
    await user.click(screen.getByRole('button', { name: 'Add Desk Dragon to cart' }));
    await user.click(screen.getByRole('button', { name: 'Existing customer Attach the sale to an existing customer record.' }));
    await user.selectOptions(screen.getByLabelText('Existing customer'), 'customer-1');

    const taxInput = screen.getByLabelText('Tax collected');
    await user.clear(taxInput);
    await user.type(taxInput, '2.5');

    await user.click(screen.getByRole('button', { name: 'Card' }));
    await user.type(screen.getByLabelText('Notes'), 'Booth sale');
    await user.click(screen.getByRole('button', { name: 'Complete checkout' }));

    await waitFor(() => {
      expect(apiPost).toHaveBeenCalledWith('/pos/checkout', {
        date: expect.any(String),
        customer_id: 'customer-1',
        customer_name: null,
        tax_collected: 2.5,
        payment_method: 'card',
        notes: 'Booth sale',
        items: [
          {
            product_id: 'product-1',
            description: 'Desk Dragon',
            quantity: 1,
            unit_price: 15,
            unit_cost: 6,
          },
        ],
      });
    });

    expect(await screen.findByRole('status')).toHaveTextContent('Sale S-2026-0001 completed');
    expect(screen.getByText('Cart is empty')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cash' })).toHaveAttribute('aria-pressed', 'true');
    expect(toastSuccess).toHaveBeenCalledWith('POS checkout complete: S-2026-0001');
  });

  it('shows checkout API errors without clearing the cart', async () => {
    const user = userEvent.setup();
    apiPost.mockRejectedValue({
      response: {
        data: {
          detail: 'Insufficient stock for POS checkout: Desk Dragon only has 1 available',
        },
      },
    });

    renderPOSPage();

    await screen.findByText('Desk Dragon');
    await user.click(screen.getByRole('button', { name: 'Add Desk Dragon to cart' }));
    await user.click(screen.getByRole('button', { name: 'Complete checkout' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Insufficient stock for POS checkout');
    expect(screen.getByLabelText('Desk Dragon quantity')).toHaveTextContent('1');
    expect(toastError).toHaveBeenCalledWith(
      'Insufficient stock for POS checkout: Desk Dragon only has 1 available'
    );
  });

  it('adds a product from the barcode scan lane', async () => {
    const user = userEvent.setup();
    apiPost.mockImplementation((url: string, payload?: unknown) => {
      if (url === '/pos/scan/resolve') {
        expect(payload).toEqual({ code: '012345678901' });
        return Promise.resolve({ data: productsResponse.items[0] });
      }
      return Promise.reject(new Error(`Unexpected POST ${url}`));
    });

    renderPOSPage();

    await screen.findByText('Desk Dragon');
    await user.type(screen.getByLabelText('Scan barcode'), '012345678901{enter}');

    expect(await screen.findByText('Scanned Desk Dragon (POS-DRAGON-001)')).toBeInTheDocument();
    expect(screen.getByLabelText('Desk Dragon quantity')).toHaveTextContent('1');
    expect(toastSuccess).toHaveBeenCalledWith('Scanned Desk Dragon');
  });

  it('shows barcode scan errors without mutating the cart', async () => {
    const user = userEvent.setup();
    apiPost.mockRejectedValue({
      response: {
        data: {
          detail: "No active product matches barcode '000000000000'",
        },
      },
    });

    renderPOSPage();

    await screen.findByText('Desk Dragon');
    await user.type(screen.getByLabelText('Scan barcode'), '000000000000{enter}');

    expect(await screen.findByText("No active product matches barcode '000000000000'")).toBeInTheDocument();
    expect(screen.getByText('Cart is empty')).toBeInTheDocument();
    expect(toastError).toHaveBeenCalledWith("No active product matches barcode '000000000000'");
  });
});
