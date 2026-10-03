import 'fake-indexeddb/auto'

// React 19 uses this flag to suppress false act() environment warnings in Vitest.
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
