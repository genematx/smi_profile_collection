"""Temporary documentation browser. Never receives the IPython user namespace."""

import asyncio
import shutil

from .catalog import CATALOG
from .render import clean, render_card
from .search import Match, Navigation, search


ACTIONS = (
    Match(":back", "Back", "navigation"),
    Match(":home", "Home", "navigation"),
    Match(":search", "Search everything", "navigation"),
    Match(":exit", "Exit to IPython", "navigation"),
)


def choices(query, context, *, global_search=False):
    results = search(query, "home" if global_search else context)
    if global_search and not query.strip():
        results = [Match(c.id, c.title, "All topics") for c in CATALOG.cards.values()]
    return results + list(ACTIONS)


def selector(context, *, global_search=False, input=None, output=None):
    """Build a fresh, inline prompt_toolkit Application (also testable with pipes)."""
    from prompt_toolkit.application import Application
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl

    buffer = Buffer(multiline=False)
    selected = 0
    keys = KeyBindings()

    def matches():
        items = choices(buffer.text, context, global_search=global_search)
        if buffer.text and len(items) == len(ACTIONS):
            items.insert(0, Match(":none", "No documented matches — broaden search or ask a scientist", "help"))
        return items

    def changed(_):
        nonlocal selected
        selected = 0

    buffer.on_text_changed += changed

    @keys.add("down")
    def down(event):
        nonlocal selected
        selected = (selected + 1) % len(matches())

    @keys.add("up")
    def up(event):
        nonlocal selected
        selected = (selected - 1) % len(matches())

    @keys.add("enter")
    def accept(event):
        target = matches()[selected].target
        if target != ":none":
            event.app.exit(result=target)

    @keys.add("tab")
    def complete(event):
        match = matches()[selected]
        if not match.target.startswith(":"):
            buffer.text = match.target
            buffer.cursor_position = len(buffer.text)

    @keys.add("escape")
    def clear(event):
        buffer.text = ""

    @keys.add("escape", "left")
    def back(event):
        event.app.exit(result=":back")

    @keys.add("c-c")
    @keys.add("c-d")
    def exit_guide(event):
        event.app.exit(result=":exit")

    def menu():
        items = matches()
        start = max(0, selected - 7)
        shown = items[start:start + 10]
        rows = []
        for i, item in enumerate(shown, start):
            # Plain markers as well as reverse video; no dependence on color.
            rows.append(("reverse" if i == selected else "", clean(
                f"{'>' if i == selected else ' '} {item.label} [{item.group}]")))
            rows.append(("", "\n"))
        rows.append(("", f"{selected + 1}/{len(items)} — type to search; arrows select; Enter opens; Tab completes"))
        return rows

    label = "all topics" if global_search else context
    layout = HSplit([
        Window(FormattedTextControl(f"guide [{label}] — Back / Home / Search everything / Exit below"), height=1),
        Window(BufferControl(buffer=buffer), height=1),
        Window(FormattedTextControl(menu)),
        Window(FormattedTextControl("Esc clears · Alt-Left back · Ctrl-C/D exit (documentation only)"), height=1),
    ])
    app = Application(layout=Layout(layout), key_bindings=keys, full_screen=False,
                      input=input, output=output, mouse_support=False)
    app.layout.focus(buffer)
    return app


def browse(start="home", *, plain=False, read=input, write=print):
    """Own only documentation navigation. A normal return always restores IPython."""
    nav = Navigation(start)
    global_search = False
    write("SMI GUIDE — STAFF PREVIEW — documentation only; no live reads or actions")
    try:
        while True:
            width = shutil.get_terminal_size((88, 24)).columns
            write(render_card(nav.current, width=width))
            write("Path: " + " > ".join(nav.history[-5:]))
            if plain:
                target = _plain_select(nav.current, global_search, read, write)
            else:
                app = selector(nav.current, global_search=global_search)
                # IPython versions/embedders differ in whether an event loop is running.
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    in_thread = False
                else:
                    in_thread = True
                from prompt_toolkit.patch_stdout import patch_stdout
                from prompt_toolkit.input.typeahead import get_typeahead
                try:
                    with patch_stdout():
                        target = app.run(in_thread=in_thread)
                finally:
                    # Discard queued guide keystrokes instead of handing them to
                    # the next documentation prompt or IPython's executable input.
                    get_typeahead(app.input)
            if target == ":exit":
                break
            if target == ":search":
                global_search = True
                continue
            global_search = False
            if target == ":back":
                nav.back()
            elif target == ":home":
                nav.home()
            else:
                nav.visit(target)
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        write("Leaving guide; no beamline actions were performed.")


def _plain_select(context, global_search, read, write):
    query, page = "", 0
    while True:
        items = choices(query, context, global_search=global_search)
        results = items[:-len(ACTIONS)]
        pages = max(1, (len(results) + 9) // 10)
        shown = results[page * 10:(page + 1) * 10]
        write(f"Choices — page {page + 1}/{pages}")
        for i, match in enumerate(shown, 1):
            write(clean(f"  {i}. {match.label} [{match.group}]"))
        if not results:
            write("No documented matches. Try another term or ask a beamline scientist.")
        write(":back :home :search :exit | :next :prev | number opens, text searches")
        answer = read("guide> ").strip()
        if answer in {action.target for action in ACTIONS}:
            return answer
        if answer in (":next", ":prev"):
            page = (page + (1 if answer == ":next" else -1)) % pages
        elif answer.isdigit():
            index = int(answer) - 1
            if 0 <= index < len(shown):
                return shown[index].target
            write("Choose a displayed number, or type a search term.")
        else:
            query, page = answer, 0
