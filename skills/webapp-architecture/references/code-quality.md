# Code quality

The standard: a careful senior reviewer reads the change and has nothing to flag. Correct on the unhappy paths, typed end to end, no dead code, nothing clever where plain code would do, and every unusual choice explained in a short comment.

## TypeScript

`tsconfig.json`, on top of the React Router template's settings:

```jsonc
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,     // arr[i] and record[key] may be undefined
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "exactOptionalPropertyTypes": true,   // `prop?: string` doesn't accept explicit undefined
    "verbatimModuleSyntax": true,         // type-only imports stay type-only
    "isolatedModules": true
  }
}
```

`noUncheckedIndexedAccess` catches the most common runtime crash in React apps, reading a property of an array element or map entry that isn't there. `exactOptionalPropertyTypes` can be noisy with some libraries. If it costs more than it catches in a given repo, drop it and note why.

Rules:
- **No `any`.** Use `unknown` and narrow it with a schema or type guard. An `any` spreads: every value derived from it is unchecked too.
- **No `@ts-ignore`.** Use `@ts-expect-error` with a reason, only for a known library typing bug. It fails once the bug is fixed, so it can't outlive its reason.
- **No non-null `!`** unless the reason is on the same line. Usually there's a better shape: narrow with an `if`, or make the type say the value exists.
- **Discriminated unions for states:** `{ status: "idle" } | { status: "error"; message: string } | …` instead of several booleans that can contradict each other.
- **Derive types from the source.** `Route.ComponentProps`, `z.infer<typeof Schema>`, the ORM's generated types. Hand-written duplicates drift.
- **Exhaustive switches** end with `default: return assertNever(value)`, so adding a union member is a compile error everywhere it isn't handled.

## Lint and format

- ESLint with `typescript-eslint` (type-aware rules), `eslint-plugin-react-hooks`, and `eslint-plugin-jsx-a11y`. The hooks plugin catches stale closures and conditional hooks, and the a11y plugin catches missing labels and non-interactive click handlers.
- Prettier, or whatever formatter the repo uses, run in CI with `--check`. Formatting is never a review topic.
- Worth turning on: `@typescript-eslint/no-floating-promises` (an unawaited promise swallows its error), `no-misused-promises`, `switch-exhaustiveness-check`, `consistent-type-imports`.
- An `eslint-disable` comment always names the rule and gives the reason.

## Structure

```
app/
  root.tsx
  routes.ts
  routes/                 # route modules, thin
  components/ui/          # shared primitives, no domain knowledge
  features/<domain>/      # components, hooks, server logic for one domain
    ProjectCard.tsx
    ProjectCard.module.css
    projects.server.ts    # data access and business rules
    projects.ts           # pure domain logic shared by client and server
  lib/                    # pure utilities with no framework imports
  styles/global.css
```

- **Thin routes.** A route module parses input, calls `features/*` functions, and composes components. Logic in a route file can only be tested through the route and can't be reused by another route.
- **Imports go one way:** `routes → features → components/ui → lib`. A primitive in `components/ui` never imports from a feature, and features don't import each other's internals. When two features need the same thing, move it down a level.
- **Server and client code apart.** Database clients, secrets, sessions and third-party API keys live only in `*.server.ts` files. The build refuses to bundle them for the browser, which makes leaking a secret a build error instead of an incident.
- **Colocate.** A component's styles, its skeleton, its hooks and its tests sit next to it. Folders by type (`hooks/`, `styles/`, `utils/` at the top level) scatter one feature across the tree.
- **Name files after what they export.** `ProjectCard.tsx` exports `ProjectCard`. Use named exports, except where React Router requires a default (the route component).

## Reusing components

- **Search first.** Before writing a component, look in `components/ui/` and the feature folder. Duplicated buttons, inputs and dialogs are the most common source of inconsistent behavior: one handles focus properly, the other doesn't.
- **Extract on the second real use**, when the two uses have the same purpose and will change together. Don't extract on looks alone. Two things that happen to look alike today will diverge, and the shared component fills up with boolean props for each caller.
- **Primitives in `components/ui/`:** Button, IconButton, Link (wrapping the router `Link` with app defaults like `prefetch="intent"`), Field, Input, Select, Checkbox, Dialog, Menu, Tabs, Tooltip, Skeleton, EmptyState, ErrorState, Stack/Cluster layout helpers. They're accessible by default (labels, focus management, keyboard support), so features get that for free.
- **Composition over configuration.** Prefer `children` and slot props (`<Card header={…} footer={…}>`) to a growing list of flags. A component with more than about five boolean props is several components.
- **Shared hooks** for repeated behavior: `useDebouncedValue`, `useMediaQuery`, `useCopyToClipboard`. One hook, one job.

