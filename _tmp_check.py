from aiprod_adaptation.core.pass2_visual import visual_rewrite

tests = [
    ("Emma felt nervous in the corridor. She thought about the future. Emma walked to the door.",
     ["Emma"]),
    ("She was terrified of the darkness.", ["Emma"]),
    ('"I found the passage," Clara said quietly, tracing a line with her finger.', ["Clara"]),
    ('"We go forward," Marcus said.', ["Marcus"]),
    ('"The captain waited," she said.', []),
    ("Emma walked quickly to the door.", ["Emma"]),
]

for raw, chars in tests:
    scene = {"scene_id": "S01", "characters": chars, "location": "room",
             "time_of_day": None, "raw_text": raw}
    r = visual_rewrite([scene])[0]
    print("VA:", r["visual_actions"])
    aus = r.get("action_units", [])
    if aus:
        au = aus[0]
        print(f"  AU[0]: subject_id={au['subject_id']} action_type={au['action_type']} target={au.get('target')}")
    print()
