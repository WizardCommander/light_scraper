import { describe, expect, test } from 'vitest'
import { cleanLogMessage, getLogColor, removeDuplicates } from './logUtils'

describe('cleanLogMessage', () => {
  test('removes ANSI color codes', () => {
    const input = '\x1b[31mERROR\x1b[0m message'
    expect(cleanLogMessage(input)).toBe('ERROR message')
  })

  test('removes ERROR prefix', () => {
    const input = 'ERROR: something went wrong'
    expect(cleanLogMessage(input)).toBe('something went wrong')
  })

  test('removes timestamp prefix', () => {
    const input = '2025-12-17 02:27:20.655 | INFO | Loading products'
    expect(cleanLogMessage(input)).toBe('INFO | Loading products')
  })

  test('removes INFO log level separator', () => {
    const input = 'src.module | INFO | message'
    expect(cleanLogMessage(input)).toBe('src.module | message')
  })

  test('removes SUCCESS log level separator', () => {
    const input = 'src.module | SUCCESS | completed'
    expect(cleanLogMessage(input)).toBe('src.module | completed')
  })

  test('removes ERROR log level separator', () => {
    const input = 'src.module | ERROR | failed'
    expect(cleanLogMessage(input)).toBe('src.module | failed')
  })

  test('handles complex log with multiple patterns', () => {
    const input = 'ERROR: 2025-12-17 02:27:20.655 | INFO | src.module:function - message here'
    expect(cleanLogMessage(input)).toBe('src.module:function - message here')
  })

  test('handles empty string', () => {
    expect(cleanLogMessage('')).toBe('')
  })

  test('handles whitespace-only string', () => {
    expect(cleanLogMessage('   \n\t  ')).toBe('')
  })

  test('trims leading and trailing whitespace', () => {
    const input = '  message with spaces  '
    expect(cleanLogMessage(input)).toBe('message with spaces')
  })

  test('preserves message content with special characters', () => {
    const input = 'File: output\\17371 4100\\products.csv'
    expect(cleanLogMessage(input)).toBe('File: output\\17371 4100\\products.csv')
  })
})

describe('getLogColor', () => {
  test('returns green for SUCCESS', () => {
    expect(getLogColor('Operation SUCCESS')).toBe('#51cf66')
  })

  test('returns green for Successfully', () => {
    expect(getLogColor('Successfully completed')).toBe('#51cf66')
  })

  test('returns red for ERROR', () => {
    expect(getLogColor('ERROR occurred')).toBe('#ff6b6b')
  })

  test('returns red for Failed', () => {
    expect(getLogColor('Operation Failed')).toBe('#ff6b6b')
  })

  test('returns red for Error:', () => {
    expect(getLogColor('Error: something wrong')).toBe('#ff6b6b')
  })

  test('returns white for neutral message', () => {
    expect(getLogColor('Loading products')).toBe('#ffffff')
  })

  test('returns white for empty string', () => {
    expect(getLogColor('')).toBe('#ffffff')
  })

  test('prioritizes success over error if both present', () => {
    // SUCCESS check comes first in implementation
    expect(getLogColor('Successfully handled ERROR')).toBe('#51cf66')
  })
})

describe('removeDuplicates', () => {
  test('removes consecutive duplicates from string array', () => {
    const input = ['a', 'a', 'b', 'b', 'c']
    expect(removeDuplicates(input)).toEqual(['a', 'b', 'c'])
  })

  test('keeps non-consecutive duplicates', () => {
    const input = ['a', 'b', 'a', 'c']
    expect(removeDuplicates(input)).toEqual(['a', 'b', 'a', 'c'])
  })

  test('handles empty array', () => {
    expect(removeDuplicates([])).toEqual([])
  })

  test('handles single element array', () => {
    expect(removeDuplicates(['a'])).toEqual(['a'])
  })

  test('handles array with all same elements', () => {
    const input = ['a', 'a', 'a', 'a']
    expect(removeDuplicates(input)).toEqual(['a'])
  })

  test('handles array with no duplicates', () => {
    const input = ['a', 'b', 'c', 'd']
    expect(removeDuplicates(input)).toEqual(['a', 'b', 'c', 'd'])
  })

  test('works with numbers', () => {
    const input = [1, 1, 2, 3, 3, 3, 4]
    expect(removeDuplicates(input)).toEqual([1, 2, 3, 4])
  })

  test('works with objects (reference equality)', () => {
    const obj1 = { id: 1 }
    const obj2 = { id: 2 }
    const input = [obj1, obj1, obj2, obj2]
    expect(removeDuplicates(input)).toEqual([obj1, obj2])
  })
})
