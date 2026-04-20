import { describe, expect, it } from 'vitest';
import { getApiErrorMessage } from './apiError';

describe('getApiErrorMessage', () => {
  it('returns a string detail as-is', () => {
    const err = { response: { data: { detail: 'Not enough stock on hand.' } } };
    expect(getApiErrorMessage(err)).toBe('Not enough stock on hand.');
  });

  it('formats a Pydantic validation array', () => {
    const err = {
      response: {
        data: {
          detail: [
            {
              type: 'string_type',
              loc: ['body', 'settings', 'ai_openai_api_key', 'value'],
              msg: 'Input should be a valid string',
              input: null,
            },
          ],
        },
      },
    };
    expect(getApiErrorMessage(err)).toBe(
      'settings.ai_openai_api_key.value: Input should be a valid string',
    );
  });

  it('joins multiple validation errors with a bullet', () => {
    const err = {
      response: {
        data: {
          detail: [
            { loc: ['body', 'name'], msg: 'Field required' },
            { loc: ['body', 'email'], msg: 'value is not a valid email address' },
          ],
        },
      },
    };
    expect(getApiErrorMessage(err)).toBe(
      'name: Field required · email: value is not a valid email address',
    );
  });

  it('falls back to the axios message for network errors', () => {
    const err = { message: 'Network Error' };
    expect(getApiErrorMessage(err, 'Failed')).toBe('Network Error');
  });

  it('uses the fallback when no detail is available', () => {
    expect(getApiErrorMessage({}, 'Failed to save')).toBe('Failed to save');
    expect(getApiErrorMessage(null, 'Failed to save')).toBe('Failed to save');
  });

  it('treats an empty string detail as missing', () => {
    const err = { response: { data: { detail: '   ' } } };
    expect(getApiErrorMessage(err, 'Default')).toBe('Default');
  });
});
