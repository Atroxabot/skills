# React Router in framework mode

Patterns for the current React Router major in framework mode. This was written against React Router 8.4. Run `npm view react-router version` first. If the major is newer than 8, read that release's changelog and upgrade guide on reactrouter.com before relying on the code below, since majors rename and remove APIs.

## Contents
1. Baseline versions
2. Project files
3. Route modules
4. Loaders and actions
5. Middleware and auth
6. Streaming slow data
7. Client data and browser-only code
8. Navigation, pending and optimistic UI
9. Errors
10. Upgrading: v7 to v8, v6 and react-router-dom, Remix
11. Things to avoid

## 1. Baseline versions

React Router 8 requires Node 22.22 or later, React and React DOM 19.2.7 or later, and Vite 7 or later. It ships as ESM only, so the app's `package.json` needs `"type": "module"` and `tsconfig.json` should target ES2022 or later. Keep `react-router` and every `@react-router/*` package on the same version.

## 2. Project files

```
react-router.config.ts   # ssr, prerender, splitRouteModules
vite.config.ts           # reactRouter() plugin
app/root.tsx             # Layout, root component, ErrorBoundary
app/routes.ts            # route config
app/entry.server.tsx     # optional; reveal with `npx react-router reveal`
```

`react-router.config.ts`:

```ts
import type { Config } from "@react-router/dev/config";

export default {
  ssr: true,
  // Static public pages rendered once at build time.
  prerender: ["/", "/pricing", "/about"],
} satisfies Config;
```

`splitRouteModules` is on by default in v8. It puts `clientLoader`, `clientAction`, `clientMiddleware` and `HydrateFallback` in their own chunks so the component code doesn't wait for them. Set it to `"enforce"` if you want the build to fail on routes that can't be split.

`app/routes.ts`. Declare routes explicitly. The config file is the one place to see the URL structure, and layouts are easy to read:

```ts
import { type RouteConfig, index, layout, prefix, route } from "@react-router/dev/routes";

export default [
  index("routes/home/route.tsx"),
  route("login", "routes/login/route.tsx"),
  layout("routes/_app/layout.tsx", [
    ...prefix("projects", [
      index("routes/_app/projects/route.tsx"),
      route(":projectId", "routes/_app/projects.$projectId/route.tsx"),
    ]),
    route("settings", "routes/_app/settings/route.tsx"),
  ]),
] satisfies RouteConfig;
```

`app/root.tsx` imports the global stylesheet once and renders `<Meta />`, `<Links />`, `<ScrollRestoration />` and `<Scripts />` in `Layout`.

## 3. Route modules

Each route module imports its generated types from `./+types/<file>`. Run `react-router typegen` (the dev server does it automatically) and include it in the CI typecheck: `react-router typegen && tsc`.

```tsx
import type { Route } from "./+types/route";
import styles from "./route.module.css";

export function meta({ loaderData }: Route.MetaArgs) {
  return [{ title: `${loaderData.project.name} · Acme` }];
}

export async function loader({ params, context }: Route.LoaderArgs) { /* … */ }

export async function action({ request, context }: Route.ActionArgs) { /* … */ }

export default function ProjectRoute({ loaderData }: Route.ComponentProps) {
  return <main className={styles.root}>…</main>;
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) { /* … */ }
```

Exports a route module can have: `default`, `loader`, `action`, `clientLoader`, `clientAction`, `middleware`, `clientMiddleware`, `ErrorBoundary`, `HydrateFallback`, `meta`, `links`, `headers`, `handle`, `shouldRevalidate`. Use `href("/projects/:projectId", { projectId })` to build links, so a renamed route or missing param is a type error.

## 4. Loaders and actions

- Loaders run on the server for document requests and are called with a `.data` fetch for client navigations. The loaders of all matched nested routes run in parallel, so a child doesn't wait for its parent's data unless it reads it.
- Return plain objects. Use `data(value, { status, headers })` when you need a status code or headers.
- Throw `data(null, { status: 404 })` for not found, and `throw redirect(...)` to redirect. Both stop the loader, so the code after them can assume the happy path.
- In v8 the raw `request` is passed through unchanged. Use the `url` argument when you need the normalized URL (without `.data` or `?index`).
- Parse every input:

```ts
import { data, redirect } from "react-router";
import { z } from "zod";
import { renameProject } from "~/features/projects/projects.server";

const RenameInput = z.object({ name: z.string().trim().min(1).max(120) });

export async function action({ request, params, context }: Route.ActionArgs) {
  const user = context.get(userContext);
  const parsed = RenameInput.safeParse(Object.fromEntries(await request.formData()));
  if (!parsed.success) {
    return data({ errors: z.flattenError(parsed.error).fieldErrors }, { status: 400 });
  }
  await renameProject({ projectId: params.projectId, userId: user.id, name: parsed.data.name });
  return redirect(href("/projects/:projectId", { projectId: params.projectId }));
}
```

