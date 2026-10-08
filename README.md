# doex

Adaptive **design-of-experiments** desktop app for lab campaigns: import existing tables, suggest the next batch of runs, edit bounds/algorithms on the fly, inspect **2D maps** in the GUI.

> Spec (ТЗ): see [`TZ.md`](TZ.md). Status: pre-alpha scaffold.

## Install

```bash
pip install "doex @ git+https://github.com/MikhailLifar/doex.git"
```

Editable (dev):

```bash
git clone https://github.com/MikhailLifar/doex.git
cd doex
pip install -e .
```

## Run

```bash
doex
doex --version
doex doctor
```

## Layout

- `src/doex/core/` — campaign logic (no Qt)
- `src/doex/gui/` — PyQt5 UI
- `TZ.md` — full product requirements

## License

Apache-2.0
