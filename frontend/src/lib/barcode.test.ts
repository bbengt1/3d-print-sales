import { describe, expect, it } from 'vitest';
import { canRenderUpcA } from './barcode';

describe('canRenderUpcA', () => {
  it('accepts exactly 12 numeric digits', () => {
    expect(canRenderUpcA('040000000013')).toBe(true);
    expect(canRenderUpcA(' 040000000013 ')).toBe(true);
  });

  it('rejects missing, short, long, or non-numeric UPC values', () => {
    expect(canRenderUpcA(null)).toBe(false);
    expect(canRenderUpcA('')).toBe(false);
    expect(canRenderUpcA('123')).toBe(false);
    expect(canRenderUpcA('1234567890123')).toBe(false);
    expect(canRenderUpcA('PRD-PLA-0001')).toBe(false);
  });
});
