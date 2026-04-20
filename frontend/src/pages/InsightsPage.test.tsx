import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import InsightsPage from '@/pages/InsightsPage';
import api from '@/api/client';

const toastError = vi.fn();

vi.mock('sonner', () => ({
  toast: {
    error: (...args: unknown[]) => toastError(...args),
  },
}));

vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({
    user: { id: 'admin-1', role: 'admin' },
  }),
}));

const apiGet = api.get as unknown as Mock;
const apiPost = api.post as unknown as Mock;

function renderInsightsPage() {
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
        <InsightsPage />
      </QueryClientProvider>
    </MemoryRouter>
  );
}

describe('InsightsPage', () => {
  beforeEach(() => {
    toastError.mockReset();
    apiGet.mockReset();
    apiPost.mockReset();
  });

  it('surfaces admin configuration guidance when no provider is configured', async () => {
    apiGet.mockResolvedValue({
      data: {
        provider: 'chatgpt',
        model: 'gpt-4.1-mini',
        configured: false,
        available_providers: ['chatgpt', 'claude', 'grok'],
        note: 'Read-only recommendations only.',
      },
    });

    renderInsightsPage();

    expect(await screen.findByText('AI Insights')).toBeInTheDocument();
    expect(screen.getByText(/Configure a provider in/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Admin Settings' })).toHaveAttribute('href', '/admin/settings');
    expect(screen.getByRole('button', { name: 'Generate Insight Summary' })).toBeDisabled();
  });

  it('generates an insight summary from the focused question flow', async () => {
    const user = userEvent.setup();
    apiGet.mockResolvedValue({
      data: {
        provider: 'claude',
        model: 'claude-3-5-sonnet-latest',
        configured: true,
        available_providers: ['chatgpt', 'claude', 'grok'],
        note: 'Read-only recommendations only.',
      },
    });
    apiPost.mockResolvedValue({
      data: {
        provider: 'claude',
        model: 'claude-3-5-sonnet-latest',
        generated_at: '2026-04-13T12:00:00Z',
        title: 'Craft fair readiness',
        summary: 'Restock Desk Dragon and review margin on low-volume add-ons.',
        question: 'What should I print more of before the next craft fair?',
        recommendations: [
          {
            title: 'Print more Desk Dragon',
            detail: 'Demand is outpacing on-hand stock.',
            priority: 'high',
            evidence: ['Low stock alerts', 'Gross sales'],
            recommended_action: 'Queue a replenishment run this week.',
          },
        ],
        risks: [],
        suggested_questions: ['Which products have weak margins?'],
        evidence_metrics: [
          { key: 'gross_sales', label: 'Gross sales', value: '$1200.00' },
        ],
        read_only: true,
      },
    });

    renderInsightsPage();

    await screen.findByText('AI Insights');
    await user.type(
      screen.getByPlaceholderText('Example: What should I print more of before the next market and what inventory is at risk?'),
      'What should I print more of before the next craft fair?'
    );
    await user.click(screen.getByRole('button', { name: 'Generate Insight Summary' }));

    await waitFor(() => {
      expect(apiPost).toHaveBeenCalledWith('/insights/summary', {
        question: 'What should I print more of before the next craft fair?',
      });
    });

    expect(await screen.findByText('Craft fair readiness')).toBeInTheDocument();
    expect(screen.getByText('Print more Desk Dragon')).toBeInTheDocument();
    expect(screen.getByText('Which products have weak margins?')).toBeInTheDocument();
  });
});
