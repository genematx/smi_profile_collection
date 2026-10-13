"""Documentation-only guide: content routes, zero live access, terminal lifecycle."""

import asyncio
import builtins
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from IPython.core.interactiveshell import InteractiveShell
from IPython.core.completer import CompletionContext
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from traitlets.config import Config

from smi_beamline.discovery.browser import browse, selector
from smi_beamline.discovery.catalog import CATALOG
from smi_beamline.discovery.ipython import load_ipython_extension, unload_ipython_extension
from smi_beamline.discovery.render import render_card
from smi_beamline.discovery.schema import Card, Catalog, Link
from smi_beamline.discovery.search import Navigation, search


def test_catalog_rejects_collisions_and_dangling_relations():
    a = Card("a", "A", "first", aliases=("alias",))
    with pytest.raises(ValueError, match="Duplicate"):
        Catalog((a, replace(a, id="b")))
    with pytest.raises(ValueError, match="Broken link"):
        Catalog((replace(a, links=(Link("missing", "Missing"),)),))
    assert CATALOG.resolve("pil2M_pos.z").id == "pil2M.motor.z"
    with pytest.raises(KeyError):
        CATALOG.resolve("pil2m")  # suggestion, never a silent exact resolution


def test_distance_has_three_routes_and_back_history_handles_cycles():
    routes = (
        ("home", "devices", "detectors", "pil2M", "pil2M.motor", "pil2M.motor.z"),
        ("home", "tasks", "pil2M.motor.z"),
        ("home", "devices", "positioning", "detector-positioning", "pil2M.motor.z"),
    )
    for route in routes:
        for parent, child in zip(route, route[1:]):
            assert child in {link.target for link in CATALOG[parent].links}
    nav = Navigation()
    for target in ("pil2M", "pil2M.motor", "pil2M"):
        nav.visit(target)
    nav.back()
    assert nav.current == "pil2M.motor"
    nav.home()
    nav.back()
    assert nav.history == ["home"]


def test_context_search_global_escape_and_case_sensitive_identity():
    assert search("pil2M.motor.z", "piezo")[0].target == "pil2M.motor.z"
    matches = search("exp", "pil2M")
    assert "command:exp" in {m.target for m in matches if m.group == "In this context"}
    assert search("runengine", "pil2M")[0].group == "Elsewhere in the guide"
    assert search("saxs distance")[0].target == "pil2M.motor.z"
    catalog = Catalog((Card("wbs", "Slits", "slits"), Card("WBS", "Camera", "camera")))
    assert search("WBS", "wbs", catalog=catalog)[0].target == "WBS"
    assert search("wbs", "WBS", catalog=catalog)[0].target == "wbs"


def test_sample_context_and_specialist_routes():
    assert [m.target for m in search("", "alignment")] == ["gi-mount", "transmission", "staff"]
    mount = search("", "gi-mount")
    assert mount[0].target == "gi-stack"
    assert all(m.target == "staff" for m in mount[1:])
    assert {m.target for m in search("", "gi-stack")} == {"alignment:piezo", "alignment:stage", "staff"}
    assert "getting close by eye" in render_card("alignment:piezo")
    assert "RE(alignment_gisaxs(angle=0.15))" in render_card("alignment:piezo")
    assert "RE(alignement_gisaxs_hex(angle=0.1))" in render_card("alignment:stage")
    assert "half-width" in render_card("alignment:stage")
    assert "pf" in render_card("transmission")
    assert "%syrscan SPAN POINTS" in render_card("transmission:stage")
    assert CATALOG.resolve("ps").id == "pf"
    assert "still use ps internally" in render_card("pf", width=200)


def test_effects_and_execution_context_are_not_lost():
    text = render_card("command:exp", width=200)
    assert "both pil2M and pil900KW" in text
    assert "int(2 / 0.5) = 4" in text
    assert "Standalone IPython magic" in text
    assert "does not automatically move" in render_card("transmission:piezo", width=200)
    assert "sample-detector distance" in render_card("pil2M.motor.z")


def test_import_and_all_static_routes_block_live_dependencies():
    # Fresh process avoids the repository's autouse ophyd fixtures masking imports.
    code = '''
import sys
class BlockLive:
    def find_spec(self, fullname, *args):
        if (fullname.split('.')[0] in {'ophyd', 'bluesky', 'redis', 'tiled', 'smi_plans'}
            or fullname.startswith(('smi_beamline.devices', 'smi_beamline.instances',
                                    'smi_beamline.plans', 'startup'))):
            raise AssertionError('Live dependency: ' + fullname)
sys.meta_path.insert(0, BlockLive())
from smi_beamline.discovery.catalog import CATALOG
from smi_beamline.discovery.search import search
from smi_beamline.discovery.render import render_card
for identifier in CATALOG.cards:
    render_card(identifier, detail=True)
    search('exposure', identifier)
'''
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


class Untouchable:
    def __getattribute__(self, name):
        raise AssertionError(f"Touched a live object: {name}")

    def __call__(self, *args, **kwargs):
        raise AssertionError("Called a live object")

    def __repr__(self):
        raise AssertionError("Rendered a live object")


@pytest.fixture
def shell():
    shell = InteractiveShell(user_ns={}, config=Config({"HistoryManager": {"hist_file": ":memory:"}}))
    shell.user_ns.update({name: Untouchable() for name in ("RE", "pil2M", "stage", "mdsave", "pf")})
    load_ipython_extension(shell)
    yield shell
    unload_ipython_extension(shell)
    shell.history_manager.end_session()


