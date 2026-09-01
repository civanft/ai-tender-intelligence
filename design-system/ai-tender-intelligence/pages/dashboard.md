# Dashboard Page Direction

> **Project:** AI Tender Intelligence
> **Page:** Streamlit dashboard
> **Override status:** These rules replace Master typography, colors, components, and page pattern for this screen.

## Subject and job

This is a European public-procurement signal desk for a university admissions portfolio. Its single job is to let a reviewer move from market scope to ranked notices to inspectable evidence without mistaking the result for an AI prediction.

## Visual thesis

Build a **public record observatory**, not an AI SaaS dashboard. The visual language comes from tender bulletins, registry numbers, research instruments, and European transport information systems. Keep the system cool, exact, and quietly distinctive.

## Tokens

| Role | Value |
|---|---|
| Cold paper | `#EDF1F2` |
| Registry surface | `#F8FAFA` |
| Deep ink | `#102A34` |
| Secondary ink | `#314A53` |
| Muted copy | `#5B6C72` |
| Oxide signal | `#C44F36` |
| Signal dark | `#8F3325` |
| Hairline rule | `#CBD4D7` |
| Strong rule | `#9CABB0` |

Country comparison colors are functional supplements: Belgium `#173F5F`, Italy `#C44F36`, Finland `#277B78`. Always pair them with labels or a table.

## Typography

- Display: **IBM Plex Sans Condensed**, 500–700. Use for the masthead and section heads.
- Body: **Source Sans 3**, 400–600. Use for readable interface copy.
- Data: **IBM Plex Mono**, 400–600. Use for record IDs, dates, market codes, small labels, and numeric annotations.

## Layout

```text
┌─ source / scope / edition ────────────────────────────────────────────────┐
│ TENDER / INTELLIGENCE                  BEL │ ITA │ FIN market signal rail │
└──────────────────────────────────────────────────────────────────────────┘
┌ visible ┬ source pool ┬ screening yield ┬ disclosed EUR ┐
└─────────┴─────────────┴─────────────────┴───────────────┘
  REGISTRY | MARKETS | TIMELINE | DOSSIER | METHOD
────────────────────────────────────────────────────────────────────────────
  selected analytical view
```

## Signature

The memorable element is the **market signal rail**: a bordered BEL–ITA–FIN scope instrument inside the masthead that shows screened/source counts. It encodes the actual market focus and replaces decorative hero imagery.

## Components

- Square corners, one-pixel rules, flat surfaces, no soft card cloud.
- Native filters remain visible and labelled; tags are rectangular deep-ink tokens.
- Tabs behave like a registry index with an inverted active state.
- Profile-fit components use horizontal rulers with numeric points and prose reasons.
- Keyword and CPV evidence use readable tables, never raw JSON blocks.
- Charts have direct values, restrained gridlines, accessible country labels, and table alternatives.

## Explicitly avoid

- Gradients, glow, glassmorphism, neon green, purple-blue AI palettes.
- Robot, sparkle, brain, magic-wand, or abstract-network imagery.
- Rounded cards for every statistic, excessive pills, floating shadows.
- Large generic claims such as “unlock insights” or “AI-powered intelligence.”
- Raw JSON as a user-facing explanation.
- Motion that does not explain a state change.

## Responsive and accessibility rules

- Maintain 4.5:1 text contrast and visible keyboard focus.
- At 1000px, collapse the masthead to one column and metrics to 2×2.
- At 640px, simplify metadata, stack dossier content, and make market facts vertical.
- Respect `prefers-reduced-motion`.
- Never rely on country color alone; preserve labels and data tables.
