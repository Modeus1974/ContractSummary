---
name: Tree of Prosperity
colors:
  emerald: "#0F3D2A"      # Dark Emerald — slide background (dark mode), deep surfaces
  mint-cream: "#EAF4EF"   # Mint Cream — slide background (light mode), light surfaces
  growth-green: "#1B7A54" # Growth Green — primary text, headers, structural elements
  gold: "#D4AF37"         # Metallic Gold — accents, callouts, key metrics
  # Derived / utility tones
  surface: "#FFFFFF"      # white card surface on light mode
  emerald-soft: "#17543A" # raised cards on dark mode
  growth-soft: "#2E9468"  # hover / secondary green
  gold-deep: "#B8932B"    # gold hover / pressed
  ink-on-light: "#0F3D2A" # body text on light backgrounds
  on-emerald: "#EAF4EF"   # body text on dark backgrounds
  muted-on-light: "#4A6B5B" # supporting text on light
  muted-on-dark: "#A8C9B8"  # supporting text on dark
  error: "#C0392B"
typography:
  display-lg:
    fontFamily: Fraunces
    fontSize: 3rem
    fontWeight: 600
    lineHeight: 1.1
  headline-lg:
    fontFamily: Fraunces
    fontSize: 2.25rem
    fontWeight: 600
    lineHeight: 1.2
  headline-md:
    fontFamily: Fraunces
    fontSize: 1.5rem
    fontWeight: 600
    lineHeight: 1.25
  body-lg:
    fontFamily: Inter
    fontSize: 1.125rem
    fontWeight: 400
    lineHeight: 1.6
  body-md:
    fontFamily: Inter
    fontSize: 1rem
    fontWeight: 400
    lineHeight: 1.6
  metric-lg:
    fontFamily: Fraunces
    fontSize: 3.5rem
    fontWeight: 600
    lineHeight: 1.0
  label-caps:
    fontFamily: Inter
    fontSize: 0.75rem
    fontWeight: 600
    letterSpacing: 0.1em
    textTransform: uppercase
rounded:
  sm: 6px
  md: 12px
  lg: 20px
  pill: 999px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 48px
  xxl: 80px
components:
  button-primary:
    backgroundColor: "{colors.gold}"
    textColor: "{colors.emerald}"
    typography: "{typography.label-caps}"
    rounded: "{rounded.pill}"
    padding: 14px 28px
  button-primary-hover:
    backgroundColor: "{colors.gold-deep}"
  button-secondary:
    backgroundColor: transparent
    borderColor: "{colors.growth-green}"
    textColor: "{colors.growth-green}"
    rounded: "{rounded.pill}"
    padding: 13px 27px
  card-light:
    backgroundColor: "{colors.surface}"
    borderColor: "rgba(27,122,84,0.15)"
    rounded: "{rounded.md}"
    padding: "{spacing.lg}"
  card-dark:
    backgroundColor: "{colors.emerald-soft}"
    rounded: "{rounded.md}"
    padding: "{spacing.lg}"
  metric-callout:
    valueColor: "{colors.gold}"
    labelColor: "{colors.muted-on-dark}"
    typography: "{typography.metric-lg}"
  divider:
    color: "{colors.gold}"
    thickness: 2px
---

## Overview

Tree of Prosperity's design language is grounded, warm, and quietly premium. It evokes growth, patience, and compounding value — the feeling of wealth that is cultivated, not gambled. Deep emerald greens anchor the brand, a single gold accent signals what matters most, and generous white space keeps lecture slides and marketing pieces calm and credible rather than busy.

The system is built for two surfaces: **dark mode** (Dark Emerald backgrounds, used for title slides, section breaks, and high-impact marketing) and **light mode** (Mint Cream backgrounds, used for content-heavy teaching slides and printed collateral).

## Colors

The palette is four colors, used with discipline.