The feature function (`renameProject`) checks that the user may edit this project. Authentication in middleware says who the user is. Authorization (whether they can touch this record) belongs next to the data access, so no caller can skip it.

## 5. Middleware and auth

Middleware is always on in v8, and `context` is always a `RouterContextProvider`. A custom server's `getLoadContext` has to return one (see the middleware docs' migration section). Put authentication on the authenticated layout route so every child is covered:

```ts
// app/context.ts
import { createContext } from "react-router";
import type { User } from "~/features/auth/types";

export const userContext = createContext<User>();
```

```ts
// app/features/auth/auth.middleware.server.ts
import { redirect, type MiddlewareFunction } from "react-router";
import { userContext } from "~/context";
import { getSessionUser } from "./session.server";

export const requireUser: MiddlewareFunction = async ({ request, context }) => {
  const user = await getSessionUser(request);
  if (!user) {
    const url = new URL(request.url);
    throw redirect(`/login?redirectTo=${encodeURIComponent(url.pathname + url.search)}`);
  }
  context.set(userContext, user);
};
```

```tsx
// app/routes/_app/layout.tsx
export const middleware: Route.MiddlewareFunction[] = [requireUser];

export async function loader({ context }: Route.LoaderArgs) {
  return { user: context.get(userContext) };
}
```

Creating the context without a default means `context.get` throws if middleware didn't set it, instead of quietly returning `null`. That turns a wiring mistake into a loud error.

Two things to know:
- On client navigations, server middleware only runs when a request reaches the server, which happens when the target route (or one of its parents) has a `loader` or `action`. The authenticated layout has a loader, so this is covered. If a protected route has no loader in its chain, add `export async function loader() { return null; }` to the layout.
- Validate the `redirectTo` value on the login route: only accept paths that start with a single `/`. Otherwise the login page becomes an open redirect.

## 6. Streaming slow data

Start every query at once, `await` the ones the page can't render without, and return the rest as promises:

```ts
export async function loader({ params, context }: Route.LoaderArgs) {
  const user = context.get(userContext);
  const projectPromise = getProject(user, params.projectId); // fast, critical
  const activity = getActivity(user, params.projectId);     // slow, streamed
  const usage = getUsageStats(user, params.projectId);      // slow, streamed

  const project = await projectPromise;
  if (!project) throw data(null, { status: 404 });

  return { project, activity, usage };
}
```

Start the slow queries before awaiting the critical one, as above. If you write `const project = await getProject(...)` first, the slow queries can't start until it finishes, and the time adds up.

```tsx
import { Suspense } from "react";
import { Await } from "react-router";

export default function ProjectRoute({ loaderData, params }: Route.ComponentProps) {
  const { project, activity, usage } = loaderData;
  return (
    <ProjectLayout project={project}>
      <Suspense key={params.projectId} fallback={<UsagePanelSkeleton />}>
        <Await resolve={usage} errorElement={<PanelError title="Usage" />}>
          {(value) => <UsagePanel usage={value} />}
        </Await>
      </Suspense>
      <Suspense key={params.projectId} fallback={<ActivityFeedSkeleton />}>
        <Await resolve={activity} errorElement={<PanelError title="Activity" />}>
          {(items) => <ActivityFeed items={items} />}
        </Await>
      </Suspense>
    </ProjectLayout>
  );
}
```

With React 19 you can pass the promise to a child that calls `React.use(promise)` instead of using `<Await>`. In that case, put an error boundary around the child to catch rejections.

Details:
- You have to return an object of values and promises, not a single bare promise.
- Pending promises are rejected after `streamTimeout`, 4950 ms by default. Export `streamTimeout` from `entry.server.tsx` to change it. Keep it a little below the server's response timeout.
- A streamed promise that rejects before streaming begins (for example, while a slower parent loader is still running) has no handler yet and can crash a Node process. Add a `process.on("unhandledRejection", …)` logger in the server entry, and have data functions catch their own expected failures and return a result type.
- Only stream data the user can wait for. Anything that affects the page's status code (a 404 or 403) has to be awaited, because the status is sent before the streamed parts.

## 7. Client data and browser-only code

