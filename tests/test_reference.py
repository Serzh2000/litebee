"""The function reference cannot drift from the code: methods, signatures, statuses, examples."""
import inspect

import pytest

from litebee import reference as ref
from litebee.mission import CMD_NAMES, PROVEN_CMDS
from litebee.safety import check_show
from litebee.show import Drone, Show, UploadUnsupported, drone_to_mission


def public_members(cls):
    return {n for n, v in vars(cls).items() if not n.startswith("_") and (callable(v) or isinstance(v, property))}


def entries_of(owner):
    return {e.name: e for e in ref.ENTRIES if e.owner == owner}


def test_every_public_method_has_an_entry():
    assert public_members(Drone) <= set(entries_of("Drone"))
    assert public_members(Show) <= set(entries_of("Show"))
    assert "Show" in entries_of("Show")                       # the constructor


def test_every_entry_names_a_real_member():
    for e in ref.ENTRIES:
        cls = {"Show": Show, "Drone": Drone}[e.owner]
        if e.kind == "class":
            assert e.name == e.owner
        elif e.kind == "property":
            assert isinstance(getattr(cls, e.name, None), property), e.key
        else:
            assert callable(getattr(cls, e.name, None)), e.key
    assert len({e.key for e in ref.ENTRIES}) == len(ref.ENTRIES)


def _real_signature(e):
    cls = {"Show": Show, "Drone": Drone}[e.owner]
    if e.kind == "property":
        return e.name, []
    fn = cls.__init__ if e.kind == "class" else getattr(cls, e.name)
    params = [p for p in inspect.signature(fn).parameters.values() if p.name != "self"]
    sig = inspect.Signature(params)
    return e.name + str(sig), [p.name for p in params]


@pytest.mark.parametrize("e", ref.ENTRIES, ids=lambda e: e.key)
def test_signature_and_params_match_the_code(e):
    signature, names = _real_signature(e)
    assert e.signature == signature
    if e.kind != "property":
        assert [p.name for p in e.params] == names
        assert all(p.unit and p.text for p in e.params)


@pytest.mark.parametrize("e", ref.ENTRIES, ids=lambda e: e.key)
def test_entry_is_complete(e):
    assert e.summary and e.summary[0].isupper() and not e.summary.endswith(".")
    assert e.example.strip() and e.topic in ref.TOPIC_TITLE
    assert e.status in (ref.STATUS_VERIFIED, ref.STATUS_SIM, ref.STATUS_HELPER)
    assert e.context in ("drone", "show", "full")


def test_status_matches_proven_commands():
    for e in ref.ENTRIES:
        if e.command is None:
            assert e.status == ref.STATUS_HELPER, e.key
            continue
        assert e.command in ref.CMD_ID_BY_NAME, e.key
        proven = e.cmd_id in PROVEN_CMDS
        assert e.status == (ref.STATUS_VERIFIED if proven else ref.STATUS_SIM), e.key
    for cid, name, funcs, status in ref.COMMANDS:
        if cid in CMD_NAMES:
            assert name.lower() == CMD_NAMES[cid].lower()
        if funcs:
            assert status == (ref.STATUS_VERIFIED if cid in PROVEN_CMDS else ref.STATUS_SIM)
            assert {ref.entries_dict()[("Drone", f)].command for f in funcs} == {name}
        else:
            assert status == ref.STATUS_ABSENT and cid not in PROVEN_CMDS
    assert {cid for cid, *_ in ref.COMMANDS} >= PROVEN_CMDS


def _program(e):
    pre = {"drone": "from litebee import Show\nshow = Show('t')\nd = show.drone(1)\n",
           "show": "from litebee import Show\nshow = Show('t')\n",
           "full": ""}[e.context]
    return pre + e.example


@pytest.mark.parametrize("e", ref.items(), ids=lambda e: e.key)
def test_examples_run_and_pass_the_checks(e):
    if not e.example:
        return
    ns = {}
    exec(compile(_program(e), e.key, "exec"), ns)
    show = ns["show"]
    errors = [f for f in check_show(show) if f.level == "error"]
    assert not errors, errors


@pytest.mark.parametrize("e", [e for e in ref.ENTRIES if e.command], ids=lambda e: e.key)
def test_status_agrees_with_the_uploader(e):
    """'проверено на дроне' really uploads, 'только симулятор' really refuses."""
    if e.name == "circle":
        pytest.skip("circle was flown from the desktop app; the Python uploader of this older app does not pack it")
    ns = {}
    exec(compile(_program(e), e.key, "exec"), ns)
    drone = ns["show"].drones[1]
    if e.status == ref.STATUS_VERIFIED:
        assert drone_to_mission(drone).steps
    else:
        with pytest.raises(UploadUnsupported):
            drone_to_mission(drone)


def test_articles_cover_the_required_topics():
    titles = {a.title for a in ref.ARTICLES}
    assert {"Коврик и координаты", "Безопасность", "Рабочая последовательность"} <= titles
    text = " ".join(" ".join(map(str, s.lines)) for a in ref.ARTICLES for s in a.sections)
    for needle in ("столбец + 12 × строка", "40 см", "x = y = 0", "50 см", "150", "200", "7,0", "100 см/с",
                   "±10-15 см", "~20 см", "Esc"):
        assert needle in text, needle
    for a in ref.ARTICLES:
        assert a.topic in ref.TOPIC_TITLE and a.summary and a.sections


def test_get_find_search():
    assert ref.get("Drone.takeoff").name == "takeoff"
    assert ref.get("mat").title == "Коврик и координаты"
    assert ref.get("nope") is None
    assert [e.key for e in ref.find("takeoff")] == ["Drone.takeoff"]
    assert [e.key for e in ref.find("duration")] == ["Show.duration", "Drone.duration"]
    assert {e.name for e in ref.drone_commands()} == {
        "calibrate", "takeoff", "land", "land_on", "set_z", "code", "code_s", "code_z", "circle", "circle_z", "rgb", "rgb_value"}
    assert ref.search("") == ref.items()
    assert ref.get("Drone.takeoff") in ref.search("ВЗЛЁТ")
    assert ref.get("Drone.takeoff") in ref.search("взлет")                 # ё and е are the same
    assert ref.get("Drone.code") in ref.search("moveXY")                    # formation command name
    assert ref.search("zzzz-no-such-thing") == []
    assert [e.key for e in ref.search("rgb") if not e.article][:2] == ["Drone.rgb", "Drone.rgb_value"]


def test_hint_html_mentions_signature_and_status():
    html = ref.hint_html(ref.get("Drone.takeoff"), {"text2": "#8B97A8"})
    assert "takeoff(z, seconds)" in html and ref.STATUS_VERIFIED in html and "см" in html
