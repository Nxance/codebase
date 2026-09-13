# Nxance development

Read README.md before changing the app. Preserve the existing Site project ID in .openai/hosting.json. A GitHub push is not a production deployment.

Use the current npm lockfile and Node.js 24 for laptop work. Fresh clones use the portable execution profile; do not commit machine-specific .sites-runtime state.

## Important boundaries

- Identify users server-side from the platform-provided ChatGPT headers. Never accept a client-supplied owner ID or role as authority.
- The local sign-in simulator is only for loopback development. Do not extend it to production.
- Preserve user-scoped database access, active/suspended checks, protected owner permissions, CSRF checks, optimistic revisions and transactional admin audit writes.
- Existing production migrations 0000 and 0001 are already applied. Append migrations; do not rewrite them.
- Never commit .env, .dev.vars, credentials, live user data, local database files, node_modules or compiled dist output.
- Keep calculations deterministic. Do not invent live prices, portfolio scores or AI capabilities.

For changes to authentication, permissions or persistence, run `node tests/access.test.mjs`, TypeScript checking and the application build. For other changes, use checks relevant to the change.

The active hosted product has Health Check, Goal Planner, saved user workspaces, account pages and an admin panel. Production sharing remains controlled separately through ChatGPT Sites.
