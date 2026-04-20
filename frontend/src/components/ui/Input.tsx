import { forwardRef, useId, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Show a destructive outline when the field has a validation error. */
  invalid?: boolean;
  /**
   * Inline validation message. When set, the input renders with destructive
   * styling, `aria-invalid="true"`, and a below-input error paragraph that
   * is wired to the input via `aria-describedby`. Overrides `invalid`.
   */
  error?: string | null | false;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, invalid = false, error, id: providedId, 'aria-describedby': describedBy, ...props },
  ref,
) {
  const generatedId = useId();
  const id = providedId ?? generatedId;
  const errorId = error ? `${id}-error` : undefined;
  const isInvalid = Boolean(error) || invalid;

  const inputEl = (
    <input
      ref={ref}
      id={id}
      aria-invalid={isInvalid || undefined}
      aria-describedby={cn(describedBy, errorId) || undefined}
      className={cn(
        'flex h-9 w-full rounded-md border bg-background px-3 py-1 text-sm transition-colors placeholder:text-muted-foreground file:border-0 file:bg-transparent file:text-sm file:font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
        isInvalid ? 'border-destructive focus-visible:ring-destructive' : 'border-input',
        className,
      )}
      {...props}
    />
  );

  if (!error) return inputEl;

  return (
    <div className="space-y-1">
      {inputEl}
      <p id={errorId} className="text-xs text-destructive">
        {error}
      </p>
    </div>
  );
});
