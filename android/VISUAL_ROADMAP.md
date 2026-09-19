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
