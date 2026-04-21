"""
Duration rules — documentation module.

The verb lists that drive the deterministic duration calculation are defined in
verb_categories.py (MOTION_VERBS, INTERACTION_VERBS, PERCEPTION_VERBS).

Duration logic (in pass3_shots.py):
  base = 3 seconds
  +1 second if the action contains a motion verb
  +1 second if the action contains an interaction verb
  +1 second if the action contains a perception verb
  clamped to [3, 8]
"""
