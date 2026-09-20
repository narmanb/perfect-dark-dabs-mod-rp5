# Turn Boost: Run 129 investigation

Baseline commit: `65903e2c107701e4f7c8f9836db18139554c1150`.

## Finding and limitation

No downstream attenuation of a fully charged 2x multiplier was reproduced in
the generated walking path. Do not describe this investigation build as a fix
for the RP5 hardware report. It adds passive measurements and a deterministic
CI check so the device discrepancy can be located instead of guessed at.

The actual generated C code, compiled on the host, gives full positive stick,
Precision, sensitivity 1, no acceleration/smoothing, normal walking:

| Measurement | Boost off | Fully charged 100% |
|---|---:|---:|
| Player yaw, degrees/second | 193.789858 | 387.579964 |
| Boosted / baseline yaw | | 2.000001 |
| Engine Y-matrix yaw ratio | | 2.000001 |

192 scenarios cover both directions, 30/60/120 FPS, all four response modes,
natural and aim-turn branches, normal/half FOV and dynamics off/on. Tests
extract the code being compiled by Android CI, not a duplicate implementation.
The supplied axes are synthetic; these tests cannot establish the RP5's actual
settings, input route, ramp charge, or final camera state.

## Traced path

1. `inputReadController`: SDL axes -> physical-axis sensitivity/deadzone ->
   physical right-stick shape and dynamics, even with swapped logical sticks ->
   signed 8-bit controller axis (`/256`). Precision supplies no extra exponent;
   its later game response is squared. Dynamics code is unchanged.
2. `bmoveProcessInput`: joyGetStickX -> five-unit safe deadzone -> analogturn.
   Modern PC/swapped look divides by 127, classic divides by 70; clamp/square
   occurs BEFORE boost. Full positive modern input is 122 after safe deadzone,
   so its natural output is `(122/127)^2`, approximately .92281.
3. Natural output adds mouse freelook and FOV scaling. The alternate aim path
   updates `speedthetacontrol` toward its .7-FOV-scaled limit. Boost tests this
   unboosted output, then sets `speedtheta = speedthetacontrol * multiplier`.
   Normal walking's `bwalkUpdateSpeedTheta` only contains N64 crouch scaling,
   which is not compiled on Android.
4. `bmoveTick` calls input then `bwalkTick`; its first yaw operation is
   `bwalkUpdateTheta`. Its linear rotateamount goes into
   `bwalkCalculateNewPositionWithPush`/`bwalkCalculateNewPosition`. Pure yaw has
   zero position delta, bypasses translational collision, and updates vv_theta
   with only modulo-360 wrapping. No post-boost maximum exists there.
5. `bmoveUpdateHead` composes head roll/pitch with the full vv_theta Y rotation.
   Normal walking passes NULL for the optional quaternion interpolation matrix.
   The resulting bond2 look vector is copied by normal player tick, optionally
   tilted, and reaches `playerSetCamProperties` and camera matrix allocation.
6. DABS Body Turn Speed affects third-person tether body facing. Tether zeros a
   local animation speed variable, not the normal player speedtheta field.
   Normal first-person testing must still exclude third-person/death/cutscenes,
   recoil/shake and special camera modes.

## Actual device measurements

`Turn Boost Readout` appears in Advanced Stick Calibration and starts enabled
in this investigation build. It can be disabled and persists in config.
Seven short gameplay rows show pad/control mode/aim state, physical raw stick,
analog turn and gate amount, charge/multiplier, input/output speeds, unboosted
counterfactual and actual body rate, final camera rate, and measured ratios.
Rates use a .25-game-second window; "real" is camera degrees per wall second.
The baseline column is calculated from the SAME unboosted control value and
tick duration; body/camera columns are observed deltas, not multiplier echoes.
Detailed `turnboost` log rows also record processed stick, mouse input and all
runtime boost settings. No input, movement, camera or rendering settings are
changed by the instrumentation.

Run the user's Precision / acceleration 0 / smoothing 0 / boost 100 / ramp 3s /
threshold 50 / release .05 configuration, tether off, standing still and not
aiming. Hold full horizontal stick for at least five seconds. Capture the
readout WHILE holding the stick. Repeat at boost 0 with identical sensitivity.
At full charge the intended body/camera ratios are approximately 2.00.

* Charge below 100%: investigate input/gate/timing/aim suppression.
* Charge 100%, multiplier below 2: inspect runtime boost setting and aim mode.
* Multiplier 2, body ratio below 2: inspect actual tick/movement routing.
* Body ratio 2, camera ratio below 2: inspect final camera transformations.
* Both ratios 2: compare wall-time camera rate and timed complete rotations.

The previous comment claiming +50% at full boost is stale; runtime Run 129
already calculates +100%. Another independently visible edge case is that a
100% threshold is unreachable in the modern natural path (maximum about .923
after the safe deadzone). Neither observation explains weak boost at the
reported 50% threshold, and neither justifies raising the multiplier.
