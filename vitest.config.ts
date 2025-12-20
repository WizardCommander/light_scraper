import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    globals: true,
    include: ['electron/**/*.spec.ts', 'electron/**/*.spec.tsx']
  }
})
