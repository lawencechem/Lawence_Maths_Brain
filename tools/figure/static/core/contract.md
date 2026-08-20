# Figure contract before plotting

A publication-quality scientific figure is a visual argument, not an isolated pretty plot. Every figure starts from a claim, an evidence hierarchy, and a review-risk check before code or aesthetics. Before generating or editing code, establish the contract below.

## Python single-track backend

Formal data figures use Python, Matplotlib and NumPy. If the solver is MATLAB or another language, export traceable numeric results first and draw from those files with Python. Do not introduce a second plotting backend merely to reproduce a chart. Non-data diagrams route to `tools/diagram/SKILL.md`; GeoGebra is allowed there only for continuous 2D/3D geometry.

## Missing runtime/package rule

Check Python and the required plotting packages early. If the runtime or packages are unavailable, stop before rendering and report the exact blocker. You may provide a Python script and installation commands, but must not silently switch to another plotting language.

## Data-integrity gate

Use all user-provided observations and requested variables unless an exclusion has a scientific or statistical justification or the user explicitly requests a subset. Never reduce data merely to make a plot easier or faster to render. For large point clouds, prefer rasterized marks, hexbin/density representations, aggregation with a stated rule, or another backend-native rendering strategy.

If any row, column, replicate, image, or category is excluded, record the before/after counts, the exact rule, and the reason in the QA notes. Preserve the unmodified source data and never silently select convenient columns to satisfy a template.

## The visual-argument contract

1. **Reader gap**: state what the reader cannot judge without the figure.
2. **Core conclusion**: write the one-sentence claim the figure must defend.
3. **Carrier test**: explain why a figure is more direct than text, a formula, or a table.
4. **Evidence chain**: map each planned panel to the claim, and drop panels that do not carry unique evidence.
5. **Placement chain**: draft the lead-in, chapter location, visible observation, and downstream implication.
6. **Export contract**: set final dimensions, editable text, source data, statistics, image-integrity notes, and export formats before styling.

The highest-priority rule is: **the chart serves the scientific logic**. Aesthetic polish, template matching, and complex layout are subordinate to making the core conclusion clear, defensible, and reviewable.

For the full method to convert a request into core conclusion, evidence hierarchy, panel map, and review-risk checks, open `../../references/guides/figure_contract.md`.
