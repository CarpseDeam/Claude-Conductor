\# Code Standards



\## Hard Limits



\*\*Function Size:\*\* One clear purpose. If doing multiple things → break it up.

\- Aim for under 25 lines

\- 40+ lines doing one thing clearly? Fine.

\- Don't fragment just to hit a number



\*\*Class Size:\*\* One responsibility. Second "system" → new file.



\*\*File Size:\*\* One clear responsibility matters more than line count.

\- New files: Aim for 200-300 lines

\- Existing files: Don't refactor unless crossing ~500 or doing multiple unrelated things

\- Working code with one purpose: Leave it alone



\*\*Inheritance:\*\* Max 1 level. Prefer composition, mixins, or protocols.



\*\*Static Typing:\*\* Every variable, parameter, return. No exceptions.



\## Tool Usage



\- Use \*\*bridge MCP\*\* for all code implementation tasks

\- Don't spin up alternative approaches — bridge MCP is the workflow



\## Before Writing Code



1\. Check existing codebase for patterns — match them

2\. No pattern exists? Ask before inventing one

3\. Read function signatures first, not entire files



\## Python Standards



\- Type hints everywhere: `def fetch(url: str) -> dict\[str, Any]:`

\- `dataclasses` or `pydantic` for structured data — no naked dicts

\- Context managers (`with`) for all I/O

\- Guard clauses up top — fail fast, don't nest

\- f-strings for formatting



\## Error Handling



\- Custom exceptions over generic `Exception`

\- No bare `except:` — always specify the type

\- Let errors bubble unless you can actually handle them



\## Docstrings



\- Brief: what it does, params, returns

\- Skip for obvious one-liners



\## Logging



\- Use `logging` module, never bare `print()`

\- Format: `logging.error("ServiceName: What failed \[context]")`

\- \*\*Never log inside loops\*\* — if you must, rate limit or log summary after

\- Log state changes, not continuous state



\## Testing



\- \*\*New code:\*\* Tests required

\- \*\*Modifying existing code:\*\* Add tests for what you touch

\- \*\*Don't:\*\* Boil the ocean — build the habit, not backfill everything

\- Test file mirrors source: `src/auth.py` → `tests/test\_auth.py`

\- No mocks unless hitting external services



\## Dependencies



\- Stdlib first — don't add a library for something Python already does

\- Prefer `pathlib`, `itertools`, `collections` before reaching for third-party

\- Ask before adding new dependencies

\- Pin versions in requirements.txt



\## Preferred Libraries



\- `pathlib` over `os.path`

\- `httpx` over `requests` (async support)

\- `pydantic` for validation, `dataclasses` for simple structs



\## Concurrency



\- `asyncio` for I/O-bound tasks

\- `multiprocessing` for CPU-bound tasks

\- Avoid `threading` unless specifically needed



\## Project Structure

```

/src

&nbsp; /domain        # Business logic, no I/O

&nbsp; /services      # External integrations

&nbsp; /models        # Data structures

&nbsp; /utils         # Small, focused helpers (not junk drawers)

/tests

```



\## Don't



\- Create `utils.py` junk drawers — group by domain

\- Use `\*args, \*\*kwargs` without good reason

\- Import inside functions (except circular dep fixes)

\- Nest more than 2-3 levels deep

\- `try-except-pass` — log it or handle it

\- Mutable default arguments: `def func(arg=\[])`

\- Global state — use dependency injection



\## When Modifying Existing Code



\- Refactor toward these standards as you go

\- Bloated file? Split it as part of your change

\- Missing tests? Add tests for the code you touch



---



\## GDScript (When Applicable)



\- Static typing: `var speed: float = 10.0`

\- `@export`, `@onready` — with the @

\- `.instantiate()` not `.instance()`

\- `signal\_name.emit()` not `emit\_signal()`

\- Composition via child nodes, not inheritance

\- No `get\_node("../")` — use `@export` injection

\- Never `print()` in `\_process`

