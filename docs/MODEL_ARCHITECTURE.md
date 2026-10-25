# Personal gaze model architecture

Updated: 2026-10-25 (America/Los_Angeles).

Status: proposed design accompanying the [collection plan](DATA_COLLECTION_PLAN.md). Only capture and diagnostic feature extraction currently exist. No personal gaze model or session calibration implementation is claimed here.

## 1. Three distinct jobs

```text
Unmirrored RGB camera frame
    -> fixed pretrained face detection and landmark inference
    -> normalized iris coordinates + quality and pose measurements
    -> four-corner session calibration
    -> session-only screen estimate
    -> optional learned personal correction
    -> validity handling
    -> later: temporal filtering and a separate desktop controller
```

The pretrained vision model answers where eye/face landmarks appear in an image. Session calibration establishes how this user's current eye geometry corresponds to this screen. Personal training learns repeatable errors that remain after that calibration across varied sessions.

Ordinary collection is possible before personal training: its labels come from displayed targets, and four-corner fitting does not depend on a previously trained personal model. The same calibration procedure must be available at deployment. Later filtering and blink gestures are separate from the spatial gaze mapping.

## 2. Fixed visual front end

The existing runner uses local MediaPipe Face Landmarker with one face and timestamped video inference. Google describes its bundle as a face detector, a face mesh network producing 478 3D landmarks, and an optional expression/blendshape stage. The project currently uses the landmark outputs; it does not train that bundle or use expression scores as verified blink force.

The current official guide lists a 192x192 detector input and a 256x256 FaceMesh-V2 input. These are model-internal inputs, not the webcam resolution. Native 1080p may improve the source crop before resizing, but it does not make the network larger or establish higher gaze accuracy. These published architecture details are not an independent inspection of every layer in the local binary. [Official guide](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker)

The checked local `models/face_landmarker.task` is 3,758,596 bytes (approximately 3.76 MB, 3.58 MiB). Bundle file size is not parameter count, runtime RAM or total installed software size. Keep the tested model hash rather than silently downloading a new version.

## 3. Features extracted from landmarks

For each eye, the existing adapter takes two corners, upper/lower eyelid points and an iris center. Let the corners be `a,b`, midpoint `m=(a+b)/2`, eye width `w=||b-a||`, local horizontal axis `h=(b-a)/w`, and local vertical axis `v=(-h_y,h_x)`. For iris center `p`:

```text
eye_x = dot(p-m, h) / w
eye_y = dot(p-m, v) / w
openness = distance(upper_lid, lower_lid) / w
```

Dividing by eye width reduces sensitivity to image scale. Using a local eye axis reduces simple in-plane rotation effects. Neither operation fully removes perspective, head rotation, glasses effects or landmark error. Preserve eye identity and the unmirrored coordinate convention.

The current adapter also provides eye-pair midpoint x/y, interocular-width fraction, and eye-line roll. These are image-derived pose proxies, not calibrated yaw/pitch or measured physical depth. Keep openness/geometry primarily for eligibility; adding eyelid openness to gaze regression can accidentally make predictions blink-dependent.

## 4. Four-corner calibration: small transforms fitted each session

Propose fitting a separate 2D affine map for each eye. For eye `e`, using only its four anchor summaries:

```text
c_e = A_e * [eye_x, eye_y]^T + b_e
```

`A_e` is 2x2 and `b_e` has two elements: **6 fitted coefficients per eye, 12 per session**. The outputs are preliminary normalized screen coordinates. Each corner supplies two scalar label constraints; four non-collinear eye-space anchors support the six affine coefficients with residual information available. An affine map accommodates translation, axis scale, rotation and shear; it does not model arbitrary nonlinear distortion.

Fit to robust per-anchor summaries with equal corner weights. Record rank/conditioning and within-anchor variation. Reject degenerate mappings rather than relying on regularization to manufacture evidence. Use standardized anchor inputs and a fixed, development-selected ridge penalty if needed; do not tune it on the session's center or scored targets. The intercept is not penalized.

Use the equal-eye average as the **session-only baseline**:

```text
p0 = (c_left + c_right) / 2
```

Both eyes must be eligible for this initial baseline. The center check assesses the result but does not fit it. Four noisy corner fixations cannot guarantee an accurate screen interior; compare nine-point calibration later if required, under a separately recorded protocol.

Per-eye maps avoid fitting a flexible four-feature gaze model from only four spatial anchors. Repeated frames improve anchor precision but do not create new calibration positions. A full projective transform can exactly interpolate four correspondences yet amplify noise; it is not the initial choice.

## 5. Personal correction trained across sessions

After every training session is normalized using its own designated four anchors, construct eight features:

```text
z = [c_left_x, c_left_y, c_right_x, c_right_y,
     delta_midpoint_x, delta_midpoint_y, delta_log_scale, delta_roll]
```

Pose deltas use a robust reference from that session's calibration anchors. Scale uses `log(current_scale/reference_scale)` for positive valid scales; roll differences must be wrapped consistently. A pose outside supported ranges remains invalid even when the model emits a finite number.

Learn a residual correction with multi-output ridge regression:

```text
z_std = (z - training_mean) / training_scale
residual = W * z_std + b
prediction = p0 + residual
```

`W` is 2x8 and `b` has two elements: **18 personal coefficients**, plus 8 training means and 8 scales. Fit those statistics on training sessions only. This yields 12 session-affine coefficients plus 18 shared personal coefficients; extra normalization/reference metadata is separate.

