import { type SelectHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/utils';

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'onChange' | 'size'> {
  value: string;
  onChange: (next: string) => void;
  options: SelectOption[];
  placeholder?: string;
  size?: 'sm' | 'md';
}

/**
 * Thin wrapper over native <select>. Uses business-style borders and tabular
 * sizing. Prefer for toolbar filters; the shared Radix Select primitive will
 * land in phase 4 and supplant this for form contexts.
 */
const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { value, onChange, options, placeholder, size = 'md', className, ...rest },
  ref,
) {
  return (
    <select
      ref={ref}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        'rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring',
        size === 'sm' ? 'px-2 py-1' : 'px-3 py-1.5',
        className,
      )}
      {...rest}
    >
      {placeholder ? <option value="">{placeholder}</option> : null}
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
});

export default Select;
