# doex

Adaptive **design-of-experiments** desktop app for lab campaigns: import existing tables, suggest the next batch of runs, edit bounds/algorithms on the fly, inspect **2D maps** in the GUI.

> Spec (ТЗ): see [`TZ.md`](TZ.md).

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

## Quick start

1. **Import table…** → choose `examples/toy_campaign.csv` → confirm column roles.
2. Set **Batch size K** and the response to optimize in the left Basics column.
3. Click **Suggest next** — proposed rows appear in **Runs**.
4. Fill response values, **Mark selected done**, Suggest again.
5. Open **Maps** for scatter / model slice. Tune mode under **Advanced**.
6. **Save** / **Export** the campaign folder (`.doex` directory with `campaign.json` + `runs.csv`).

## Layout

- `src/doex/core/` — campaign logic (no Qt)
- `src/doex/gui/` — PyQt5 UI
- `src/doex/viz/` — matplotlib 2D helpers
- `TZ.md` — full product requirements

## License

Apache-2.0