@pytest.mark.parametrize("line", [
    "%guide", "%guide --plain", "%guide show pil2M", "%guide show pil2M.motor.z --detail",
    "%guide find saxs distance", "%guide align", "%guide learn runengine", "%guide show exp",
    "%guide show nonsense --help", "%guide show {RE()}", "%guide find $pil2M",
])
def test_ipython_static_lookups_never_touch_namespace(shell, line):
    assert shell.run_cell(line).success


def test_unknown_queries_and_invalid_paging(shell, capsys):
    assert shell.run_cell("%guide show pil2m").success
    text = capsys.readouterr().out
    assert "No exact documented entry" in text
    assert "%guide show pil2M" in text
    assert not shell.run_cell("%guide find detector --page 0").success
    assert not shell.run_cell("%guide show pil2M; RE(shclose())").success


def test_reload_unload_restore_magic_completion_and_names(shell):
    original_help = builtins.help
    shell.user_ns["guide"] = "user's variable"
    unload_ipython_extension(shell)
    old = lambda line: None
    shell.register_magic_function(old, magic_kind="line", magic_name="guide")
    before = len(shell.Completer.custom_matchers)
    load_ipython_extension(shell)
    load_ipython_extension(shell)
    assert len(shell.Completer.custom_matchers) == before + 1
    matcher = shell.Completer.custom_matchers[-1]
    context = CompletionContext(token="pil", full_text="%guide show pil", cursor_position=15,
                                cursor_line=0, limit=None)
    assert "pil2M" in [c.text for c in matcher(context)["completions"]]
    assert matcher(replace(context, full_text="other pil"))["completions"] == []
    unload_ipython_extension(shell)
    assert shell.magics_manager.magics["line"]["guide"] is old
    assert len(shell.Completer.custom_matchers) == before
    assert shell.user_ns["guide"] == "user's variable"
    assert builtins.help is original_help


def test_actual_completion_replaces_only_path_fragment(shell):
    for line, expected in (("%guide show pil2M.mo", "%guide show pil2M.motor"),
                           ("%guide show command:ex", "%guide show command:exp")):
        token, matches = shell.complete(text=None, line=line, cursor_pos=len(line))
        replaced = [line[:-len(token)] + value for value in matches]
        assert expected in replaced
        assert all("pil2M.pil2M" not in value and "command:command:" not in value
                   for value in replaced)


def test_worker_registration_refused(shell):
    shell.user_ns["IS_QS_WORKER"] = True
    with pytest.raises(Exception, match="QueueServer"):
        load_ipython_extension(shell)


def test_dumb_terminal_uses_numbered_fallback(shell, monkeypatch):
    from smi_beamline.discovery import browser, ipython

    calls = []
    monkeypatch.setattr(ipython, "terminal_available", lambda _: True)
    monkeypatch.setattr(browser, "browse", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setenv("TERM", "dumb")
    assert shell.run_cell("%guide").success
    assert calls == [{"plain": True}]


def test_plain_navigation_search_and_interrupt():
    responses = iter(("saxs distance", "1", ":back", ":search", "generator", "1", ":exit"))
    output = []
    browse(plain=True, read=lambda _: next(responses), write=output.append)
    transcript = "\n".join(output)
    assert "Direct lookup: %guide show pil2M.motor.z" in transcript
    assert "Direct lookup: %guide show runengine" in transcript
    assert "Leaving guide" in transcript
    def interrupted(_):
        raise KeyboardInterrupt
    browse(plain=True, read=interrupted, write=output.append)
    assert "Leaving guide" in output[-1]


@pytest.mark.parametrize("keys,expected", [
    ("pil2M\r", "pil2M"),
    ("pil2M\t\r", "pil2M"),
    ("\x1b[B\r", "alignment"),
    ("\x04", ":exit"),
    ("\x03", ":exit"),
    ("\x1b\x1b[D", ":back"),
    ("no-such-entry\r\x04", ":exit"),
])
def test_real_prompt_key_handling(keys, expected):
    async def exercise():
        with create_pipe_input() as pipe:
            app = selector("home", input=pipe, output=DummyOutput())
            pipe.send_text(keys)
            return await asyncio.wait_for(app.run_async(), timeout=3)
    assert asyncio.run(exercise()) == expected


def test_actual_terminal_ipython_handoff(tmp_path):
    import pexpect

    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"),
               PROMPT_TOOLKIT_NO_CPR="1", NO_COLOR="1")
    child = pexpect.spawn(sys.executable, [
        "-m", "IPython", "--quick", "--no-banner", "--colors=NoColor",
        f"--profile-dir={tmp_path}", "--HistoryManager.hist_file=:memory:",
        "--TerminalInteractiveShell.confirm_exit=False",
    ], env=env, encoding="utf-8", timeout=15, dimensions=(40, 110))
    try:
        child.expect(r"In \[1\]:")
        child.sendline("%load_ext smi_beamline.discovery.ipython")
        child.expect(r"In \[2\]:")
        child.sendline("%guide")
        child.expect("guide \\[home\\]")
        child.send("pil2M\r")
        child.expect("Direct lookup: %guide show pil2M")
        child.expect("guide \\[pil2M\\]")
        # Resize while the guide owns the prompt, then return to normal Python.
        child.setwinsize(35, 85)
        child.sendcontrol("d")
        child.expect("Leaving guide")
        child.expect(r"In \[3\]:")
        child.sendline("print('GUIDE_RETURN_OK')")
        child.expect("GUIDE_RETURN_OK")
        child.expect(r"In \[4\]:")
        child.sendline("%unload_ext smi_beamline.discovery.ipython")
        child.expect(r"In \[5\]:")
        child.sendline("exit()")
        child.expect(pexpect.EOF)
    finally:
        child.close(force=True)
