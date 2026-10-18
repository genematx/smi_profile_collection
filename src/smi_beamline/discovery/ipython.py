"""Optional IPython extension: %load_ext smi_beamline.discovery.ipython."""

import shlex
import shutil
import sys
import os

from IPython.core.error import UsageError
from IPython.core.magic import no_var_expand
from IPython.core.completer import SimpleCompletion, completion_matcher

from .catalog import CATALOG
from .render import render_card, render_matches
from .search import search


HELP = """SMI GUIDE — STAFF PREVIEW (documentation only; no hardware reads/actions)
%guide                         searchable browser in terminal IPython
%guide --plain                 numbered terminal browser
%guide show NAME [--detail]     exact card or alias (case-sensitive)
%guide find WORDS [--page N]    search all documented topics
%guide devices                 device categories
%guide commands                existing console commands
%guide align                   sample-context alignment questions
%guide learn [TOPIC]            short learning cards
%guide home                    home card without opening a browser
%guide ?                       this help
Selectors display usage; they never execute it. Outside terminal IPython,
use direct queries. Unknown/special setups: ask a beamline scientist.
"""


def terminal_available(shell):
    from IPython.terminal.interactiveshell import TerminalInteractiveShell

    return (isinstance(shell, TerminalInteractiveShell)
            and sys.stdin.isatty() and sys.stdout.isatty())


def run_guide(shell, line):
    try:
        tokens = shlex.split(line)
    except ValueError as exc:
        raise UsageError(f"{exc}\n{HELP}") from None
    if any(token in ("?", "-h", "--help") for token in tokens):
        print(HELP)
        return
    if not tokens or tokens == ["--plain"]:
        if terminal_available(shell):
            from .browser import browse
            browse(plain=bool(tokens) or os.environ.get("TERM") == "dumb",
                   color=str(shell.colors).lower() != "nocolor" and "NO_COLOR" not in os.environ)
        else:
            print(HELP)
            print(render_card("home"))
        return
    command, *args = tokens
    if command == "find":
        page = 1
        if "--page" in args:
            index = args.index("--page")
            if index != len(args) - 2:
                raise UsageError("Use %guide find WORDS --page N")
            try:
                page = int(args[-1])
            except ValueError:
                raise UsageError("Page must be an integer.") from None
            args = args[:index]
        if not args or any(arg.startswith("--") for arg in args):
            raise UsageError("Use %guide find WORDS [--page N]")
        try:
            print(render_matches(search(" ".join(args)), page=page))
        except ValueError as exc:
            raise UsageError(str(exc)) from None
        return
    detail = False
    if args and args[-1] == "--detail":
        args = args[:-1]
        detail = True
    if command in ("show", "learn") and len(args) == 1:
        name = args[0]
    elif not args and command in ("devices", "commands", "align", "learn", "home", "tasks"):
        name = command
    else:
        raise UsageError(HELP)
    try:
        card = CATALOG.resolve(name)
    except KeyError:
        print(f"No exact documented entry for {name!r}; nothing was executed.")
        print(render_matches(search(name)))
        return
    print(render_card(card.id, detail=detail, width=shutil.get_terminal_size((88, 24)).columns))


def load_ipython_extension(ipython):
    if ipython.user_ns.get("IS_QS_WORKER", False):
        raise UsageError("The guide is an interactive documentation extension, not a QueueServer plan.")
    # Restore before replacing: repeated manual loads and extension reloads are safe.
    unload_ipython_extension(ipython)
    previous = ipython.magics_manager.magics["line"].get("guide")

    @no_var_expand
    def guide(line):
        return run_guide(ipython, line)

    guide.__doc__ = HELP

    @completion_matcher(priority=100, api_version=2)
    def complete(context):
        line = context.text_until_cursor.lstrip()
        words = line.split()
        if not words or words[0] not in ("%guide", "guide"):
            return {"completions": [], "suppress": False}
        fragment = context.token
        word = "" if line.endswith(" ") else words[-1]
        if len(words) == 1 or (len(words) == 2 and not line.endswith(" ")):
            candidates = ("show", "find", "devices", "commands", "align", "learn", "home", "tasks", "--plain")
        else:
            candidates = CATALOG.names
        # IPython may split at '.' or ':'. Match the entire catalog path, but
        # replace only its final fragment so completion cannot duplicate prefixes.
        prefix_length = len(word) - len(fragment) if word.endswith(fragment) else 0
        return {"completions": [SimpleCompletion(name[prefix_length:], type="guide")
                                for name in candidates if name.startswith(word)],
                "matched_fragment": fragment, "suppress": True}

    ipython.register_magic_function(guide, magic_kind="line", magic_name="guide")
    ipython.Completer.custom_matchers.append(complete)
    ipython._smi_guide_extension = (guide, complete, previous)


def unload_ipython_extension(ipython):
    state = getattr(ipython, "_smi_guide_extension", None)
    if state is None:
        return
    guide, complete, previous = state
    matchers = ipython.Completer.custom_matchers
    if complete in matchers:
        matchers.remove(complete)
    magics = ipython.magics_manager.magics["line"]
    # Do not overwrite a replacement installed by someone else after us.
    if magics.get("guide") is guide:
        if previous is None:
            magics.pop("guide", None)
        else:
            magics["guide"] = previous
    del ipython._smi_guide_extension
