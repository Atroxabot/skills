---
name: webapp-architecture
description: Sets the structure, tech stack and code standards for React web apps built on the latest React Router in framework mode. Covers server-side rendering by default, streaming slow data into Suspense boundaries with layout-matched skeletons on authenticated panels, auth via middleware, prefetching and optimistic UI so navigation feels instant, a small global stylesheet with CSS Modules for every component and page, reusable components, strict TypeScript, and tests that catch real bugs instead of padding coverage. Includes an audit script. Use when the user asks to start, scaffold, structure, build, refactor, review or upgrade a web app, dashboard, admin panel, SaaS app or React project, add a route, page, loader, panel or feature, upgrade React Router or migrate from react-router-dom or Remix, set up SSR, streaming, lazy loading or skeletons, organize CSS or CSS modules, or write or clean up tests for a React app. Not about visual design.
---

# Web app architecture

This skill covers how a web app is built: its stack, structure, data flow, code quality and tests. It does not cover how the app looks. Colors, typography and layout taste belong to the design system or the designer. Skeletons and loading states come up here because they are part of the data flow, not because of how they look.

The goal is an app that feels fast and seamless. Pages arrive as rendered HTML, navigation never blanks the screen, slow data streams into place without moving the layout, and the user never stares at a spinner covering the whole page. The rules below exist to produce that experience and to keep the codebase easy to change as it grows.

## The stack

| Concern | Choice | Why |
|---|---|---|
| Router and framework | **The latest stable React Router**, framework mode (Vite plugin, `app/routes.ts`, route modules with typegen) | Framework mode gives SSR, streaming, code splitting, middleware and typed loaders in one tool. Staying on the latest major means getting fixes and performance work, and avoiding a big painful upgrade later. |
| Language | TypeScript, `strict` plus the extra flags in [references/code-quality.md](references/code-quality.md) | Most bugs that types can catch are cheaper to catch at compile time than in review or production. |
| Styling | One small global stylesheet, a `.module.css` file for each component and page | Scoped class names can't collide or leak, unused styles get deleted along with their component, and the global file stays small enough to read in one sitting. |
| Validation | The schema library the repo already uses; Zod if there is none | Every input from outside the process (form data, params, search params, env, third-party responses) is untrusted until parsed. |
| Unit and integration tests | Vitest, React Testing Library, `createRoutesStub` from `react-router` | Vitest uses the same Vite config as the app, and Testing Library queries the way a user sees the page. |
| End-to-end tests | Playwright | Real browser, real SSR and hydration, and tracing when a test fails in CI. |

Don't add a second tool for something the stack already does: no separate data-fetching library on top of loaders, no CSS-in-JS runtime, no utility-class framework next to CSS Modules, no client-side router other than React Router. Each extra layer adds bundle weight and a second way to do the same thing, and two ways to do the same thing turn into inconsistent code.

### Always the latest React Router

Before starting or reviewing an app, check the current version instead of trusting memory, because React Router ships often and majors change APIs:

```bash
npm view react-router version            # latest stable
npm view react-router dist-tags          # latest, plus older lines
```

Then:
- **New app:** `npx create-react-router@latest`. Pin the resolved version in `package.json` with a caret.
- **Existing app behind the latest major:** upgrade as part of the work, or, if the upgrade is large, say so and propose it as its own change before building on the old version. Follow the official upgrade guide one major at a time. Enable the previous major's future flags first, since each flag is a small, testable step and the major bump then becomes mostly a version change.
- Keep every `@react-router/*` package on the same version as `react-router`. Mixed versions cause confusing build and typegen errors.
- Use only stable APIs in production code. Anything prefixed `unstable_` can change in a minor release; use it only when the user agrees to the risk, and leave a comment saying why.

As of React Router 8 there is no `react-router-dom`: imports come from `react-router`, and DOM-specific ones (`RouterProvider`, `HydratedRouter`) from `react-router/dom`. Middleware is always on. [references/react-router.md](references/react-router.md) has the current patterns, the v7-to-v8 changes and the migration steps from v6, `react-router-dom` and Remix. Check the version you found against it. If a newer major has come out since it was written, read that major's changelog before writing code.

## Rendering strategy: SSR wherever it makes sense

Server-render by default (`ssr: true` in `react-router.config.ts`). The first paint is real content, search engines and link previews see it, and the app works before the JavaScript arrives. Decide per route:

| Route | Strategy |
|---|---|
| Public, the same for every visitor (landing, docs, pricing, blog) | Prerender at build time with `prerender` in the config, or SSR with cache headers. |
| Public but dynamic (search results, a product page) | SSR with a `loader`, and `Cache-Control` headers where the data allows. |
| Behind authentication (dashboard, settings, admin) | SSR the shell and the cheap critical data. **Stream** everything slow (see below). |
| Needs browser-only APIs (canvas editor, map, WebGL, local files) | SSR the surrounding page. Load the browser-only part with `React.lazy` inside `<Suspense>`, or use a `clientLoader` with a `HydrateFallback`. Never switch the whole app to `ssr: false` for one widget. |