The objective is weighted squared error between predicted and known target coordinates plus an L2 penalty on `W`. It discourages unstable large corrections. Give each fixation comparable total weight and balance sessions/regions so an extended target or high-FPS session cannot dominate. Tune regularization on grouped training folds/development sessions, never final test fixations. [Ridge documentation](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html)

Compare against the session-only baseline and a four-input correction using only calibrated eye coordinates. The latter has 10 coefficients and tests whether pose features help. Pose terms are justified only when the collection contains adequate independent variation; small parameter count does not make them automatically identifiable or beneficial.

The earlier technical plan's four-raw-iris-input, two-output ridge model also had 10 coefficients. The new design explicitly introduces session calibration before a shared correction. Do not treat an old profile and this calibrated-input model as interchangeable.

## 6. Optional nonlinear models

Use the same session calibration, split, quality rules and scored samples for comparisons.

| Candidate shared correction | Architecture | Learned coefficient/parameter count |
| --- | --- | ---: |
| Linear ridge | 8 standardized inputs -> 2 residual outputs | 18 |
| Degree-2 polynomial ridge | 8 linear terms + 36 squares/cross terms -> 2 residual outputs | 90 |
| Small MLP, conditional experiment | 8 -> 32 ReLU -> 16 ReLU -> 2 linear residual outputs | 850 |

The polynomial count excludes a duplicate constant feature and includes two output intercepts: `44*2+2=90`. Fit its feature scaling within training data too.

For the MLP, dense-layer counts are `(8*32+32) + (32*16+16) + (16*2+2) = 850`. ReLU supplies nonlinear interactions. The output is linear because out-of-screen predictions must remain visible to diagnostics; clipping or a sigmoid should not hide errors. This MLP would be trained from scratch on numeric features, using regularization and session-based validation/early stopping. It is a candidate, not a claim that neural networks will perform better.

850 float32 parameters occupy 3,400 bytes before file-format and metadata overhead. Personal profiles remain on the order of kilobytes for these candidates. MediaPipe inference, capture and image processing are expected to dominate runtime cost, but the completed pipeline must still be benchmarked on the Linux laptop. No new end-to-end latency or FPS result is inferred.

## 7. Training versus calibration versus fine-tuning

| Operation | Data used | When it changes |
| --- | --- | --- |
| Pretrained landmark inference | Vendor-trained model, local images at inference | Fixed model/hash throughout this dataset |
| Session calibration | Current setup's four labeled anchor fixations only | Every new setup/calibration segment |
| Personal model training | Main labeled observations from training sessions, after their own calibration | Explicit offline fitting; selected with development data |
| Final evaluation | New sessions with permitted four-corner adaptation, followed by independent targets | No shared weights, tuning or global preprocessing updates |

No vision-network fine-tuning is planned for the first version. We fit small numeric models from scratch while reusing the pretrained visual front end. Four-corner calibration is itself a small supervised fit; it does not retrain the face detector or all personal weights.

If landmarks limit performance, a future appearance-based branch would use appropriately prepared left/right eye images, possibly face context and pose, with a pretrained gaze encoder and a screen mapping/adaptation head. Prefer a compatible pretrained gaze checkpoint over training a general vision model from one user's dataset. Its precise architecture, size, license and preprocessing remain undecided. Numeric-only collection cannot support image-model fine-tuning without recollection.

## 8. What additional data can and cannot fix

More well-distributed sessions can teach a shared correction about repeatable pose and appearance-related errors visible in its numeric inputs. More adjacent frames at the same target mostly refine estimates of the same situation.

If two different gaze positions generate indistinguishable retained features, a larger regression network cannot recover information that is absent. If glare corrupts landmark positions, low calibration fitting error cannot prove the eye was observed correctly. Diagnose failures using session-only versus corrected performance, region/condition errors, calibration failures and validity coverage before collecting more of the same data.

The collector uses displayed target coordinates as labels and does not emit pointer actions. The [action and gesture proposal](ACTION_GESTURE_DESIGN.md) adds left/right/middle held-button toggles and a separate blink-sequence recognition stream. These commands are not outputs of the gaze regression model. Initially compare personalized eyelid thresholds and a temporal state machine; collect labeled gesture and ordinary-reading negative examples separately. Gesture decoding, button lifecycle, filtering and desktop control require their own evaluation.

## 9. Gesture recognition and controller separation

SSS is reserved for middle-button toggle; detailed left/right bindings are deferred. The gaze architecture above is unchanged: two screen-coordinate outputs do not classify commands.

Gesture path: fixed landmarks -> continuous per-eye openness/validity -> personalized open/closed normalization -> hysteresis and timestamped events -> bounded S/SS/SSS/L/SL decoder -> configurable binding -> explicit held-button state. LL is exploratory. The software defines grammar and state transitions; references, thresholds, duration bands, gap and cooldown are fitted/selected from confirmed training/development traces and negative reading, then stored in a versioned profile. Test-session references may use only a predeclared, separate calibration block.

S and SS must wait until an SSS continuation is excluded. A fourth closure inside the completion window rejects the whole candidate. The same recognized sequence causes down or up according to state; six button events do not require six recognition classes.

If calibrated rules remain inadequate, compare a regularized event-feature classifier or small tree model on durations, gaps, openness dynamics and bilateral agreement, preserving abstention. Use independent continuous sessions and ground truth independent of the baseline rules. Numeric-only data can support this classifier; image-based models need separately authorized image data.

See [GESTURE_COLLECTION_TRAINING.md](GESTURE_COLLECTION_TRAINING.md) for the starting 375-sequence/45-minute budget, grouped splits and controller exercises. These counts do not establish release reliability or justify a large neural sequence model.
