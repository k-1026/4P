---
name: Retro Arcade Survival HUD
colors:
  surface: '#f7faf9'
  surface-dim: '#d8dada'
  surface-bright: '#f7faf9'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f3'
  surface-container: '#eceeee'
  surface-container-high: '#e6e9e8'
  surface-container-highest: '#e0e3e2'
  on-surface: '#191c1c'
  on-surface-variant: '#3f4948'
  inverse-surface: '#2d3131'
  inverse-on-surface: '#eff1f0'
  outline: '#6f7979'
  outline-variant: '#bec9c8'
  surface-tint: '#196969'
  primary: '#156666'
  on-primary: '#ffffff'
  primary-container: '#367f7f'
  on-primary-container: '#f3fffe'
  inverse-primary: '#8bd3d2'
  secondary: '#4a6362'
  on-secondary: '#ffffff'
  secondary-container: '#cce8e7'
  on-secondary-container: '#4f6968'
  tertiary: '#864d30'
  on-tertiary: '#ffffff'
  tertiary-container: '#a36546'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#a7efef'
  primary-fixed-dim: '#8bd3d2'
  on-primary-fixed: '#002020'
  on-primary-fixed-variant: '#004f50'
  secondary-fixed: '#cce8e7'
  secondary-fixed-dim: '#b0ccca'
  on-secondary-fixed: '#051f1f'
  on-secondary-fixed-variant: '#324b4a'
  tertiary-fixed: '#ffdbcc'
  tertiary-fixed-dim: '#ffb693'
  on-tertiary-fixed: '#351000'
  on-tertiary-fixed-variant: '#6d391d'
  background: '#f7faf9'
  on-background: '#191c1c'
  surface-variant: '#e0e3e2'
typography:
  headline-xl:
    fontFamily: Space Grotesk
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 22px
    fontWeight: '700'
    lineHeight: 30px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 18px
    fontWeight: '700'
    lineHeight: 26px
  body-lg:
    fontFamily: Public Sans
    fontSize: 15px
    fontWeight: '500'
    lineHeight: 22px
  body-md:
    fontFamily: Public Sans
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-sm:
    fontFamily: Public Sans
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 15px
  label-lg:
    fontFamily: Space Mono
    fontSize: 14px
    fontWeight: '700'
    lineHeight: 18px
    letterSpacing: 0.02em
  label-md:
    fontFamily: Space Mono
    fontSize: 12px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Space Mono
    fontSize: 10px
    fontWeight: '400'
    lineHeight: 14px
spacing:
  gutter: 12px
  margin: 16px
  space-xs: 4px
  space-sm: 8px
  space-md: 12px
  space-lg: 16px
  space-xl: 24px
---

## Brand & Style

This design system blends 16-bit arcade nostalgia, retro computing (Windows 95/classic X11), and playful RPG HUD dynamics tailored for local data analytics. Designed for public business insights, demographic data, and culinary survival statistics ("대구 음식점 생존배수"), the visual tone turns dry open-government telemetry into an engaging retro dungeon-crawler experience.

### Aesthetic Principles
- **Early Cyber-Arcade meets Classic OS:** Heavy reliance on classic 3D beveled surfaces, chiseled panel insets, crisp high-contrast retro borders, and CRT phosphor accents.
- **Heroic Gaming Metaphor:** Longevity and survival ratios translate directly into retro RPG metrics (EXP bars, survival multipliers, equipment tiers like "무딘 강철 검", pixelated turtle companions).
- **Dense, Legible Utility:** High data density inspired by classic simulation games (SimCity 2000, Theme Hospital) and Win95 administrative dialogue suites, providing immediate clarity across dense tabular registers, maps, and stat readouts.

## Colors

The palette embraces the quintessential Windows 95 desktop environment infused with tonal spot arcade phosphor tones and warm vintage chassis neutrals.

- **Primary (`#398282` Tonal Teal):** Represents systemic authority, primary active headers, title bar gradients, and focused states.
- **Secondary (`#627C7B` Muted Phosphor Slate):** Applied to active survival multipliers, positive longevity metrics, live operational markers, and high-score rankings.
- **Tertiary (`#527C96` Quest Blue-Amber):** Highlights top-tier leaderboard medals, critical statistical callouts, warning indicators, and special badge milestones.
- **Neutral Core (`#737878` System Gray & Chassis):** The structural base for window frames, toolbars, bevel edges, and inset wells. Paired with crisp high-contrast borders and retro accents.

## Typography

Typography bridges utilitarian administrative legibility with retro computing charm.