- `clientLoader` runs in the browser. Use it for data that only exists there (IndexedDB, local state), or to add a client cache in front of `serverLoader()`. Set `clientLoader.hydrate = true as const` and export a `HydrateFallback` only when it has to run on the first load. Otherwise the server-rendered data is used and the client loader runs on later navigations.
- For components that touch `window`, canvas or WebGL on import, load them with `React.lazy(() => import("./MapView"))` inside `<Suspense>` with a skeleton. The SSR output has the skeleton and the browser fills in the component.
- Don't import `*.server.ts` modules from code that runs in the browser. The build fails if you do, which is the point.

## 8. Navigation, pending and optimistic UI

```tsx
<Link to={href("/projects/:projectId", { projectId })} prefetch="intent">…</Link>
```

- `prefetch="intent"` loads data and code on hover or focus. `"viewport"` loads them when the link scrolls into view. `"render"` loads them right away; avoid it except for the one obvious next page.
- `useNavigation().state` is `"idle"`, `"loading"` or `"submitting"`. Use it for a global progress bar in the root layout, and to dim the outlet while a slow navigation loads.
- `useFetcher()` for mutations that shouldn't navigate. Optimistic UI reads `fetcher.formData`:

```tsx
function FavoriteButton({ project }: { project: Project }) {
  const fetcher = useFetcher();
  const favorite = fetcher.formData
    ? fetcher.formData.get("favorite") === "true"
    : project.favorite;
  return (
    <fetcher.Form method="post" action={href("/projects/:projectId/favorite", { projectId: project.id })}>
      <button name="favorite" value={String(!favorite)} aria-pressed={favorite}>
        {favorite ? "Unfavorite" : "Favorite"}
      </button>
    </fetcher.Form>
  );
}
```

- After an action, every loader on the page revalidates. Export `shouldRevalidate` on routes whose data a given mutation can't change, and return `defaultShouldRevalidate` otherwise.
- `<Link viewTransition>` uses the View Transitions API where the browser supports it.

## 9. Errors

- `root.tsx` exports an `ErrorBoundary` that renders a complete, styled page, so even a crash looks like part of the app.
- Routes that load data export their own `ErrorBoundary`. The error then replaces only that route's outlet, and the layout and navigation stay.
- Use `isRouteErrorResponse(error)` to tell expected responses (404, 403) from crashes. Show the user a message for the first kind. For the second, show a generic message and log the error. Never render stack traces in production.

## 10. Upgrading

### v7 to v8
1. Meet the baseline versions (Node 22.22+, React 19.2.7+, Vite 7+).
2. Update to the latest 7.x and fix its deprecation warnings.
3. Turn on the v8 future flags one at a time, running the tests after each: `v8_middleware` (a custom server's `getLoadContext` must return a `RouterContextProvider`), `v8_splitRouteModules`, `v8_viteEnvironmentApi` (move `isSsrBuild` config under `environments.ssr.build`), `v8_passThroughRequests` (use the `url` argument for normalized URLs), `v8_trailingSlashAwareDataRequests` (update any CDN or rewrite rules that match `.data` URLs).
4. Replace `data` with `loaderData` in `meta` args, `matches[i]` and `useMatches()`.
5. Uninstall `react-router-dom`. Import from `react-router`, and `RouterProvider` and `HydratedRouter` from `react-router/dom`.
6. Cloudflare: replace `cloudflareDevProxy` with `@cloudflare/vite-plugin`.
7. Install `react-router@latest` and every `@react-router/*@latest`, then remove the now-default `v8_*` flags from the config.

### v6 or react-router-dom
Go to the latest v7 first, following the v6-to-v7 guide (enable the `v7_*` future flags on v6, then switch imports from `react-router-dom` to `react-router`), then do v7 to v8 above. An app on `createBrowserRouter` (data mode) can stay in data mode at first. Moving to framework mode, so the app gets SSR, is a separate step: add the Vite plugin, write `routes.ts`, and convert one route at a time to a route module.

### Remix v2
Remix v2 continues as React Router v7 framework mode. Follow the official "Upgrading from Remix" guide to v7 (mostly package and import renames: `@remix-run/*` becomes `react-router` and `@react-router/*`), then do v7 to v8.

## 11. Things to avoid

- Fetching in `useEffect` for data a loader could provide.
- `unstable_` APIs in production code without a decision and a comment. In 8.4 this includes RSC framework mode and `unstable_routePatternMatching`.
- `ssr: false` for the whole app because one part needs the browser.
- Awaiting slow, non-critical data in a loader.
- Authentication checks copied into each loader instead of in middleware.
- Building URLs by string concatenation instead of `href()`.
- Mixed versions across `react-router` and `@react-router/*`.

Sources: the React Router documentation and changelog at reactrouter.com (framework mode guides, the middleware and streaming how-tos, and the v8 upgrade guide).
