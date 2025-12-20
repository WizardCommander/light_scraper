/**
 * Utilities for cleaning and formatting log messages
 */

/**
 * Removes ANSI color codes and formatting from log message
 */
export function cleanLogMessage(log: string): string {
  return log
    .replace(/\x1b\[[0-9;]*m/g, '') // Remove ANSI color codes
    .replace(/^ERROR:\s+/g, '') // Remove ERROR: prefix first
    .replace(/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\s+\|\s+/g, '') // Remove timestamp prefix
    .replace(/\s+\|\s+INFO\s+\|\s+/g, ' | ') // Clean up log level separators
    .replace(/\s+\|\s+SUCCESS\s+\|\s+/g, ' | ')
    .replace(/\s+\|\s+ERROR\s+\|\s+/g, ' | ')
    .trim()
}

/**
 * Determines the appropriate color for a log message based on its content
 */
export function getLogColor(log: string): string {
  const isSuccess = log.includes('SUCCESS') || log.includes('Successfully')
  const isError = log.includes('ERROR') || log.includes('Failed') || log.includes('Error:')

  if (isSuccess) return '#51cf66' // Green
  if (isError) return '#ff6b6b'   // Red
  return '#ffffff'                 // White
}

/**
 * Removes consecutive duplicate items from an array
 */
export function removeDuplicates<T>(arr: T[]): T[] {
  return arr.filter((item, i, array) => i === 0 || item !== array[i - 1])
}
