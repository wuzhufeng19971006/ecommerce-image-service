import { describe, expect, it } from 'vitest'
import {
  STATUS_LABELS,
  WORKFLOW_LABELS,
  formatBytes,
  formatDuration,
  formatElapsed,
} from './format'

describe('format helpers', () => {
  it('maps workflow and status labels', () => {
    expect(WORKFLOW_LABELS.try_on).toBe('模特试穿')
    expect(STATUS_LABELS.succeeded).toBe('已完成')
  })

  it('formats durations', () => {
    expect(formatDuration(800)).toBe('800 ms')
    expect(formatDuration(12_000)).toBe('12 秒')
    expect(formatDuration(65_000)).toBe('1 分 5 秒')
  })

  it('formats elapsed time with two digits', () => {
    expect(formatElapsed(0)).toBe('00:00')
    expect(formatElapsed(65)).toBe('01:05')
  })

  it('formats byte sizes', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(2048)).toBe('2 KB')
    expect(formatBytes(2 * 1024 * 1024)).toBe('2.0 MB')
  })
})
