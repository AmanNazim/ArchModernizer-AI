---
name: nextjs-ui-standard
description: Enforces modern Next.js/React frontend conventions — functional components with hooks only (no class components), Tailwind CSS for all styling (no ad hoc CSS frameworks or inline style objects), modular and responsive component structure, and loading skeletons for anything that fetches data. Use this whenever writing, editing, or reviewing Next.js/React components, building any frontend UI, adding a data-fetching component, or when the user asks for a page, component, form, dashboard, or "the frontend for X" — even if they don't name React, Tailwind, or Next.js explicitly. Also use when reviewing existing frontend code for class components, non-Tailwind styling, missing loading states, or unjustified UI library imports.
---

# Next.js UI Standard

The failure mode this skill exists to prevent isn't bad taste — it's inconsistency. Left unconstrained, component generation drifts: one file uses a class component because that's a common pattern in older training data, another reaches for styled-components or a random CDN CSS framework, a data-fetching component ships with no loading state because the happy path was the only one considered. None of these are wrong in isolation, but a codebase where every file made a different choice is expensive to maintain. This skill pins the choices down so every generated component looks like it came from the same team.

## Core rules

### 1. Functional components with hooks — never class components

Every component is a function (arrow function or `function` declaration), using `useState`, `useEffect`, `useContext`, `useReducer`, etc. for anything a class component would have used `this.state`, lifecycle methods, or context consumers for. There is no scenario in current Next.js/React development where a class component is the right default — if existing code has one, that's a candidate for conversion during review, not a pattern to match.

```tsx
// Correct
export function UserCard({ userId }: { userId: string }) {
  const [user, setUser] = useState<User | null>(null);
  useEffect(() => {
    fetchUser(userId).then(setUser);
  }, [userId]);
  return <div>{user?.name}</div>;
}
```

```tsx
// Flag and convert — class component, lifecycle methods
class UserCard extends React.Component {
  componentDidMount() {
    /* ... */
  }
  render() {
    /* ... */
  }
}
```

### 2. Tailwind CSS for all styling — no exceptions without an explicit ask

Style with Tailwind utility classes directly on elements. Do not:

- Write separate `.css`/`.scss` files for component styling.
- Use inline `style={{ ... }}` objects for anything Tailwind can express (spacing, color, layout, typography, borders, shadows).
- Pull in a different styling approach (styled-components, CSS-in-JS, Bootstrap, Bulma, Material UI's styling system) unless the user explicitly names it.

If a design genuinely needs something Tailwind's utility classes can't express directly (a complex keyframe animation, a highly specific gradient), use Tailwind's arbitrary-value syntax (`w-[137px]`, `bg-[radial-gradient(...)]`) before reaching for a separate stylesheet — arbitrary values stay within the Tailwind system rather than fragmenting the styling approach.

### 3. No external UI component libraries unless explicitly requested

Do not import shadcn/ui, MUI, Chakra, Ant Design, Radix (as a pre-styled component, not the unstyled primitive), or similar component libraries by default. Build UI elements — buttons, modals, dropdowns, tabs, accordions, toasts — from scratch using semantic HTML and Tailwind utility classes. This keeps the bundle small, keeps every component's visual language consistent with the rest of the app instead of inheriting a library's own design opinions, and avoids introducing a dependency the user didn't ask for.

If the user does explicitly name a library ("use shadcn for this," "add MUI"), use it as asked — this rule is about not defaulting to one silently, not about refusing one on request.

### 4. Components are modular

Each component does one job and is sized to be reused. Concretely:

- A component that mixes data-fetching, business logic, and a large chunk of unrelated markup is a signal to split it — extract the fetch into a hook (`useUserData`), and break large markup blocks into named sub-components rather than one file with everything inline.
- Shared visual patterns (a card, a button variant, a form field) become their own component the first time they're needed a second place, not copy-pasted.
- Props are typed explicitly (TypeScript interfaces/types) rather than left as implicit `any` — this is what makes a component safely reusable by someone who didn't write it.

### 5. Responsive by default

Every component that renders visible layout uses Tailwind's responsive prefixes (`sm:`, `md:`, `lg:`, `xl:`) to adapt spacing, layout direction, and visibility across breakpoints — not just a single fixed-width design that happens to look fine on the viewport it was written against. At minimum, check: does this layout hold up at a narrow mobile width and a wide desktop width, not just whatever was assumed while writing it?

### 6. Every component that fetches data ships with a loading skeleton

If a component calls an API, a server action, or otherwise has a state where data hasn't arrived yet, it must render a loading skeleton during that state — not a blank screen, not a bare "Loading..." text string as the only treatment, and not an unhandled `undefined` that crashes downstream rendering. The skeleton should approximate the shape of the loaded content (matching card/list/text dimensions) so the layout doesn't jump when data arrives. See `references/patterns.md` for a skeleton component pattern to reuse rather than rebuilding one per feature.

This applies to client-side fetching (`useEffect` + `fetch`, SWR, React Query) and to Next.js Server Components with `Suspense` boundaries alike — the mechanism differs, the requirement doesn't.

## Review checklist

When reviewing existing frontend code, flag in this order:

1. Class components — convert to functional + hooks.
2. Non-Tailwind styling (separate stylesheets, inline style objects, a different CSS framework) — convert to Tailwind utilities.
3. An external UI library import with no corresponding explicit user request for it.
4. A data-fetching component with no loading skeleton (blank screen or bare text during the loading state).
5. A component handling more than one concern (fetching + heavy business logic + large unrelated markup) that should be split.
6. Layout with no responsive breakpoint handling — fixed widths/columns that won't hold up on mobile.

## Reference

`references/patterns.md` has full code for: a reusable skeleton component, a data-fetching component that uses it correctly, a custom modal/dropdown built without a UI library, and a responsive card grid layout — use these as the starting shape for new components rather than improvising the pattern each time.
