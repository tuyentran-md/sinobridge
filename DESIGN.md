# SinoBridge — Design direction

**Updated 2026-11-09 · Paper & Ink (giấy và mực)**

## North star

SinoBridge should feel like opening a thoughtfully printed bilingual book, not like configuring an AI dashboard. Its visual reference is a Chinese handscroll: luminous xuan paper, muted green-grey ink washes, distant mountains, a few bamboo strokes, and one restrained red seal. The product remains practical and open to general readers as well as researchers.

### What the owner asked for

- An unmistakably Sino-inflected identity, not a generic "AI tool" template.
- Bright, airy and warm rather than dark lacquer.
- A little watercolor landscape in the background, **never under the actual bilingual reading text**.
- Fewer nested cards, fewer decorative chips and no wall of identical controls.
- Web demo and locally served app should share a consistent character.

## Tokens

| Role | Value | Usage |
|---|---|---|
| Paper | `#faf9f4` | Reading surface |
| Warm ground | `#f4f2e9` | App canvas and rail |
| Soft celadon | `#e9eae0` | Segmented controls and neutral UI |
| Ink green | `#273b30` | Primary typography |
| Ink grey | `#52665a` | Supporting copy |
| Cinnabar | `#a43e34` | Seal, main action, small highlights |
| Faint border | `#d9dfd4` | Section separators and form fields |
| Completed sage | `#91a789` | Translation completion progress |

Cinnabar means the **primary action or a small identity accent**; it must not fill every button. Muted sage is completion. Gold, if present, is barely a supporting accent, not a second saturated color.

## Typography

- UI and Vietnamese translations: Be Vietnam Pro where available; system sans in local app.
- Source Chinese: Songti / Noto Serif CJK. Maintain comfortable line height.
- Literary accent: Georgia italic only for *one short phrase* in the welcome heading.
- Clear hierarchy: editorial welcome heading; restrained functional side-rail labels; source-and-translation pairs as the visual priority once a document is open.
- All prose must sound like a normal Vietnamese product, without AI marketing filler.

## Composition

### Website (`web/`)

1. **Header:** a 34px red seal bearing 譯, an editorial SinoBridge wordmark, discreet navigation and theme toggle.
2. **Left work rail:** compact numbered steps (01–04). No nested card stack. Existing document, provider, export and progress controls remain accessible.
3. **Welcome state:** left-aligned editorial headline, gentle watercolor landscape to the right/back, a solid-paper import surface, a short three-step explanation.
4. **Reading state:** nearly flat, undistracted parallel Chinese and Vietnamese/English rows; no landscape behind text. Small passage-spine marks communicate progress.
5. **Mobile:** vertical sections, wide touch targets, no horizontal overflow. The welcome landscape fades out more strongly behind text.

### Local app (`src/sinobridge/static/index.html`)

Share the same palette and background scene. Remove rounded dashboard-card styling in favor of page sections separated by fine rules. The existing workflow, bilingual preview, account modes and local privacy notices must remain intact.

## Watercolor asset

`web/ink-landscape.svg` is a custom local vector, no remote image or external CDN. It shows faded mountains, water, a distant bridge and bamboo at the right edge; it is purely decorative and has no semantic UI content. The local app embeds the asset so that its HTTP server needs no new static-file route.

## Accessibility and technical invariants

- Foreground text retains contrast and no decorative mountain overlays translated text.
- The drop area remains keyboard operable and can be activated from the file picker.
- Both light and dark modes work. Light is the default.
- Respect reduced-motion preference.
- No change to the provider credentials, translation, saved-document format, persistence or export logic.
- Bundle fonts and art locally; do not depend on Google Fonts or an image CDN.
- Verify a full no-real-model browser smoke test and responsive widths 320–1440px before considering deployment.
- Commit, push and deployment still require explicit approval.

## Anti-patterns

No dark full-screen lacquer, purple/blue AI gradients, centered SaaS hero, multiple equal-weight cards, rounded badges on every label, fake usage figures, enormous Chinese glyph overlays or illegible decorative calligraphy. The visual theme must support reading rather than announce itself.
