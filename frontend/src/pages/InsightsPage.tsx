import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Bot, LoaderCircle, ShieldCheck, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';
import { Label } from '@/components/ui/Label';
import StatusBadge, { type StatusTone } from '@/components/data/StatusBadge';
import { Skeleton, SkeletonCard } from '@/components/ui/Skeleton';
import EmptyState from '@/components/ui/EmptyState';
import { useAuthStore } from '@/store/auth';
import type { AIInsightStatus, AIInsightSummary } from '@/types';

const presetQuestions = [
  'What needs attention right now?',
  'Which products should we print or restock next?',
  'Where is margin weak or slipping?',
];

const priorityToTone: Record<'high' | 'medium' | 'low', StatusTone> = {
  high: 'destructive',
  medium: 'warning',
  low: 'success',
};

export default function InsightsPage() {
  const { user } = useAuthStore();
  const [question, setQuestion] = useState('');

  const { data: status, isLoading: statusLoading } = useQuery<AIInsightStatus>({
    queryKey: ['insights', 'status'],
    queryFn: () => api.get('/insights/status').then((r) => r.data),
  });

  const summaryMutation = useMutation({
    mutationFn: async (nextQuestion: string | null) =>
      api.post('/insights/summary', { question: nextQuestion || null }).then((r) => r.data as AIInsightSummary),
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to generate insights');
    },
  });

  const isAdmin = user?.role === 'admin';
  const summary = summaryMutation.data;

  const handleGenerate = async (nextQuestion?: string) => {
    const selected = nextQuestion ?? question;
    if (!status?.configured) {
      toast.error('Configure an AI provider in Admin Settings before generating insights.');
      return;
    }
    await summaryMutation.mutateAsync(selected.trim() || null);
  };

  if (statusLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-72" />
        <SkeletonCard rows={3} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Insights"
        description="Read-only business intelligence — explainable recommendations grounded in your app data. Analysis only, no autonomous writes."
      />

      {/* Provider summary */}
      <section className="rounded-md border border-border bg-card p-4 shadow-xs">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs text-muted-foreground">Active provider</p>
            <p className="mt-0.5 text-base font-semibold capitalize">{status?.provider || 'Unavailable'}</p>
            <p className="text-sm text-muted-foreground">{status?.model || 'No model selected'}</p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {status?.available_providers.map((provider) => (
              <StatusBadge
                key={provider}
                tone={provider === status.provider ? 'info' : 'neutral'}
                hideDot
              >
                <span className="capitalize">{provider}</span>
              </StatusBadge>
            ))}
          </div>
        </div>
        {status?.note ? (
          <p className="mt-3 flex items-start gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>{status.note}</span>
          </p>
        ) : null}
      </section>

      {/* Ask question */}
      <section className="rounded-md border border-border bg-card p-5 shadow-xs space-y-4">
        <h2 className="text-base font-semibold">Ask a focused question</h2>

        <div className="flex flex-wrap gap-2">
          {presetQuestions.map((item) => (
            <Button
              key={item}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setQuestion(item);
                void handleGenerate(item);
              }}
              disabled={summaryMutation.isPending}
            >
              {item}
            </Button>
          ))}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="insights-question" className="sr-only">
            Your question
          </Label>
          <Textarea
            id="insights-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={4}
            placeholder="Example: What should I print more of before the next market and what inventory is at risk?"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            onClick={() => void handleGenerate()}
            disabled={summaryMutation.isPending || !status?.configured}
          >
            {summaryMutation.isPending ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            {summaryMutation.isPending ? 'Generating insights…' : 'Generate Insight Summary'}
          </Button>
          {!status?.configured ? (
            <p className="text-sm text-muted-foreground">
              {isAdmin ? (
                <>
                  Configure a provider in{' '}
                  <Link to="/admin/settings" className="text-primary no-underline hover:underline">
                    Admin Settings
                  </Link>{' '}
                  first.
                </>
              ) : (
                'An admin must configure an AI provider before this workspace can generate insights.'
              )}
            </p>
          ) : null}
        </div>
      </section>

      {summary ? (
        <>
          {/* Summary header */}
          <section className="rounded-md border border-border bg-card p-5 shadow-xs">
            <div className="flex items-start gap-3">
              <Bot className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
              <div className="min-w-0">
                <p className="text-xs text-muted-foreground">
                  {summary.provider} · {summary.model}
                </p>
                <h2 className="mt-1 text-lg font-semibold">{summary.title}</h2>
                <p className="mt-2 text-sm text-muted-foreground">{summary.summary}</p>
                <p className="mt-2 text-xs text-muted-foreground">
                  Generated {new Date(summary.generated_at).toLocaleString()}
                </p>
                {summary.question ? (
                  <p className="mt-3 text-sm text-muted-foreground">Question: {summary.question}</p>
                ) : null}
              </div>
            </div>
          </section>

          {/* Recommendations + Risks */}
          <div className="grid gap-6 xl:grid-cols-2">
            <section className="rounded-md border border-border bg-card p-5 shadow-xs space-y-4">
              <h2 className="text-base font-semibold">Recommendations</h2>
              {summary.recommendations.length ? (
                <div className="space-y-3">
                  {summary.recommendations.map((item, index) => (
                    <article
                      key={`${item.title}-${index}`}
                      className="rounded-md border border-border bg-background p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <h3 className="text-sm font-semibold">{item.title}</h3>
                        <StatusBadge tone={priorityToTone[item.priority]} hideDot>
                          <span className="capitalize">{item.priority}</span>
                        </StatusBadge>
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground">{item.detail}</p>
                      {item.recommended_action ? (
                        <p className="mt-3 text-sm font-medium">Action: {item.recommended_action}</p>
                      ) : null}
                      {item.evidence.length ? (
                        <p className="mt-3 text-xs text-muted-foreground">
                          Evidence: {item.evidence.join(' · ')}
                        </p>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState compact icon="reports" title="No recommendations returned." />
              )}
            </section>

            <section className="rounded-md border border-border bg-card p-5 shadow-xs space-y-4">
              <h2 className="text-base font-semibold">Risks</h2>
              {summary.risks.length ? (
                <div className="space-y-3">
                  {summary.risks.map((item, index) => (
                    <article
                      key={`${item.title}-${index}`}
                      className="rounded-md border border-border bg-background p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <h3 className="text-sm font-semibold">{item.title}</h3>
                        <StatusBadge tone={priorityToTone[item.priority]} hideDot>
                          <span className="capitalize">{item.priority}</span>
                        </StatusBadge>
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground">{item.detail}</p>
                      {item.recommended_action ? (
                        <p className="mt-3 text-sm font-medium">Action: {item.recommended_action}</p>
                      ) : null}
                      {item.evidence.length ? (
                        <p className="mt-3 text-xs text-muted-foreground">
                          Evidence: {item.evidence.join(' · ')}
                        </p>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState compact icon="reports" title="No risks returned." />
              )}
            </section>
          </div>

          {/* Evidence + follow-ups */}
          <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
            <section className="rounded-md border border-border bg-card p-5 shadow-xs space-y-4">
              <h2 className="text-base font-semibold">Evidence metrics</h2>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {summary.evidence_metrics.map((metric) => (
                  <div
                    key={metric.key}
                    className="rounded-md border border-border bg-background p-3"
                  >
                    <p className="text-xs text-muted-foreground">{metric.label}</p>
                    <p className="mt-0.5 text-lg font-semibold tabular-nums">{metric.value}</p>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-md border border-border bg-card p-5 shadow-xs space-y-3">
              <h2 className="text-base font-semibold">Suggested follow-ups</h2>
              {summary.suggested_questions.length ? (
                <div className="flex flex-col gap-2">
                  {summary.suggested_questions.map((item) => (
                    <Button
                      key={item}
                      type="button"
                      variant="outline"
                      size="sm"
                      className="w-full justify-start text-left font-normal"
                      onClick={() => {
                        setQuestion(item);
                        void handleGenerate(item);
                      }}
                      disabled={summaryMutation.isPending}
                    >
                      {item}
                    </Button>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No follow-up questions returned.</p>
              )}
            </section>
          </div>
        </>
      ) : null}
    </div>
  );
}
