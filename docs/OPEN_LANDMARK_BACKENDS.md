# Open 48-landmark backends for the next PILOT_001 stage

PILOT_001 has independently established the exact bytes and timing metadata for its two frozen videos. The remaining scientific bottleneck is visual measurement.

## Primary reference

The 2024 social-signal study reports that its landmark detection was performed with the Tech4Animals animal facial landmarks API. Its 48-landmark representation is grounded in CatFLW/Finka and CatFACS-related anatomy.

This is the preferred reference path when the published API can be executed reproducibly on the frozen Fast-CAT source frames.

## Open secondary implementation candidate

`hugocornellier/cat_detection` is an MIT-licensed, on-device LiteRT/TFLite implementation that advertises CatFLW-based 48-point facial landmark extraction. Its current package exposes:

- a 224x224 cat face localizer;
- a 384x384 full 48-landmark model;
- ear/eye/nose/mouth/contour landmark groups;
- Linux support.

It is useful as an **independent secondary detector candidate**, not as ground truth. Because its exact relationship to the peer-reviewed ELD/Tech4Animals model has not been established, Fast-CAT must validate it on manually reviewed frames before its output can enter the admitted event table.

## Admission strategy

For each frozen video:

1. decode exact PTS frames from the already SHA-256-bound source;
2. run the Tech4Animals/reference detector where reproducibly available;
3. run an open secondary 48-point detector where possible;
4. compare landmark geometry and stability over adjacent frames;
5. manually review candidate action onsets, especially `EAD103` and `EAD104`;
6. preserve disagreements as disagreements rather than averaging them away;
7. admit a facial-action onset only through the frozen `manual_catfacs_frame_review` or a separately validated `validated_fastcat_model` channel.

No detector may create or alter source timestamps: video PTS remains authoritative.
