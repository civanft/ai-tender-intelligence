# Dashboard Page Direction

> **Project:** AI Tender Intelligence
> **Page:** Streamlit dashboard
> **Override status:** These rules replace Master typography, colors, components, and page pattern for this screen.

## Subject and job

This is a European public-procurement market-entry desk for a university admissions portfolio. Its single job is to let a reviewer move from market scope to ranked notices to inspectable evidence without mistaking profile fit for a win prediction.

## Visual thesis

Build a **European intelligence atelier**: the evidence discipline of a public registry, the compositional confidence of an institutional annual report, and the finish of a strategy consultancy briefing room. Luxury comes from proportion, typography, material contrast, and restraint—not ornament.

## Tokens

| Role | Value |
|---|---|
| Midnight registry | `#071D2A` |
| Raised midnight | `#102C37` |
| Mineral canvas | `#EAE7DF` |
| Porcelain surface | `#FBFAF6` |
| White surface | `#FFFFFF` |
| Aged brass | `#B58A48` |
| Brass highlight | `#D1A85F` |
| Oxblood signal | `#8F4035` |
| Baltic teal | `#286F6C` |
| Muted copy | `#56686C` |
| Hairline rule | `#D4CEC2` |

Country comparison colors are functional supplements: Belgium `#315F83`, Italy `#8F4035`, Finland `#286F6C`. Always pair them with labels and a data table.

## Typography

- Display: **Source Serif 4**, 400–600. Use for the masthead, section heads, dossier titles, and large metrics. Its restrained book typography should read as an institutional report rather than a fashion/editorial template.
- Body: **Public Sans**, 400–700. Use for readable interface copy and controls; its public-service character is intentionally neutral and formal.
- Data: **IBM Plex Mono**, 400–600. Use for record IDs, dates, market codes, filter summaries, and numeric annotations.

## Layout

```text
┌ midnight masthead ───────────────────────────────────────────────────────┐
│ live source / edition                                                    │
│ TENDER / INTELLIGENCE                 BEL │ ITA │ FIN market aperture    │
└──────────────────────────────────────────────────────────────────────────┘
    ┌ visible ┬ source pool ┬ change set ┬ disclosed EUR ┐
    └─────────┴─────────────┴────────────┴───────────────┘
  active view tokens
  REGISTRY | MARKETS | TIMELINE | DOSSIER | METHOD
────────────────────────────────────────────────────────────────────────────
  porcelain analytical surfaces on a mineral canvas
```

## Signature

The memorable element is the **market aperture**: a three-cell BEL–ITA–FIN instrument inside the midnight masthead. It shows real screened/source counts, uses three restrained country rules, and places each national flag at eight-percent opacity behind its corresponding cell. The flags are decorative watermarks; labels and data remain the information layer.

## Components

- Use a dark query console and dark dossier to anchor the composition.
- Summary metrics overlap the masthead edge to create one intentional layer transition.
- Use 6–18px radii selectively; do not turn every label into a pill.
- Registry rows are paginated and become stacked record cards below 1100px.
- Profile-fit components use horizontal rulers with numeric points and prose reasons.
- Keyword and CPV evidence use readable tables, never raw JSON blocks.
- Charts use direct values, restrained gridlines, accessible country labels, and table alternatives.
- Spreadsheet exports neutralize formula-like source strings.

## Explicitly avoid

- Neon, purple-blue AI palettes, glow, glassmorphism, or abstract network imagery.
- Robot, sparkle, brain, or magic-wand imagery.
- Gold-on-black ornament that carries no data meaning.
- Excessive rounded cards, floating pills, or unrelated animation.
- Generic claims such as “unlock insights” or “AI-powered intelligence.”
- Raw JSON as a user-facing explanation.

## Responsive and accessibility rules

- Maintain 4.5:1 text contrast and visible keyboard focus.
- All primary controls have a minimum 44px target.
- At 1100px, collapse the masthead to one column, metrics to 2×2, and registry rows to cards.
- At 720px, stack dossier and market content and use 16px body copy.
- Respect `prefers-reduced-motion`.
- Never rely on country color alone; preserve labels and data tables.
