# Perfect Dark Android Visual Roadmap

## Current / screen-space effects
- Sharpen (Basic / Adaptive)
- Vignette
- Film grain
- Colour grading, exposure, gamma, vibrance, temperature, tint, white point
- Tone mapping, posterize, dithering
- Bloom, bloom threshold, bloom radius
- Screen-space lens dirt (kept for now, not a priority)
- Light streaks
- Chromatic aberration
- Lens distortion
- Post-process anti-aliasing: FXAA and SMAA Lite

## Deferred until event/game-state hooks are used
Do not spend time faking these with screen brightness alone. Revisit them together as a proper event-aware visual system:
- Event-driven lens dirt / temporary lens contamination
- Explosion flash and proximity-scaled bloom/exposure response
- Muzzle-flash response
- Damage vignette
- Low-health desaturation / damage grading
- Automatic underwater visual treatment
- Heat/explosion distortion tied to actual world events
- Event-aware glow for explosions, lasers and muzzle flashes

## Android bug fixes / polish
- Fix touch-control/input state after Android app resume. This is broader than the original gameplay-stick symptom: after backgrounding/minimizing and resuming, touchscreen input can be remapped/corrupted globally. In gameplay the left MOVE stick can behave like the right LOOK stick; if the app is backgrounded while a menu is open, the on-screen arrow buttons can instead trigger Back/Confirm, move in the wrong direction, or otherwise map to incorrect actions. Physical controls are unaffected. Treat this as an Android resume/touch-state restoration bug, not a MOVE-stick-only bug. On resume, cancel/reset all stale touch pointers/gesture ownership, clear per-control pressed state, rebuild the normal touch regions/action bindings, and verify both gameplay sticks and menu buttons after resume.
- Remove/hide the Recording tab from Dab's Mod Options for the Android build. It can be restored later if recording is reintroduced.
- Redesign the Android launcher layout. The current launcher is functional but visually/layout-wise poor. Review the complete launcher flow and controls before implementing the redesign so the new layout is deliberate rather than incremental patchwork.

## Later presentation work
- Cinematic bars
- HUD scaling and visual options
- Modern crosshair options
- Weapon/viewmodel FOV, scale and position
- Camera smoothing and head-bob controls
- Performance/FPS overlay
- Visual presets

## Harder renderer work for later
- SSAO / HBAO-style ambient occlusion
- Depth of field
- Motion blur
- Volumetric lighting / god rays
- Normal/specular/emissive material extensions
- Dynamic shadows / shadow maps
- Screen-space reflections / upgraded water
- Higher-end model, particle and material upgrades
