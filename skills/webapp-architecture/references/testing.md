# Testing

A test is worth keeping if it would fail when a real bug ships and pass while the behavior is right. Every test costs time to run and time to update. A test that never catches anything is all cost, and a suite full of them teaches people that red builds are noise.

Two questions decide whether to write a test:
1. **What bug would this catch?** Name it. If you can't, don't write the test.
2. **Would a correct refactor break it?** If renaming a class, splitting a component or reordering markup fails the test, it's testing the implementation. Rewrite it against behavior.

## What to test, by level

| Level | Tool | Test here | Volume |
|---|---|---|---|
| Unit | Vitest | Pure logic in `lib/` and `features/*/`: calculations, parsing, permissions rules, state reducers, date and money handling | Many small, fast tests, focused on edge cases |
| Server | Vitest | Loaders, actions, middleware and `*.server.ts` functions, called directly with a `Request` and a test database or in-memory fake | One test per rule: auth, authorization, validation, not found, redirect after success |
| Component | Vitest + React Testing Library, `createRoutesStub` | Components with behavior: forms, filters, multi-step widgets, optimistic UI, keyboard handling | Only components that make decisions |
| End to end | Playwright | Critical flows through the real server: sign in, the app's core job, payment, account deletion | A few, chosen carefully |

Most of the confidence per minute comes from server tests and a few good E2E flows. Component tests are for components with real logic, not for every component.

## Server tests

Call the loader or action the way React Router would:

```ts
import { describe, expect, it } from "vitest";
import { RouterContextProvider } from "react-router";
import { action } from "./route";
import { userContext } from "~/context";

function formRequest(fields: Record<string, string>) {
  return new Request("http://test/projects/p1", {
    method: "POST",
    body: new URLSearchParams(fields),
  });
}

function contextFor(user: User) {
  const context = new RouterContextProvider();
  context.set(userContext, user);
  return context;
}

describe("rename project action", () => {
  it("rejects an empty name with a field error and leaves the project unchanged", async () => {
    const res = await action({
      request: formRequest({ name: "   " }),
      params: { projectId: "p1" },
      context: contextFor(owner),
    } as Route.ActionArgs);

    expect(res).toMatchObject({ init: { status: 400 }, data: { errors: { name: expect.any(Array) } } });
    expect(await db.project.findUnique({ where: { id: "p1" } })).toMatchObject({ name: "Original" });
  });

  it("refuses a user from another organization", async () => {
    await expect(
      action({ request: formRequest({ name: "X" }), params: { projectId: "p1" }, context: contextFor(outsider) } as Route.ActionArgs),
    ).rejects.toMatchObject({ init: { status: 403 } });
  });
});
```

Check the outcome the user or the system sees (status, returned errors, the database state, the redirect target), not which internal functions were called. Use a real test database (SQLite, a Postgres container, or the ORM's test setup) for data-layer code where you can. Mocks of the database tend to agree with whatever the code does.

Test the middleware once: no session redirects to login and keeps `redirectTo`, a valid session sets the user. Then routes behind it don't each need their own "redirects when logged out" test.

## Component tests

Query by role and accessible name, the way a user finds things, and interact through `user-event`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createRoutesStub } from "react-router";

it("shows the server's field error next to the name input", async () => {
  const Stub = createRoutesStub([
    {
      path: "/projects/:projectId/settings",
      Component: ProjectSettingsRoute,
      loader: () => ({ project: { id: "p1", name: "Original" } }),
      action: () => data({ errors: { name: ["Name is required"] } }, { status: 400 }),
    },
  ]);
  render(<Stub initialEntries={["/projects/p1/settings"]} />);

  const input = await screen.findByRole("textbox", { name: "Project name" });
  await userEvent.clear(input);
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  expect(await screen.findByText("Name is required")).toBeVisible();
  expect(input).toHaveAttribute("aria-invalid", "true");
});
```

Good component tests check: validation messages and their association with fields, disabled and pending states during submission, optimistic updates and their rollback, what an empty list or an error shows, keyboard navigation in custom widgets (menus, comboboxes, dialogs return focus).

For streamed panels, test the panel component with resolved data and with a rejected promise (the error state). Don't test that `<Suspense>` shows a fallback. That's React's job.

## End-to-end tests

- Run against a production build (`react-router build` then start the server), so SSR, hydration and streaming are exercised the way users get them.
- Seed a known state per test, and give each test its own user or organization so tests can run in parallel.
- Log in once per worker through the UI or an API and reuse the storage state. Logging in through the UI in every test makes the suite slow without testing anything new.
- Use role and label locators (`getByRole`, `getByLabel`). Wait on what the user waits on (`await expect(locator).toBeVisible()`), never on fixed timeouts.
- Keep traces on failure in CI (`trace: "retain-on-failure"`).
- A flaky E2E test is a bug, either in the test or in the app (often a real race). Fix it, don't retry it until it passes.

Worth one E2E check each: the authenticated dashboard renders its shell before the slow panels resolve, and an action that fails on the server shows the error without losing the user's input.

## Tests to delete or never write

| Test | Why it's pointless | Instead |
|---|---|---|
| `it("renders without crashing")` | The typecheck, the build and any other test already render it | Test what it does |
| `expect(container).toMatchSnapshot()` on markup | Fails on every harmless change, so people run `-u` without reading the diff | Assert the specific output that matters |
| Checking a static heading or label is present | Tests the JSX you just typed | Nothing, or test the behavior around it |
| `expect(Link).toHaveAttribute("href", …)` for a static link | Tests React Router | Nothing; E2E covers navigation |
| Testing that Zod rejects a wrong type | Tests Zod | Test your action's response to invalid input once |
| Mocking the function under test, or every collaborator | Proves the mocks agree with each other | Use real collaborators; mock only the network and the clock |
| `expect(el).toHaveClass(styles.active)` | Tests implementation; breaks on a CSS refactor | Assert the accessible state (`aria-current`, `aria-pressed`) |
| Tests repeating type guarantees ("returns a string") | TypeScript already checks it | Nothing |
| One test file per component, by policy | Produces the filler above | Test where there's logic |
| `it.skip`, or `it.only` left in | Silently disabled coverage | Fix or delete |

## Coverage

Don't set a coverage percentage as a goal. It rewards exactly the filler tests above. Use the coverage report to find untested branches in logic that matters (permissions, money, data transformations), and add tests there.

## Every bug fix gets a regression test

Write the test first, watch it fail for the reason the bug report describes, then fix the code. That proves the test can catch the bug, and keeps it from coming back.

Sources: the Testing Library guiding principles (test the way the software is used), the React Router testing docs (`createRoutesStub`), and the Playwright best-practices guide. The text above is written from those ideas, not copied.
