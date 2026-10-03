import { readdir, readFile } from 'node:fs/promises'
import { extname, join } from 'node:path'

const roots = ['src']
const violations = []

async function walk(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) await walk(path)
    else if (['.ts', '.tsx'].includes(extname(path))) {
      const text = await readFile(path, 'utf8')
      const rules = [
        [/\beval\s*\(/g, 'eval is forbidden'],
        [/new\s+Function\s*\(/g, 'dynamic Function is forbidden'],
        [/console\.log\s*\(/g, 'console.log is forbidden; use structured UI/logging'],
        [/\bany\s*\[\s*\]/g, 'unbounded any[] is forbidden'],
      ]
      for (const [pattern, message] of rules) {
        if (pattern.test(text)) violations.push(`${path}: ${message}`)
      }
    }
  }
}

for (const root of roots) await walk(root)
if (violations.length) {
  console.error(violations.join('\n'))
  process.exit(1)
}
console.log('Agent5 frontend static lint checks passed.')
