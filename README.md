# Nxance

Nxance is a basic investment workspace with portfolio allocation and concentration analysis, a goal/SIP calculator, ChatGPT sign-in, saved workspaces, and an owner/admin panel.

This repository contains the complete application source, API routes, database schema and migrations, UI components, lockfile, and access-control tests. Production database contents, credentials, dependency folders, and build outputs are not part of the repository.

## Laptop setup

Use Node.js 24 LTS and npm. A fresh clone automatically uses the portable execution profile for Windows, macOS, or Linux.

```sh
npm ci
npm run build
```

Initialize the **local** database by applying these existing migrations once, in order:

```sh
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --file drizzle/0000_thick_morlun.sql
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --file drizzle/0001_omniscient_captain_midlands.sql
npm run dev
```

Open the loopback URL printed by the development server, normally http://localhost:5173. Do not replay those initial migrations against an already initialized local database.

## Local sign-in and admin testing

The existing portable development helper provides synthetic ChatGPT sign-in on loopback only. Visit `/signin-with-chatgpt?return_to=/workspace` to sign in as `local_seedy` / `seedy@sites.test`. This mock is not included in production builds.

For a fresh local test database, the following **local-only** command assigns that synthetic account as owner:

```sh
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --command "INSERT INTO app_settings (key,value) VALUES ('owner_user_id','local_seedy') ON CONFLICT(key) DO NOTHING"
```

Then visit `/admin`. This preserves an existing local owner assignment. Never run local test identity setup against production.

Hosted sign-in is provided by ChatGPT Sites. Hosted ownership bootstraps from the secret runtime value `NXANCE_OWNER_EMAIL`, then binds to the stable signed-in user ID. Its production value stays in Sites settings and is not copied into this repository.

## Validation

```sh
node tests/access.test.mjs
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run build
```

The tests use an isolated in-memory SQLite database. They cover owner binding, member isolation, suspension, CSRF, administrator permissions, revision conflicts, resets and audit records. They do not test a live ChatGPT OAuth browser session.

## Code map

| Path | Responsibility |
| --- | --- |
| `app/page.tsx` | Welcome and sign-in page |
| `app/workspace/` | Protected portfolio and goal workspace |
| `public/app.js`, `public/math.mjs`, `public/style.css` | Calculator UI, deterministic maths and styles |
| `app/account/` | Profile and saved workspace summary |
| `app/admin/` | User directory, workspace editing and database overview |
| `app/api/workspace/` | User-scoped load/save API |
| `app/api/admin/` | Protected admin reads and mutations |
| `lib/app-user.ts` | User registration, owner binding, roles and status |
| `db/`, `drizzle/` | Database helpers, schema and migrations |
| `tests/access.test.mjs` | Access-control and database regression tests |
