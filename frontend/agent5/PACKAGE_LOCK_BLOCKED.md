# Frontend lockfile status

The source archive does not fabricate a `package-lock.json` because the audit container could not complete public npm registry access and timed out.

All top-level frontend versions in `package.json` are exact. On the first connected Windows setup, `setup_agent5.ps1`:

1. generates `package-lock.json` using the public npm registry;
2. rejects private audit-sandbox registry URLs;
3. runs `npm ci` with retries;
4. runs TypeScript validation, static lint, Vitest, and the Vite production build.

After a successful first setup, preserve the generated `frontend/package-lock.json` in source control for repeatable organizational deployments.
