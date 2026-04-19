import { useEffect, useRef, useState } from 'react';
import { Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SearchInputProps {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  /** Debounce delay in ms before calling onChange. 0 to disable. */
  debounceMs?: number;
  className?: string;
  ariaLabel?: string;
}

/**
 * Controlled text input with a magnifying glass affordance and clear button.
 * Debounces `onChange` to keep typing responsive on large datasets.
 */
export default function SearchInput({
  value,
  onChange,
  placeholder = 'Search…',
  debounceMs = 200,
  className,
  ariaLabel,
}: SearchInputProps) {
  const [local, setLocal] = useState(value);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Keep local in sync when parent resets (e.g. Clear filters)
  useEffect(() => {
    setLocal(value);
  }, [value]);

  useEffect(() => {
    if (debounceMs <= 0) {
      onChange(local);
      return;
    }
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => onChange(local), debounceMs);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [local, debounceMs]);

  return (
    <div className={cn('relative min-w-[220px]', className)}>
      <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <input
        type="text"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        placeholder={placeholder}
        aria-label={ariaLabel || placeholder}
        className="w-full rounded-md border border-input bg-background py-1.5 pl-8 pr-8 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      />
      {local && (
        <button
          type="button"
          onClick={() => setLocal('')}
          aria-label="Clear search"
          className="absolute right-2 top-1/2 flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded text-muted-foreground hover:text-foreground"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}
