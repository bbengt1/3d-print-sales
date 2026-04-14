import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Bot, BrainCircuit, LoaderCircle, ShieldCheck, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import api from '@/api/client';
import { useAuthStore } from '@/store/auth';
import type { AIInsightStatus, AIInsightSummary } from '@/types';

const presetQuestions = [
  'What needs attention right now?',
  'Which products should we print or restock next?',
  'Where is margin weak or slipping?',
];

function PriorityBadge({ value }: { value: 'high' | 'medium' | 'low' }) {
  const classes =
    value === 'high'
      ? 'border-red-300 bg-red-50 text-red-800'
      : value === 'medium'
        ? 'border-amber-300 bg-amber-50 text-amber-800'
        : 'border-emerald-300 bg-emerald-50 text-emerald-800';

  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${classes}`}>
      {value}
    </span>
  );
}

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
    return <div className="space-y-6"><div className="h-12 w-72 animate-pulse rounded-2xl bg-card" /><div className="h-64 animate-pulse rounded-3xl bg-card" /></div>;
  }

  return (
    <div className="space-y-8">
      <section className="rounded-[2rem] border border-border bg-card/90 p-6 shadow-[0_18px_50px_rgba(8,17,31,0.08)]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
              <BrainCircuit className="h-4 w-4" />
              AI Insights
            </div>
            <h1 className="mt-4 text-3xl font-bold">Read-only business intelligence</h1>
            <p className="mt-3 text-base text-muted-foreground">
              Ask for explainable recommendations grounded in your app data. This surface is analysis only: no autonomous writes, no silent pricing changes, and no hidden inventory actions.
            </p>
          </div>
          <div className="rounded-[1.5rem] border border-border bg-background/80 p-4 text-sm">
            <p className="font-semibold text-foreground">Active provider</p>
            <p className="mt-2 text-lg font-semibold capitalize">{status?.provider || 'Unavailable'}</p>
            <p className="text-muted-foreground">{status?.model || 'No model selected'}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {status?.available_providers.map((provider) => {
                const isActive = provider === status.provider;
                return (
                  <span
                    key={provider}
                    className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${
                      isActive
                        ? 'border-primary/30 bg-primary/10 text-primary'
                        : 'border-border bg-card text-muted-foreground'
                    }`}
                  >
                    {provider}
                  </span>
                );
              })}
            </div>
            <div className="mt-3 flex items-start gap-2 text-xs text-muted-foreground">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{status?.note}</span>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-[2rem] border border-border bg-card/90 p-6 shadow-[0_18px_50px_rgba(8,17,31,0.08)]">
        <div className="flex flex-col gap-4">
          <div>
            <h2 className="text-xl font-semibold">Ask a focused question</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Hick&apos;s Law applies here: start from one clear question instead of dumping every business concern into one prompt.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {presetQuestions.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => {
                  setQuestion(item);
                  void handleGenerate(item);
                }}
                className="rounded-full border border-border px-4 py-2 text-sm font-medium transition-colors hover:border-primary/35 hover:bg-primary/5"
              >
                {item}
              </button>
            ))}
          </div>

          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={4}
            placeholder="Example: What should I print more of before the next market and what inventory is at risk?"
            className="w-full rounded-[1.5rem] border border-input bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => void handleGenerate()}
              disabled={summaryMutation.isPending || !status?.configured}
              className="inline-flex min-h-12 items-center justify-center gap-2 rounded-2xl bg-primary px-5 py-3 font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
            >
              {summaryMutation.isPending ? <LoaderCircle className="h-5 w-5 animate-spin" /> : <Sparkles className="h-5 w-5" />}
              {summaryMutation.isPending ? 'Generating insights...' : 'Generate Insight Summary'}
            </button>
            {!status?.configured ? (
              <p className="text-sm text-muted-foreground">
                {isAdmin ? (
                  <>
                    Configure a provider in <Link to="/admin/settings" className="text-primary no-underline hover:underline">Admin Settings</Link> first.
                  </>
                ) : (
                  'An admin must configure an AI provider before this workspace can generate insights.'
                )}
              </p>
            ) : null}
          </div>
        </div>
      </section>

      {summary ? (
        <>
          <section className="rounded-[2rem] border border-border bg-card/90 p-6 shadow-[0_18px_50px_rgba(8,17,31,0.08)]">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary/12 text-primary">
                <Bot className="h-6 w-6" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  {summary.provider} • {summary.model}
                </p>
                <h2 className="mt-2 text-2xl font-semibold">{summary.title}</h2>
                <p className="mt-3 text-base text-muted-foreground">{summary.summary}</p>
                <p className="mt-3 text-xs text-muted-foreground">
                  Generated {new Date(summary.generated_at).toLocaleString()}
                </p>
                {summary.question ? (
                  <p className="mt-4 text-sm text-muted-foreground">Question: {summary.question}</p>
                ) : null}
              </div>
            </div>
          </section>

          <section className="grid gap-6 xl:grid-cols-2">
            <div className="rounded-[2rem] border border-border bg-card/90 p-6 shadow-[0_18px_50px_rgba(8,17,31,0.08)]">
              <h3 className="text-xl font-semibold">Recommendations</h3>
              <div className="mt-4 space-y-4">
                {summary.recommendations.length ? summary.recommendations.map((item, index) => (
                  <article key={`${item.title}-${index}`} className="rounded-[1.5rem] border border-border bg-background/80 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <h4 className="font-semibold">{item.title}</h4>
                      <PriorityBadge value={item.priority} />
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">{item.detail}</p>
                    {item.recommended_action ? <p className="mt-3 text-sm font-medium text-foreground">Action: {item.recommended_action}</p> : null}
                    {item.evidence.length ? <p className="mt-3 text-xs text-muted-foreground">Evidence: {item.evidence.join(' • ')}</p> : null}
                  </article>
                )) : <p className="text-sm text-muted-foreground">No recommendations returned.</p>}
              </div>
            </div>

            <div className="rounded-[2rem] border border-border bg-card/90 p-6 shadow-[0_18px_50px_rgba(8,17,31,0.08)]">
              <h3 className="text-xl font-semibold">Risks</h3>
              <div className="mt-4 space-y-4">
                {summary.risks.length ? summary.risks.map((item, index) => (
                  <article key={`${item.title}-${index}`} className="rounded-[1.5rem] border border-border bg-background/80 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <h4 className="font-semibold">{item.title}</h4>
                      <PriorityBadge value={item.priority} />
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">{item.detail}</p>
                    {item.recommended_action ? <p className="mt-3 text-sm font-medium text-foreground">Action: {item.recommended_action}</p> : null}
                    {item.evidence.length ? <p className="mt-3 text-xs text-muted-foreground">Evidence: {item.evidence.join(' • ')}</p> : null}
                  </article>
                )) : <p className="text-sm text-muted-foreground">No risks returned.</p>}
              </div>
            </div>
          </section>

          <section className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
            <div className="rounded-[2rem] border border-border bg-card/90 p-6 shadow-[0_18px_50px_rgba(8,17,31,0.08)]">
              <h3 className="text-xl font-semibold">Evidence metrics</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Jakob&apos;s Law and Common Region: the recommendation copy stays separate from the source-of-truth numbers it references.
              </p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {summary.evidence_metrics.map((metric) => (
                  <div key={metric.key} className="rounded-[1.3rem] border border-border bg-background/80 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">{metric.label}</p>
                    <p className="mt-2 text-xl font-semibold">{metric.value}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-[2rem] border border-border bg-card/90 p-6 shadow-[0_18px_50px_rgba(8,17,31,0.08)]">
              <h3 className="text-xl font-semibold">Suggested follow-ups</h3>
              <div className="mt-4 space-y-3">
                {summary.suggested_questions.length ? summary.suggested_questions.map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => {
                      setQuestion(item);
                      void handleGenerate(item);
                    }}
                    className="block w-full rounded-[1.3rem] border border-border bg-background/80 px-4 py-3 text-left text-sm font-medium transition-colors hover:border-primary/35 hover:bg-primary/5"
                  >
                    {item}
                  </button>
                )) : <p className="text-sm text-muted-foreground">No follow-up questions returned.</p>}
              </div>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
