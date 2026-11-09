---
name: SinoBridge
description: Sơn mài (lacquer) bilingual workbench for translating Chinese documents
colors:
  lac-0: "#140c0a"
  lac-1: "#1b1210"
  lac-2: "#22170f"
  lac-3: "#2e1f19"
  lac-4: "#3a2820"
  rule: "#3b2a22"
  rule-soft: "#2c1e18"
  egg: "#f1e7d6"
  egg-2: "#cbb9a0"
  egg-3: "#9f8b76"
  cinnabar: "#c8402c"
  cinnabar-hi: "#dc5640"
  cinnabar-deep: "#7d2619"
  gold: "#d9a94e"
  gold-hi: "#f0c46c"
  gold-dim: "#8a6a33"
  error: "#ff8a73"
typography:
  ui:
    fontFamily: "Be Vietnam Pro, -apple-system, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
  welcome-heading:
    fontFamily: "Be Vietnam Pro, sans-serif"
    fontSize: "clamp(1.6rem, 2.6vw, 2.3rem)"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.03em"
  section-label:
    fontFamily: "Be Vietnam Pro, sans-serif"
    fontSize: "0.74rem"
    fontWeight: 600
    letterSpacing: "0.09em"
  translation:
    fontFamily: "Be Vietnam Pro, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 400
    lineHeight: 1.75
  source-zh:
    fontFamily: "Songti SC, STSong, Noto Serif CJK SC, Source Han Serif SC, SimSun, serif"
    fontSize: "1.02rem"
    fontWeight: 400
    lineHeight: 1.85
rounded:
  tile: "1.5px"
  sm: "6px"
  md: "8px"
  lg: "16px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "20px"
  xl: "28px"
components:
  button-primary:
    backgroundColor: "{colors.cinnabar}"
    textColor: "#fff8ee"
    rounded: "{rounded.md}"
    padding: "12px 16px"
  button-primary-hover:
    backgroundColor: "{colors.cinnabar-hi}"
  button-primary-disabled:
    backgroundColor: "{colors.lac-3}"
    textColor: "{colors.egg-3}"
  button-solid:
    backgroundColor: "{colors.lac-4}"
    textColor: "{colors.egg}"
    rounded: "{rounded.md}"
    padding: "9px 14px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.egg-2}"
    rounded: "{rounded.md}"
    padding: "9px 14px"
  input:
    backgroundColor: "{colors.lac-3}"
    textColor: "{colors.egg}"
    rounded: "{rounded.md}"
    padding: "9px 11px"
  inlay-tile:
    backgroundColor: "{colors.lac-4}"
    rounded: "{rounded.tile}"
    size: "8px"
---

# Design System: SinoBridge

## Overview

A one-screen translation workbench in the world of Vietnamese sơn mài lacquer. Translating is treated like polishing lacquer: the Chinese source is the base coat, and each finished passage is polished until its translation shows in gold. The screen is a working tool (operate mode): standard web controls, a top bar, a control rail and a bilingual reader. The world contributes only palette, type, density and one signature move.

## Colors

### Primary
- **Cinnabar** `cinnabar` #c8402c: the primary action (Bắt đầu dịch / Dịch tiếp), the seal mark, and passages being translated right now. Nothing else.

### Secondary
- **Gold** `gold` #d9a94e: finished translation only (inlay tiles, spine marks, counts, success status), plus links and focus rings.

### Neutral
- Lacquer browns `lac-0`…`lac-4` own every surface, darkest at the page edge, lighter for the reader and raised controls. Eggshell `egg`, `egg-2`, `egg-3` are the three text tiers; secondary text is tinted from the lacquer hue, never grey.

### Named Rules
- **The two-state colour rule:** cinnabar means "acting now", gold means "done". Never use either decoratively.
- **No cream ground:** the light material is eggshell text on lacquer, not a paper background.

## Typography

- **Be Vietnam Pro** (self-hosted via @fontsource; built for Vietnamese diacritics) for UI and translations.
- **Song-style CJK serif** from the system for Chinese source text, at a slightly larger size and looser leading than the translation.

### Hierarchy
- Welcome heading 1.6–2.3rem/650; rail and column labels 0.74rem/600, uppercase, 0.09em tracking; body 15px; translation 0.95rem/1.75; source 1.02rem/1.85.

## Layout

- Desktop: 54px top bar; grid of a 330px control rail and a reader that fills the rest, both scrolling internally, so the working screen never needs page scroll. FAQ sits below the fold, linked from the bar.
- Reader rows: source | 34px spine | translation, translation measure capped at 68ch.
- Below 900px: rail above reader, rows stack source over translation, and the spine becomes a horizontal hairline.

## Elevation & Depth

Flat lacquer planes separated by 1px `rule` lines. The only shadow is the primary button's soft cinnabar glow (0 6px 18px -8px). The pane header uses a light blur because content scrolls beneath it.

## Shapes

8px radius on controls, 16px on the welcome drop zone, 1.5px on inlay tiles, 5px on the seal.

## Components

### Buttons
Primary (cinnabar, full width in the rail), solid (lacquer-4, exports), ghost (hairline border, secondary actions). Disabled primary turns to lacquer-3 with tertiary text.

### Inputs / Fields
Lacquer-3 fields with a gold focus border and gold caret; custom chevron on selects; a two-option segmented control for the target language.

### Navigation
Top bar text links (Hỏi đáp, GitHub) in egg-2, brightening on hover.

### Inlay progress (signature)
One 8px tile per passage (grouped when a document has more than 224 passages): lacquer-4 pending, breathing cinnabar while translating, gold when done, with slight per-tile gold variation like eggshell inlay.

### Polish reveal (signature)
When a passage lands, its translation is revealed left to right with a single gold sheen, and its spine mark turns gold. Disabled under prefers-reduced-motion.

## Do's and Don'ts

### Do:
- Keep the source visible beside every translation.
- Use cinnabar and gold only for their two states.
- Theme browser surfaces (selection, scrollbars, focus, caret) from the palette.

### Don't:
- Don't add eyebrow labels above headings or emoji/glyph icons; icons are inline SVG with a 1.7 stroke.
- Don't turn sections into same-size cards or nest cards.
- Don't introduce a light paper ground or a second accent colour.