Fetching data in `useEffect` is not one of the options. It waits for hydration before it starts, creates request waterfalls, and gives you a spinner the server could have avoided. Data belongs in loaders (server) and `clientLoader`s (browser).

## Authenticated panels: stream slow data into skeletons

An authenticated page has two kinds of data: what the page can't render without (the user, the permissions, the page title, the record being edited), and what can arrive a moment later (charts, activity feeds, counts, recommendations, anything from a slow query or third-party API). The page should never wait for the second kind.

1. **Authenticate in middleware**, not in each loader. A `middleware` on the authenticated layout route reads the session, `throw redirect("/login")` when there is none, and puts the user into a typed context with `context.set(userContext, user)`. Child loaders read it with `context.get(userContext)`. Then no route behind the layout can forget the check.
2. **Await the critical data, return the slow data as promises.** In the loader, start every query at once and `await` only the ones the page needs before it can render. Return the rest unawaited: `return { project: await project, activity, stats }`. React Router streams them to the browser as they settle.
3. **Render each streamed value inside its own `<Suspense>` boundary** with `<Await>` or `React.use`, and a skeleton as the fallback. One boundary per independent panel, so a slow chart doesn't hold back a fast list.
4. **Lazy-load heavy code the same way.** Route modules are already split per route. Inside a route, load big client-only components (rich text editors, chart libraries, PDF viewers) with `React.lazy` so they don't weigh down the first load of pages that never open them.

### Skeleton rules

A skeleton should make the page feel like it's already there, not draw attention to loading.

- **Match the real layout.** Same box sizes, same number of rows where the count is known, same grid. When the data arrives, nothing moves. Layout shift is the most visible sign of a janky page, and it counts against Cumulative Layout Shift.
- **One shared primitive, composed per panel.** A single `Skeleton` component in `components/ui/` (block, line, circle) with its own `.module.css`. Each panel has a `<PanelNameSkeleton>` next to it, built from that primitive. Panels and their skeletons change together, so they live together.
- **Don't flash.** Fade the skeleton in after about 150 ms with a CSS `animation-delay`, so a fast response goes straight from nothing to content. A skeleton that appears for 50 ms reads as flicker.
- **Respect reduced motion.** Turn off the shimmer under `prefers-reduced-motion: reduce`.
- **Accessible.** Mark the loading region with `aria-busy="true"` and hide the skeleton shapes from assistive tech with `aria-hidden`. Screen reader users need "loading", not a dozen empty boxes.
- **Errors stay inside the panel.** Give `<Await>` an `errorElement` (or wrap `React.use` in an error boundary) so a failed chart shows a small retry message inside its panel instead of taking down the page.
- **Skip the skeleton when there's nothing to wait for.** Data that is always fast and critical is awaited in the loader and rendered directly.

When the same route reloads with new params (`/projects/1` to `/projects/2`), React keeps showing the old content during the transition. If showing the previous project's data would mislead, give the `<Suspense>` boundary `key={params.id}` so the skeleton shows instead.

## Navigation that feels instant

- `<Link prefetch="intent">` on navigation links, so loaders and code start loading on hover or focus. Use `prefetch="viewport"` for small lists of likely next pages. Don't prefetch everything: it wastes bandwidth and server time on pages nobody opens.
- Show pending state for the part that is changing, using `useNavigation()` or `fetcher.state`: a thin progress bar at the top, a dimmed panel, a button that says "Saving…". Never put up a blocking overlay.
- Use optimistic UI for mutations that almost always succeed (toggles, renames, reordering, likes): render `fetcher.formData` as if the change had already happened, and let revalidation correct it if it didn't.
- Use `<Form>` and `useFetcher` for mutations, not hand-written `fetch` calls. They revalidate the loaders on the page automatically, so the page never shows stale data after a write.
- Add `shouldRevalidate` to expensive loaders whose data a given mutation can't affect.
- Keep `<ScrollRestoration />` in the root, and use `viewTransition` on links where a transition helps the user keep their place.

## Styling structure

The global stylesheet holds only what has to be global:
- the reset or normalize
- design tokens as CSS custom properties (colors, spacing, radii, font stacks, z-index scale, durations)
- base element styles (`html`, `body`, headings, links, focus ring)
- `@font-face` rules and a few accessibility utilities (`.visually-hidden`)

Everything else goes in a `.module.css` file next to the component or route that uses it. Keep the global file small (under about 300 lines in total across all global CSS files). When it grows, something component-shaped has moved in; move it out. Components use the tokens instead of hard-coded values, so a theme change touches one file. Naming, variants, composition and the few cases where `:global` is allowed are in [references/styling.md](references/styling.md).

## Code structure and quality

The bar is code that a careful senior reviewer would approve without comments: correct on the unhappy paths, typed end to end, easy to read, and with nothing in it that doesn't need to be there.

Folder layout (adapt the names to the repo if it already has a working convention):

