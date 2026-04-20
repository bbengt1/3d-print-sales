import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { QueryErrorResetBoundary } from '@tanstack/react-query';
import { Button } from '@/components/ui/Button';

interface InnerProps {
  children: ReactNode;
  onReset: () => void;
  fallback?: (args: { error: Error; reset: () => void }) => ReactNode;
}

interface InnerState {
  error: Error | null;
}

class InnerBoundary extends Component<InnerProps, InnerState> {
  state: InnerState = { error: null };

  static getDerivedStateFromError(error: Error): InnerState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (import.meta.env.DEV) {
      // eslint-disable-next-line no-console
      console.error('[QueryErrorBoundary]', error, info);
    }
  }

  reset = () => {
    this.props.onReset();
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback({ error: this.state.error, reset: this.reset });
      return (
        <div className="flex flex-col items-center justify-center rounded-md border border-destructive/30 bg-destructive/5 px-4 py-16 text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-destructive/10">
            <AlertTriangle className="h-7 w-7 text-destructive" aria-hidden="true" />
          </div>
          <h3 className="mb-1 text-lg font-semibold">Something went wrong</h3>
          <p className="mb-6 max-w-md text-sm text-muted-foreground">
            {this.state.error.message || 'The page could not load its data.'}
          </p>
          <Button type="button" variant="outline" onClick={this.reset}>
            <RefreshCw className="h-4 w-4" /> Try again
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}

interface QueryErrorBoundaryProps {
  children: ReactNode;
  /** Optional custom fallback — receives the caught error + a reset callback. */
  fallback?: (args: { error: Error; reset: () => void }) => ReactNode;
}

/**
 * Error boundary that pairs with react-query's `QueryErrorResetBoundary`
 * so clicking "Try again" both clears the boundary state AND re-triggers
 * affected queries. Wrap around any view that consumes `useQuery` without
 * manual error handling — typically a route's `<Outlet>` or a page body.
 */
export default function QueryErrorBoundary({ children, fallback }: QueryErrorBoundaryProps) {
  return (
    <QueryErrorResetBoundary>
      {({ reset }) => (
        <InnerBoundary onReset={reset} fallback={fallback}>
          {children}
        </InnerBoundary>
      )}
    </QueryErrorResetBoundary>
  );
}
