---
name: Infinity Africa Payment System
colors:
  surface: '#f9f9ff'
  surface-dim: '#d3daef'
  surface-bright: '#f9f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f1f3ff'
  surface-container: '#e9edff'
  surface-container-high: '#e1e8fd'
  surface-container-highest: '#dce2f7'
  on-surface: '#141b2b'
  on-surface-variant: '#3f4942'
  inverse-surface: '#293040'
  inverse-on-surface: '#edf0ff'
  outline: '#6f7a71'
  outline-variant: '#bec9bf'
  surface-tint: '#006d44'
  primary: '#005232'
  on-primary: '#ffffff'
  primary-container: '#006d44'
  on-primary-container: '#93ecb8'
  inverse-primary: '#80d8a6'
  secondary: '#56615e'
  on-secondary: '#ffffff'
  secondary-container: '#dae5e1'
  on-secondary-container: '#5c6764'
  tertiary: '#324d3e'
  on-tertiary: '#ffffff'
  tertiary-container: '#496555'
  on-tertiary-container: '#c1e1cd'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#9cf5c1'
  primary-fixed-dim: '#80d8a6'
  on-primary-fixed: '#002111'
  on-primary-fixed-variant: '#005232'
  secondary-fixed: '#dae5e1'
  secondary-fixed-dim: '#bec9c5'
  on-secondary-fixed: '#141d1b'
  on-secondary-fixed-variant: '#3f4946'
  tertiary-fixed: '#caead6'
  tertiary-fixed-dim: '#afceba'
  on-tertiary-fixed: '#042014'
  on-tertiary-fixed-variant: '#314d3e'
  background: '#f9f9ff'
  on-background: '#141b2b'
  surface-variant: '#dce2f7'
typography:
  display:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 8px
  container-max: 1280px
  gutter: 24px
  margin-desktop: 40px
  margin-mobile: 16px
---

## Brand & Style

The design system is anchored in **Corporate Modernism** with a focus on trust, reliability, and local relevance for the Tanzanian SME market. The visual language balances the precision of global fintech with an approachable, service-oriented warmth. 

The aesthetic is characterized by expansive whitespace, a restrained but authoritative color palette, and high-quality typography. Every interface element is designed to convey security and institutional stability, ensuring that business owners feel confident in the movement of their capital.

## Colors

This design system utilizes a high-contrast palette to ensure legibility and professional rigor.

- **Primary:** Deep fintech green (#006D44) is the signature color, used for primary actions, success states, and brand-critical indicators.
- **Secondary:** A soft wash of green (#E6F1ED) used for subtle backgrounds and hover states.
- **Accent (Highlight):** A vibrant but soft light green (#DCFCE7) specifically reserved for labels like "Highly Recommended" or active badges.
- **Neutrals:** A pure white (#FFFFFF) and light gray (#F9FAFB) foundation for surfaces, with sharp black (#111827) and medium gray (#4B5563) for hierarchy in typography.

## Typography

The typography system relies exclusively on **Inter** to ensure maximum legibility across digital devices. 

- **Weight Usage:** Use Bold (700) for large headlines to establish immediate hierarchy. Use Semi-Bold (600) for sub-headers and button text. Use Regular (400) for long-form body content.
- **Accessibility:** Ensure a minimum contrast ratio of 4.5:1 for all body text. Label-sm is used for all-caps utility text and should always carry a slight letter-spacing of 0.05em for better scanability.

## Layout & Spacing

The layout is built on a **12-column fluid grid** for desktop and a **4-column grid** for mobile. 

- **Spacing Rhythm:** Use a strict 8px base unit. All margins and paddings must be multiples of 8 (e.g., 8, 16, 24, 32, 48, 64).
- **Whitespace:** Prioritize generous vertical padding between sections (80px+) to maintain a high-end, uncluttered fintech feel.
- **Breakpoints:**
  - Mobile: 0px - 599px
  - Tablet: 600px - 1023px
  - Desktop: 1024px+

## Elevation & Depth

Hierarchy is established through **Ambient Shadows** and **Tonal Layering**.

- **Surfaces:** Use #FFFFFF for primary content cards and #F9FAFB for the main background.
- **Shadows:** Shadows should be extremely subtle and "airy." Use a low-opacity primary-tinted shadow (e.g., `0px 4px 20px rgba(0, 109, 68, 0.04)`) to make elements appear as though they are floating slightly above the surface. 
- **Active States:** Elements being interacted with should increase in shadow spread or shift slightly in Y-offset to provide tactile feedback.

## Shapes

The shape language is modern and approachable. 

- **Cards & Containers:** Use `rounded-lg` (1rem / 16px) as the standard for all dashboard cards and modal containers. 
- **Buttons & Inputs:** Use `rounded` (0.5rem / 8px) for interactive elements like buttons and text fields to maintain a professional, structured appearance.
- **Badges:** Use "Pill-shaped" (9999px) for status indicators and "Highly Recommended" tags to distinguish them from interactive buttons.

## Components

- **Buttons:** 
  - **Primary:** Solid #006D44 background with #FFFFFF text. High-contrast, 8px corner radius.
  - **Secondary:** Transparent background with #006D44 border or light green wash background.
- **Cards:** White background, 16px corner radius, and a subtle 1px border (#F3F4F6) combined with the ambient shadow defined in the Elevation section.
- **Input Fields:** 8px corner radius, 1px light gray border. On focus, the border should transition to Primary Green with a soft outer glow.
- **Status Chips:** Use a background color corresponding to the state (e.g., Tertiary Green for "Success") with dark green text.
- **Data Tables:** Clean, no vertical borders. Use 1px horizontal dividers (#F3F4F6). Row headers should use `label-sm` styling.
- **Highly Recommended Tag:** Use the accent light green (#DCFCE7) background with a small checkmark icon and Primary Green text.