- **Display & Headlines (`Space Grotesk`):** Delivers geometric precision with a tech-forward attitude reminiscent of 90s CD-ROM multimedia encyclopedias.
- **Body & Data Tables (`Public Sans`):** Ensures clear rendering for Korean and Latin script across dense table cells, address strings, and contextual descriptions.
- **Labels, Telemetry, and Multipliers (`Space Mono`):** Monospace numerals give coordinates, survival multipliers (`1.13배`), dates, rankings, and distance metrics an authentic terminal HUD readout feeling.

## Layout & Spacing

The layout employs a modular multi-pane desktop architecture built on a rigid 4px base increment.

### Structural Flow
- **Desktop (1200px+):** Three-column workspace layout. 
  - **Left Rail (280px-320px):** System control panel, active filters, candidate lists, and top-ranking telemetry.
  - **Center/Primary Stage (Fluid):** Search hero, primary target HUD gauge, survival multiplier summary, and interactive geospatial mapping viewport.
  - **Bottom Deck (Spanning/Anchored):** High-density tabular comparator registry showing nearby closed vs. open competitors.
- **Tablet / Laptop (768px - 1199px):** Two-column split with collapsible parameter sidebars.
- **Mobile (<768px):** Single-column stacked deck. Tabbed toggles between "HUD Score", "Map View", and "Leaderboard" with a persistent bottom ticker bar.

## Elevation & Depth

Visual depth is strictly physical and bevel-driven, avoiding modern diffuse gaussian dropshadows in favor of sharp directional light and shadow edges (top-left light source at 45 degrees).

### Bevel Schema
- **Window & Modal Canvas (Outset Frame):** 
  - Outer border: 1px solid `#DFDFDF`.
  - Top & Left inner border: 1px solid `#FFFFFF`.
  - Bottom & Right inner border: 1px solid `#808080`.
  - Exterior edge: 1px solid `#000000`.
- **Sunken Fields & Wells (Inset Data Sinks):**
  - Used for input boxes, data tables, map containers, and metric wells.
  - Top & Left: 1px solid `#808080` overlaid with 1px solid `#000000`.
  - Bottom & Right: 1px solid `#FFFFFF`.
  - Background fill: Pure `#FFFFFF` or terminal pitch `#111827`.
- **Pressed & Active Elements:** Inverts bevel borders immediately to simulate mechanical tactile depression.
- **CRT Scanline Texture:** Optional subtle horizontal repeating scanline overlay (1px line at 4% black opacity) on preview monitors and map overlays.

## Shapes

Strict zero-radius geometry (`roundedness: 0`). 

All buttons, inputs, dialog containers, progress bars, and badges adhere to hard 90-degree corners. Authentic 8-bit/16-bit stepped pixel cutouts are reserved for custom game sprite icons (such as the mascot turtle and RPG weapon items).

## Components

### Window Frames & Panels
- **Title Bar:** Gradient fill from `#000080` (Navy) to `#1084D0` (Active) with crisp white bold text. Inactive windows use `#808080` to `#B5B5B5`. Includes classic square minimize, maximize, and `[X]` exit buttons with centered 1px glyphs.
- **Window Body:** Flat `#C0C0C0` background with a 1px outset bevel border and 8px interior padding.

### Buttons & Arcade Triggers
- **Standard System Button:** `#C0C0C0` fill, 2px raised bevel (`#FFFFFF` top-left, `#808080` / `#000000` bottom-right). Active state inverts shadows with a 1px downward text shift.
- **Arcade Action Button (`시작` / Search):** Primary `#398282` or vibrant retro blue `#0000AA` with crisp white pixelated text, black outline, and high-contrast focus rings.

### Inputs & Search Fields
- **Inset Search Bar:** 2px sunken border, pure white `#FFFFFF` interior, monospace placeholder text, paired with a pixelated magnifying glass icon.
- **Checkboxes & Radios:** Sharp square indicators with deep inset shadows. Checkmark is a 2px high-contrast black/green retro pixel tick.

### Metric HUD Cards & Gauge Bars
- **Survival Multiplier HUD:** Sunken dark terminal card or crisp Win95 gray well. Displays big-character monospace values (`1.13배`) tinted in `#627C7B` or positive accents.
- **EXP / Longevity Comparison Bars:** Segmented or dual-tone horizontal level bars. The user restaurant bar uses vibrant `#398282` or `#627C7B`, while the peer closure baseline uses an amber `#527C96` bar framed in a 2px inset well.

### Data Tables & Status Ticker
- **Grid Header:** Gray `#C0C0C0` column headers with raised 3D bevel separators that react visually to click-sort triggers.
- **Rows:** Alternating zebra striping (`#FFFFFF` and `#F5F5F5`). Active row selection uses solid `#000080` background with pure white text.
- **Footer Status Bar:** Classic segmented inset bar at the screen base showing active tally: `대구 음식점 97,575곳 탐색 가능 | EPSG:5174 READY`.