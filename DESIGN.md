---
version: alpha
name: Litebee IDE
description: Flight-show studio with a compact tool rail, mat canvas and light timeline.
colors:
  primary: "#1d1f20"
  accent: "#1b6c80"
  background: "#f0f0ed"
  surface: "#ffffff"
  text: "#131416"
  danger: "#c4242a"
  dark-background: "#111113"
  dark-surface: "#1b1b1e"
  dark-text: "#f1f1ef"
typography:
  sans:
    fontFamily: "IBM Plex Sans, Segoe UI, sans-serif"
    fontSize: "14px"
    lineHeight: "1.43"
  mono:
    fontFamily: "IBM Plex Mono, Consolas, monospace"
rounded:
  DEFAULT: "7px"
  panel: "12px"
  status: "5px"
spacing:
  panel-gap: "12px"
  page-gutter: "16px"
components:
  button: {}
  navigation: {}
  inspector: {}
  timeline: {}
  canvas: {}
---

# Litebee IDE Design System

## Overview

### Creative North Star

A flight-show studio: the mat is the stage and each drone owns a lane on the lighting timeline. The working canvas carries the identity, rather than dashboard cards. The 3 November redesign follows the user's request to replace the previous wide-sidebar design.

### Product context and register

- Audience: the author and students, preparing Python shows for LiteBee Wing on Windows laptops. Evidence: `PRODUCT.md`, `README.ru.md` and the current renderer.
- Register: product, for long classroom sessions. Russian and English; local bundled fonts cover both scripts.
- Signature: actual numbered mat cells, drone models, selectable trajectories and synchronized LED lanes from the same Show data.
- Restraint: flight controls, disabled reasons and emergency landing keep their existing behavior. No invented telemetry or demonstration totals.
- Anti-references: broad admin sidebars, navy dashboards, neon routes everywhere, nested bordered cards, marketing headers in the work surface.
- Runtime ownership: **Model B**. `desktop/src/renderer/src/styles/tokens.css` is canonical. This file mirrors accepted values; it does not generate CSS. Historical `docs/UI_DESIGN.md` describes the Qt implementation, not the current renderer.

## Colors

Light mode uses neutral warm gray chrome and white work surfaces. Dark mode uses neutral near-black chrome and charcoal work surfaces; no navy cast. Secondary text retains readable contrast. Deep cyan is retained from the established brand, with a pale equivalent on dark. LED colors are actual show data; background routes use neutral ink, while the selected route shows programmed colors. Red remains reserved for emergency landing and errors.

## Typography

Keep the already bundled IBM Plex Sans and IBM Plex Mono, including Cyrillic. UI body 14px; controls 12–14px; axis and navigation labels at least 11px; project title 24px desktop / 18px compact. Mono belongs to Python, cell coordinates and time. Numbers use tabular figures. No remote font dependency.

## Layout

Desktop: 80px tool rail, 60px project/flight bar. Main workspace uses 16px side gutters and 12px gaps. Inspector is 288px, collapsible in both code and simulation. At 1440px, 1440 − 80 − 32 = 1328px of work: 1028px canvas + 12px gap + 288px inspector. Code and preview share the remaining space.

At 1150px, the code inspector moves below the preview. At 760px, navigation becomes a bottom bar; the inspector opens as a bounded overlay, and code uses the available column. The desktop shell owns the viewport; editor, inspector and timeline own their internal scroll. Resize observers reattach when switching modes.

## Elevation & Depth

Separate work surfaces with tonal steps and whitespace. Panels have no resting shadows. Only menus and popovers float with a restrained shadow. The outer rounded sheet has been removed.

## Shape

Panels 12px, controls 7px, status tags 5px. Controls in the same row share their height. One inversion establishes the simulation play action. The four flight preparation steps remain a real ordered sequence.

## Motion

Short hover/pressed feedback only; no entrance animations. Reduced-motion styles are global. Physical flight playback and rotor movement represent the simulated show.

## Iconography

Lucide outline icons; 20px navigation, 15–16px controls. Visible short navigation labels plus full accessible names and tooltips. No decorative icon tiles.

## Components

### Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
| --- | --- | --- | --- | --- |
| Select/Listbox | `AreaBar.tsx`, `Timetable.tsx`, `LimitPopover.tsx` | Native browser/OS controls; domain options from `core/area.ts` and active fleet | Native, OS popup accepted | Browser keyboard and open popup |
| Form | `NewProjectWizard.tsx` | `core/project.ts` MAX_DRONES, existing validCount; blank name has a generated fallback | Existing project wizard | Unit project tests, browser create/cancel |
| Scrollbar | `styles/base.css` | Semantic control tokens in `styles/tokens.css` | Standard properties plus WebKit fallback | Browser scrolling and computed styles |

| Capability | Canonical runtime owner | Contract |
| --- | --- | --- |
| Palette, sizing and type | `styles/tokens.css` | Shared light/dark semantic tokens |
| Global controls, focus, scrollbars | `styles/base.css` | Native buttons, visible keyboard focus; global standard and WebKit scrollbar styles |
| Studio composition | `App.css`, `styles/studio.css` | Rail, canvas, editor, inspector, timeline; presentation of shared existing controls |
| Navigation and settings disclosure | `Sidebar.tsx`, `Sidebar.css` | Four destinations; appearance panel; short labels and full accessible names |
| Project and flight controls | `TopBar.tsx`, `ProjectMenu.tsx`, `Preflight.tsx`, `Emergency.tsx` | Preserve domain actions and reasons; emergency landing stays visible |
| Selects | `AreaBar.tsx`, `Timetable.tsx`, `LimitPopover.tsx` | Native select: OS-owned popup geometry accepted, active locale options |
| Map detail controls | `AreaBar.tsx`, `MatChart.tsx` | Routes and actual mat markers can be toggled; selected route is emphasized |
| Readouts and report | `Inspector.tsx`, `SidePanel.tsx` | Keep real warning text, findings and navigation to source/time |
| Startup and project wizard | `StartScreen.tsx`, `NewProjectWizard.tsx` | Existing example data, no invented projects; local filtering |
| Modal keyboard focus | `state/useModalFocus.ts` | Shared focus containment and restoration; underlying workspace is inert while a dialog is open |

No new CRUD, permission, network or flight-state policy is introduced by the redesign. The maintained domain implementation and tests remain authoritative for those operations.