```
app/
  root.tsx               # document shell, global CSS import, error boundary
  routes.ts              # route config
  routes/                # route modules: thin, wire data to features
    _app/                # authenticated layout with the auth middleware
  components/ui/         # shared primitives: Button, Field, Skeleton, Dialog…
  features/<domain>/     # domain components, hooks, and *.server.ts logic
  lib/                   # pure, framework-free utilities
  styles/global.css      # the small global stylesheet
```

Core rules (the full list with reasons is in [references/code-quality.md](references/code-quality.md)):
- **Thin routes.** A route module parses input, calls feature functions and passes data to components. Business logic in route files can't be reused or tested in isolation.
- **Reuse before you write.** Search `components/ui/` and the feature folder before creating a component. Extract a shared component the second time the same UI shows up with the same purpose. Don't extract things that only look alike, because they will change for different reasons and the shared version fills up with flags.
- **Server code stays on the server.** Database clients, secrets and session handling live in `*.server.ts` files, which the build refuses to bundle for the browser.
- **Parse at the boundary.** Validate params, search params, form data, cookies and env with a schema at the point they enter, and work with typed values after that.
- **Errors are handled, not hidden.** Each route that can fail has an `ErrorBoundary`. No empty `catch` blocks. Expected failures (not found, forbidden, validation) are thrown as `data()` responses with the right status, and unexpected ones go to logging.
- **No `any`, no `@ts-ignore`, no unexplained `!`.** Each one turns off the checks this stack relies on. When one is really needed, add a comment with the reason.
- **Small, single-purpose units.** A component that needs a scroll to read, or a function with several flags, is doing several jobs. Split it.
- **CI gates:** typecheck (including `react-router typegen`), lint, unit tests, build, and E2E on the critical flows. A change isn't done until all of them pass.

## Tests that earn their place

Each test should be one that would fail if a real bug shipped. A test that can't fail, or only fails when markup is reshuffled, costs maintenance and protects nothing.

Write tests for:
- **Loaders and actions:** auth denial, permission checks, validation errors, the redirect after a mutation, the not-found path.
- **Business logic** in `features/*/` and `lib/`: calculations, state machines, parsing, formatting with edge cases.
- **Components with real behavior:** a form that validates and submits, a filter that changes results, keyboard interaction in a custom widget, rendered through `createRoutesStub` when they use router hooks.
- **Critical user flows end to end** with Playwright: sign in, the main job the app exists for, payment, anything that would mean an incident if it broke.
- **Every bug fix:** a regression test that fails before the fix.

Don't write:
- "renders without crashing" tests, or tests that only check a static heading is on the page
- snapshot tests of component markup (they fail on every harmless change and get updated without anyone reading them)
- tests of the framework or libraries (that `<Link>` navigates, that Zod rejects a wrong type)
- tests that mock the unit under test, or assert on CSS class names or internal state
- tests that repeat what TypeScript already guarantees
- a test file for each component as a rule

The details, patterns and examples are in [references/testing.md](references/testing.md).

## Workflow

### Starting a new app
1. Check the latest React Router version, then scaffold with `create-react-router@latest`.
2. Turn on the strict TypeScript flags, ESLint, Vitest and Playwright, and add the CI script.
3. Set up the folder layout, `styles/global.css` with tokens, the `Skeleton` primitive, the root `ErrorBoundary` and the authenticated layout with its middleware.
4. Build features route by route, following the sections above.
5. Run `python3 scripts/audit_webapp.py <app-dir>` and fix what it reports.

### Adding a feature or route
1. Read the neighboring routes and the `components/ui/` folder first, and reuse what's there.
2. Decide the rendering strategy for the route, and which data is critical and which is streamed.
3. Write the loader or action with validation and auth, then the components, each with its `.module.css`, then skeletons for the streamed panels.
4. Add the tests the feature needs according to the list above, not one per file.
5. Run typecheck, lint, tests and the audit script.

### Reviewing or refactoring an existing app
1. Run `python3 scripts/audit_webapp.py <app-dir>` for the mechanical problems (outdated or mixed React Router versions, `react-router-dom` imports, an oversized global stylesheet, fetching in effects, snapshot and empty tests, `any` and `@ts-ignore`).
2. Then read the code for what a script can't see: waterfalls, critical data that should stream, missing auth checks, duplicated components, layout shift when data arrives.
3. Report problems ranked by their effect on users and correctness first (security, broken states, slow pages), structure second, style last. Give each one a concrete fix.

## References

- [references/react-router.md](references/react-router.md): current framework-mode patterns (config, route modules, loaders, actions, middleware, streaming, client data, error boundaries), what changed in v8, and migration from v6, `react-router-dom` and Remix. Read before writing routes.
- [references/styling.md](references/styling.md): what goes in the global stylesheet, CSS Module conventions, variants, tokens, and the skeleton primitive's CSS.
- [references/code-quality.md](references/code-quality.md): TypeScript and lint settings, component reuse rules, error handling, security basics, and the review checklist.
- [references/testing.md](references/testing.md): what to test at each level, testing loaders, actions and routed components, Playwright setup, and examples of tests to delete.
- `scripts/audit_webapp.py`: checks an app directory for the mechanical problems above. `--json` for machine output, `--strict` to fail on warnings, `--offline` to skip the npm version check.
