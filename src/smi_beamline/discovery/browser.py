"""Temporary documentation browser. Never receives the IPython user namespace."""

import asyncio
import os
import shutil

from .catalog import CATALOG
from .render import clean, render_card
from .search import Match, Navigation, search
from .presentation import COLORS, legend, menu_row


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


def selector(context, *, global_search=False, input=None, output=None, navigation=None, color=True):
    """Build an alternate-screen browser; navigation stays inside one Application.

    Without navigation, return a single selection (useful for isolated UI tests).
    """
    from prompt_toolkit.application import Application
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
    from prompt_toolkit.widgets import TextArea
    from prompt_toolkit.lexers import Lexer
    from prompt_toolkit.styles import Style

    color = color and "NO_COLOR" not in os.environ

    class CardLexer(Lexer):
        def lex_document(self, document):
            def line(index):
                text = document.lines[index]
                category = ""
                if index == 0:
                    category = "title"
                elif text.endswith(":") and not text.startswith(" "):
                    category = "heading"
                elif text.lstrip().startswith(("%", "RE(", "pf?")):
                    category = "example"
                return [("class:" + category if category else "", text)]
            return line

    buffer = Buffer(multiline=False)
    selected = 0
    keys = KeyBindings()
    card = TextArea(read_only=True, focusable=False, scrollbar=True, wrap_lines=True, lexer=CardLexer())
    notice = ""

    def update_card():
        width = output.get_size().columns if output is not None else shutil.get_terminal_size((88, 24)).columns
        card.text = render_card(context, width=max(24, width - 2), include_links=False)
        card.buffer.cursor_position = 0

    update_card()

    def choose(event, target):
        nonlocal context, global_search
        if target == ":none":
            return
        if navigation is None or target == ":exit":
            event.app.exit(result=target)
            return
        if target == ":search":
            global_search = True
        else:
            global_search = False
            if target == ":back":
                navigation.back()
            elif target == ":home":
                navigation.home()
            else:
                navigation.visit(target)
            context = navigation.current
        buffer.text = ""
        changed(buffer)
        update_card()

    def query_and_number():
        text = buffer.text.strip()
        if text.isdecimal():
            return "", int(text)
        query, sep, number = text.rpartition(" ")
        if sep and number.isdecimal():
            return query, int(number)
        return text, None

    def matches():
        query, _ = query_and_number()
        items = choices(query, context, global_search=global_search)
        if query and len(items) == len(ACTIONS):
            items.insert(0, Match(":none", "No documented matches — broaden search or ask a scientist", "help"))
        return items

    def changed(_):
        nonlocal selected, notice
        _, number = query_and_number()
        selected = number - 1 if number is not None and 1 <= number <= len(matches()) else 0
        notice = ""

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
        nonlocal notice
        _, number = query_and_number()
        if number is not None:
            if not 1 <= number <= len(matches()):
                notice = f"Choose a number from 1 to {len(matches())}; nothing opened."
                return
            choose(event, matches()[number - 1].target)
            return
        choose(event, matches()[selected].target)

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
        choose(event, ":back")

    @keys.add("pageup")
    @keys.add("pagedown")
    def scroll_card(event):
        direction = -1 if event.key_sequence[0].key == "pageup" else 1
        row = card.buffer.document.cursor_position_row
        height = card.window.render_info.window_height if card.window.render_info else 8
        row = max(0, min(card.buffer.document.line_count - 1, row + direction * max(1, height - 2)))
        card.buffer.cursor_position = card.buffer.document.translate_row_col_to_index(row, 0)

    @keys.add("c-c")
    @keys.add("c-d")
    def exit_guide(event):
        event.app.exit(result=":exit")

    def menu():
        items = matches()
        height = app.output.get_size().rows
        count = max(3, min(10, height // 3))
        start = max(0, selected - count + 1)
        shown = items[start:start + count]
        rows = []
        for i, item in enumerate(shown, start):
            rows.extend(menu_row(item, i, i == selected, context, color=color))
        rows.append(("class:help" if notice else "", notice or
                     f"{selected + 1}/{len(items)} — number + Enter opens; text searches; e.g. exp 2 opens result 2"))
        return rows

    def heading():
        label = "all topics" if global_search else context
        return f"guide [{label}] — Back / Home / Search everything / Exit below"

    def breadcrumb():
        return "Path: " + " > ".join(navigation.history[-5:] if navigation else [context])

    layout = HSplit([
        Window(FormattedTextControl("SMI GUIDE — STAFF PREVIEW — documentation only"), height=1, style="class:title"),
        Window(FormattedTextControl(breadcrumb), height=1, style="class:breadcrumb"),
        card,
        Window(FormattedTextControl(heading), height=1, style="class:heading"),
        Window(BufferControl(buffer=buffer), height=1),
        Window(FormattedTextControl(menu), height=lambda: max(3, min(10, app.output.get_size().rows // 3)) + 1),
        Window(FormattedTextControl(lambda: legend(color)), height=1),
        Window(FormattedTextControl("PgUp/Dn scroll card · Esc clears · Alt-Left back · Ctrl-C/D exit"), height=1),
    ])
    app = Application(layout=Layout(layout), key_bindings=keys, full_screen=True,
                      input=input, output=output, mouse_support=False,
                      style=Style.from_dict(COLORS if color else {}), include_default_pygments_style=False)
    app.layout.focus(buffer)
    return app


def browse(start="home", *, plain=False, read=input, write=print, color=True):
    """Own only documentation navigation. A normal return always restores IPython."""
    nav = Navigation(start)
    global_search = False
    try:
        if not plain:
            app = selector(start, navigation=nav, color=color)
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
                    app.run(in_thread=in_thread)
            finally:
                # Do not hand queued guide keystrokes to IPython's executable input.
                get_typeahead(app.input)
            return
        write("SMI GUIDE — STAFF PREVIEW — documentation only; no live reads or actions")
        while True:
            width = shutil.get_terminal_size((88, 24)).columns
            write(render_card(nav.current, width=width, include_links=False))
            write("Path: " + " > ".join(nav.history[-5:]))
            target = _plain_select(nav.current, global_search, read, write)
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
        last = CATALOG[nav.current]
        write("Guide closed — " + clean(" > ".join(nav.history)))
        write(clean(last.title + ": " + last.summary))
        write(f"Reopen this entry: %guide show {last.id}")


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