## Clean code

- **Small units.** A component or function should do one thing you can name. If you can't name it without "and", split it.
- **Name things for what they mean in the domain**, not for their type or shape: `overdueInvoices`, not `filteredList`.
- **Early returns** for guard cases instead of nested `if`s.
- **No dead code.** No commented-out blocks, no unused exports, no `// TODO` without an issue link. Version control remembers deleted code.
- **Comments explain why,** not what: a business rule, a browser workaround, a deliberate trade-off. If a comment explains what the code does, rewrite the code until it doesn't need one.
- **No premature abstraction.** No generic "service" layers, factories or config-driven rendering for something used once. Abstraction costs indirection, so it has to pay for itself.
- **Derived state is computed, not stored.** If a value can be computed from props or loader data, compute it during render. Copying it into state means it goes stale.
- **`useEffect` is for syncing with something outside React** (a subscription, a DOM API, a timer). Not for data fetching (use a loader), not for deriving state, and not for responding to events (do it in the handler).

## Errors

- Expected failures are values or thrown responses: `throw data(null, { status: 404 })`, an action returning `{ errors }` with status 400, a data function returning `{ ok: false, reason }`.
- Unexpected failures propagate to an `ErrorBoundary` and get logged with enough context to reproduce them (route, user id, request id). Never with secrets or personal data beyond what's needed.
- No empty `catch`. A `catch` either handles the error (retry, fallback, user message) or adds context and rethrows.
- Every async call is awaited, returned, or explicitly marked fire-and-forget with error handling attached. The lint rule above enforces it.

## Security basics

- **Sessions** in `httpOnly`, `secure`, `sameSite=lax` cookies, signed with a secret from env. No tokens in `localStorage`, where any XSS can read them.
- **Authorization at the data layer.** Every query for user-owned data is scoped by the user or their organization (`where: { id, orgId: user.orgId }`). Route-level checks alone miss the action that someone forgets to guard.
- **Validate every input** with a schema, including `params`. Never trust a hidden form field for anything that matters (prices, roles, owner ids).
- **Env is parsed at startup** with a schema in `env.server.ts`, so a missing secret fails the deploy instead of the first request that needs it.
- **Security headers** from `entry.server.tsx` or the server: `Content-Security-Policy` (with nonces for inline scripts), `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, and `frame-ancestors` in the CSP.
- **No `dangerouslySetInnerHTML`** with content that came from users unless it went through a sanitizer.
- **Open redirects:** a `redirectTo` parameter only accepts same-origin paths.
- **Dependencies:** keep them few and current, run `npm audit` in CI, and commit the lockfile.

## Performance

- No waterfalls: start independent queries together, and let nested loaders run in parallel instead of having children wait for parent data.
- Check bundle size when adding a dependency. A date or chart library can outweigh the rest of the app. Prefer native APIs (`Intl.DateTimeFormat`, `Intl.NumberFormat`, `structuredClone`).
- Images get explicit `width` and `height` (or an `aspect-ratio`), so they don't shift the layout when they load, plus `loading="lazy"` below the fold.
- Long lists (hundreds of rows or more) are paginated or virtualized.
- Use `memo`, `useMemo` and `useCallback` when a measurement or a referential-equality requirement calls for them, not by default. Unneeded memoization adds noise and rarely helps. If the project uses the React Compiler, leave memoization to it.

## Review checklist

Before calling a change done:
- [ ] Typecheck, lint, tests and build pass. E2E passes if the change touches a critical flow.
- [ ] React Router is on the latest version, and all `@react-router/*` packages match it.
- [ ] New routes server-render. Slow data on authenticated pages is streamed, with a skeleton that matches the layout.
- [ ] No data fetching in effects.
- [ ] Inputs are validated with a schema. Authorization is checked at the data layer.
- [ ] Each new component has its own `.module.css`. Nothing new in the global stylesheet except tokens or base styles.
- [ ] Existing components were reused where they fit. Nothing was duplicated.
- [ ] No `any`, `@ts-ignore`, unexplained `!`, empty `catch`, or dead code.
- [ ] Error, empty and loading states exist for every new panel.
- [ ] Tests cover the new behavior and would fail if it broke. No filler tests.
- [ ] `python3 scripts/audit_webapp.py` reports nothing new.
