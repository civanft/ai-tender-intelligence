# Research workspace design

## Filter desk

The sidebar uses compact, inline disclosure cards for market coverage, technology
and record status. Closed cards show the selection count or status summary;
expanded cards retain the native labelled multiselect and keyboard controls.
Selections remain mounted across reruns so changing another filter, resizing or
switching themes does not clear them. Long labels wrap within scrollable native
selection areas. Restrained neutral tags replace the previous solid blue chips.
Coverage and ranking are separate groups, with a smaller brand lockup and a
secondary reset action. Verified in light/dark themes and at 390 px width.

## Theme and branding update

The native three-dot menu provides System, Light and Dark choices through
explicit Streamlit light/dark configurations. CSS light-dark() colors inherit
Streamlit's color-scheme immediately, without JavaScript or a server rerun.
Custom chart surfaces are transparent and labels follow the same palette.
Print is hidden with its specific menu test ID; other menu controls remain.
Recheck this selector when upgrading Streamlit. The supplied, unmodified
tenderi.png is bundled as your-intelligence-coach-logo.png for the header, sidebar
and favicon. The alternate cutout was not used because its edges contain artifacts.
Browser verification confirmed both native theme selections, successful logo
loading and the absence of a visible Print item.

The interface serves researchers comparing public AI and data procurement in
all 27 European Union member states. Its main job is to move from a filtered opportunity
to inspectable source evidence.

## Visual direction

The signature element is the market coverage panel: three country tracks show
the actual fraction of active notices classified as relevant. Subtle flag
watermarks preserve the country identity without competing with the figures.
This is snapshot coverage, not market share or a winning probability.

- Ink `#1B304C`: headings and identity.
- Research blue `#315EAA`: selection, links and primary actions.
- Workspace `#F2F5F8`: page background.
- White `#FFFFFF`: reading surfaces.
- Slate `#52667B`: secondary text.
- Rule `#D9E2EA`: boundaries.

Public Sans handles controls, body text and tabular figures. Source Serif 4 is
reserved for the main statement and notice title; IBM Plex Mono identifies
timestamps and record metadata. Country chart marks use blue, muted red and
green consistently.

The layout combines a filter sidebar, persistent product identity and six
destinations: Overview, Opportunities, Markets, Timeline, Dossier and Method.
Overview alone contains the introductory hero. Its research brief uses actual
filtered theme counts, explains the five scoring components, and links three
notices in the current sort order to their dossiers. It does not invent editorial
recommendations. Analysis destinations omit the hero to prioritize evidence.

Notice selections use wide rows with separate metadata, title and value columns
so lengthy official titles do not become narrow towers of text.
EU-27 coverage now uses a compact 27-country matrix instead of three fixed
country tracks. All member states remain selectable even when no loaded notice
matches a country. Market comparison uses horizontal bars with country labels
and expandable summaries to keep 27 countries readable on narrow screens.
Timeline offers a combined view for the full selection and up to six individual
market series per chart; its accessible data table retains every selected market.
On narrow screens coverage rows and notice cells stack. Notice titles remain
complete, without line clamping. Empty filters offer an inline reset action;
Method stays accessible even when no notices match. Trusted TED-link handling
and the underlying data, scoring and export logic remain in place.

Motion consists of a brief country-track reveal and quiet hover transitions.
Reduced-motion preferences disable animation. Keyboard focus remains visible.

All component styling is consolidated in `assets/dashboard_luxe.css`. The
duplicate inline style block and finishing stylesheet have been retired. Use
stable Streamlit keys and semantic classes rather than generated CSS hashes.
Fonts use Google Fonts with local fallback stacks; no new JavaScript dependency
or external account integration was introduced.

## Verification

The automated suite includes synthetic-database AppTest coverage of all six
destinations, exact featured-notice routing, empty-search recovery and Method
access with empty results. Tests never mutate the user's database. Browser QA
checks desktop and 390px mobile layouts. All 58 tests passed; mobile Overview,
Opportunities and Dossier checks found no horizontal document overflow. A browser
click also verified that the second selection opens TED record 541158-2026.
Public deployment remains separate
from this local design change.

## Research desk extension

Research desk and Buyers extend the navigation with watchlists, side-by-side
comparisons, deadline planning, personal ranking, buyer snapshot profiles and
portable research exports. The visual tokens above remain authoritative.
New research panels use restrained blue rules, complete notice titles, readable
explanations and native form controls. See `research_desk.md` for calculations,
session privacy and feature limits. The public data pipeline is unchanged.