**Dark Emerald (`emerald`, `#0F3D2A`)** is the signature dark surface. Use it full-bleed for title slides, section dividers, quote slides, and bold marketing covers. On emerald, text is Mint Cream and accents are Gold.

**Mint Cream (`mint-cream`, `#EAF4EF`)** is the default light surface for teaching and reading. It is softer and warmer than white, reducing glare during long lectures. On Mint Cream, headers are Growth Green and body text is Dark Emerald.

**Growth Green (`growth-green`, `#1B7A54`)** carries headers, primary text on light backgrounds, and structural elements like icons, rules, and chart lines. It is the working color of the brand — present on nearly every slide.

**Metallic Gold (`gold`, `#D4AF37`)** is reserved. It is for one thing per view: a key metric, a callout box border, a CTA button, a single underline beneath a headline. Gold is the punctuation, never the paragraph.

Never fill a large surface with Gold or use it for body copy — it reads cheap at scale and fails contrast. Treat it like a precious metal: a little, placed precisely.

## Typography

Two families. **Fraunces** (a warm, high-contrast serif) for display, headlines, and large metrics — it gives the brand its cultivated, established character. **Inter** (a clean grotesque sans) for body, captions, and labels — it keeps dense lecture content legible.

The scale runs from `display-lg` (cover slides) down through `headline-lg` / `headline-md` (slide titles and subsections) to `body-lg` / `body-md` (teaching content). `metric-lg` is a special display size in Gold for headline numbers — growth rates, returns, milestones. `label-caps` is uppercase Inter with wide tracking for eyebrows, tags, and buttons.

For most slides you'll use `headline-lg`, `body-md`, and `label-caps`. Reach for `display-lg` and `metric-lg` only on slides built to make a single point land.

## Components

### Buttons

Primary buttons (and primary CTAs in marketing) use the Gold fill with Dark Emerald text, fully rounded into a pill. The hover state deepens the gold (`gold-deep`). This is the brand's one loud element — use a single primary button per view.

Secondary buttons are outlined: 1px Growth Green border, transparent fill, Growth Green text, same pill shape. On hover, fill lightly with Growth Green at low opacity.

### Cards & Callouts

On light slides, cards sit on a white or Mint Cream surface with a hairline Growth Green border (15% opacity) and medium rounding — no heavy shadows. On dark slides, cards use `emerald-soft` (`#17543A`) so they lift gently off the Dark Emerald background.

**Metric callouts** are the brand's signature device: a large Fraunces number in Gold, with a small `label-caps` description in muted green beneath. Use them for returns, growth figures, and key takeaways.

### Dividers & Accents

A 2px Gold rule under a headline, or a short Gold tick beside a section eyebrow, is the standard way to add emphasis. One accent rule per section maximum.

## Slide Patterns

- **Title / Section slide:** Dark Emerald full-bleed, Fraunces `display-lg` headline in Mint Cream, a short Gold underline, `label-caps` eyebrow above in Gold.
- **Teaching slide:** Mint Cream background, Growth Green `headline-lg` title, Dark Emerald `body-md` content, Gold reserved for the single most important figure or term.
- **Metric slide:** Either surface; one or three `metric-lg` numbers in Gold with `label-caps` labels.
- **Quote / testimonial:** Dark Emerald background, large Fraunces quote in Mint Cream, attribution in `label-caps` Gold.

## Do's and Don'ts

- Do use Gold sparingly — one accent moment per slide or viewport section, maximum.
- Do pair Dark Emerald backgrounds with Mint Cream text, and Mint Cream backgrounds with Growth Green / Dark Emerald text, to hold WCAG AA contrast.
- Do keep the spacing scale intact; don't invent values between the defined steps.
- Don't use Gold for body copy or large fills — it loses its premium signal and fails contrast.
- Don't put Growth Green text directly on Dark Emerald — the contrast is too low; use Mint Cream or Gold instead.
- Don't mix Fraunces into body text or Inter into display headlines; keep the serif/sans roles clean.
