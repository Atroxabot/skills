# Styling structure

This file is about where CSS lives and how it's organized, not what the app looks like. The values (colors, spacing, fonts) come from the design system. The structure below keeps them in one place and keeps every component's styles scoped to that component.

## The global stylesheet

`app/styles/global.css` is imported once, in `root.tsx`. It may contain:

1. **Reset or normalize.** A short modern reset: `box-sizing`, margin resets, `img { display: block; max-width: 100% }`, form elements inheriting fonts.
2. **Tokens** as custom properties on `:root`, with dark or alternate themes overriding them under a selector or media query:
   ```css
   :root {
     --color-bg: #fff;
     --color-text: #111;
     --color-muted: #666;
     --space-1: 0.25rem;
     --space-2: 0.5rem;
     --space-4: 1rem;
     --radius-2: 6px;
     --font-sans: system-ui, sans-serif;
     --z-dialog: 100;
     --duration-fast: 150ms;
   }
   ```
3. **Base element styles:** `html`, `body`, headings, `a`, `:focus-visible`, `::selection`.
4. **`@font-face`** rules.
5. **A handful of accessibility utilities:** `.visually-hidden`, and a skip-link style.

Nothing else. Keep the total across all global CSS files under about 300 lines. Splitting it into `tokens.css` and `base.css` is fine, but the budget covers both. When the global file grows past that, look for what doesn't belong:
- styles for a named piece of UI (`.card`, `.navbar`, `.modal`): move them into that component's module
- utility classes that have piled up (`.mt-4`, `.flex-center`): replace them with module classes or a layout primitive component
- page-specific overrides: move them into the page's `route.module.css`

The reason for the budget: global CSS has no owner. Nobody knows what depends on a global rule, so nobody dares delete one, and the file only grows. A module file is deleted together with its component.

## CSS Modules

Every component and every route that needs styles has a `.module.css` file next to it, with the same base name:

```
components/ui/Button/
  Button.tsx
  Button.module.css
  index.ts
routes/_app/projects.$projectId/
  route.tsx
  route.module.css
```

### Conventions

- **camelCase class names** (`.root`, `.header`, `.itemActive`), so they read as `styles.itemActive` in TSX without bracket notation.
- **`.root` for the outermost element.** Every module has one, which makes the files easy to scan.
- **Classes only.** Style through classes, not bare element selectors. `.list li` reaches into every child component that renders an `li`. A descendant element selector is acceptable for content you don't control (rendered markdown), scoped under a class.
- **Tokens instead of literals.** `padding: var(--space-4)`, not `padding: 16px`. A literal is fine when it's truly a one-off (a specific icon size) and there's no token for it.
- **Variants** through separate classes or data attributes:
  ```tsx
  <button className={cx(styles.root, styles[variant])} data-size={size}>
  ```
  ```css
  .root { /* shared */ }
  .primary { background: var(--color-accent); }
  .secondary { background: transparent; }
  .root[data-size="sm"] { padding: var(--space-1) var(--space-2); }
  ```
  `cx` is a few lines in `lib/cx.ts` that joins truthy class names. Use a small existing package if the repo already has one; don't add one for this.
- **States** use the matching attribute selectors wherever an ARIA or HTML attribute exists already: `[aria-expanded="true"]`, `[aria-current="page"]`, `:disabled`, `[aria-invalid="true"]`. The style then can't drift out of sync with the accessible state.
- **Accept a `className` prop** on reusable components and merge it last, so a parent can position the component (margin, grid placement) without reaching into its internals. Parents shouldn't override a child's internal styles. If they need to, the component needs a variant.
- **`composes:`** is allowed for sharing a base within the same module or from a small shared module, used sparingly. Two levels deep is already hard to trace.
- **`:global`** only for styling markup you don't control (a third-party widget's classes), scoped under a local class: `.editor :global(.ProseMirror) { … }`. Leave a comment naming the library.
- **Inline `style`** only to pass dynamic values into CSS as custom properties: `style={{ "--progress": `${percent}%` }}` with `.bar { width: var(--progress); }`. Everything else goes in the module.
- **Responsive rules** live in the module next to the styles they change. Container queries (`@container`) are often a better fit than viewport media queries for reusable components, since a component's space depends on where it's placed, not on the window width.
- **Types.** Enable Vite's CSS Modules typing or add a `*.module.css` declaration, so a typo in `styles.heder` fails the typecheck.

## The skeleton primitive

One component in `components/ui/Skeleton/` that the panel skeletons are built from:

```tsx
// Skeleton.tsx
import styles from "./Skeleton.module.css";
import { cx } from "~/lib/cx";

type SkeletonProps = {
  shape?: "line" | "block" | "circle";
  width?: string;
  height?: string;
  className?: string;
};

export function Skeleton({ shape = "line", width, height, className }: SkeletonProps) {
  return (
    <span
      aria-hidden="true"
      className={cx(styles.root, styles[shape], className)}
      style={{ "--sk-width": width, "--sk-height": height } as React.CSSProperties}
    />
  );
}
```

```css
/* Skeleton.module.css */
.root {
  display: block;
  width: var(--sk-width, 100%);
  height: var(--sk-height, 1em);
  background: var(--color-skeleton);
  border-radius: var(--radius-2);
  opacity: 0;
  /* Delay the fade-in so fast responses never show a skeleton at all. */
  animation:
    sk-appear var(--duration-fast) ease-out 150ms forwards,
    sk-pulse 1.4s ease-in-out 300ms infinite;
}
.block { height: var(--sk-height, 6rem); }
.circle { border-radius: 50%; aspect-ratio: 1; height: auto; }

@keyframes sk-appear { to { opacity: 1; } }
@keyframes sk-pulse { 50% { opacity: 0.6; } }

@media (prefers-reduced-motion: reduce) {
  .root { animation: sk-appear var(--duration-fast) ease-out 150ms forwards; }
}
```

A panel skeleton uses the real panel's layout classes, so the sizes match by construction:

```tsx
// features/projects/ActivityFeed.tsx exports both
export function ActivityFeedSkeleton() {
  return (
    <section className={styles.root} aria-busy="true" aria-label="Loading activity">
      <h2 className={styles.title}>Activity</h2>
      <ul className={styles.list}>
        {Array.from({ length: 5 }, (_, i) => (
          <li key={i} className={styles.item}>
            <Skeleton shape="circle" width="2rem" />
            <Skeleton width="60%" />
          </li>
        ))}
      </ul>
    </section>
  );
}
```

The heading is real text, because it's already known. Only the parts that depend on the data are placeholders. Sharing `styles.root`, `styles.list` and `styles.item` with the real component means a layout change to the panel moves its skeleton too.

## Avoid

- CSS-in-JS libraries that inject styles at runtime. They add work to every server render and complicate streaming.
- Utility-class frameworks next to CSS Modules. Two styling systems means two ways to do everything.
- `!important`, except to override a third-party inline style you can't change (with a comment).
- Global stylesheets imported from inside components. Only `root.tsx` imports global CSS. A component that imports a global file adds rules to every page once it's loaded.
- Deep nesting. Native CSS nesting is fine one level deep for states and children (`&:hover`, `& .icon`). Deeper than that is a sign the component should be split.
