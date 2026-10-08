# ТЗ: doex — GUI для адаптивного DoE / оптимизации экспериментов

**Версия ТЗ:** 0.1  
**Дата:** 2026-10-08  
**Статус:** к реализации  
**Кодовое имя пакета:** `doex`  
**Целевые пользователи:** экспериментаторы (не программисты) в материаловедении / покрытиях (кейс РГУПС), с возможностью обобщения на другие лаб. кампании  

---

## 1. Цель и ценность

### 1.1. Проблема

Лаборатории ведут итеративные кампании «параметры синтеза → свойства», часто начиная с уже накопленных таблиц. Классический DoE (JMP, Design-Expert) плохо закрывает цикл *измерили → предложи следующие точки*. Существующие BO-GUI (BASIL, OPTIMEO, MADGUI) ближе, но:

- плохо переживают «грязные» таблицы с пропусками;
- слабо поддерживают *продолжение* исторической серии;
- не предлагают domain-aware сценарии (лит. старт → свои опыты, батч-камеры, контрастные прогоны);
- редко дают инженерные 2D-карты прямо в UI.

### 1.2. Цель продукта

Десктопное приложение **doex**: одна **кампания** = пространство факторов + отклики + история прогонов + предложение следующих экспериментов + визуализация.  
Сценарии:

1. **С нуля** — задать факторы/границы → стартовый дизайн → цикл.  
2. **Продолжение** — загрузить CSV/XLSX (как листы РГУПС) → донастроить схему → цикл.

### 1.3. Publishable edge (не «ещё один BO»)

Заложить в архитектуру (MVP — каркас, v1+ — наполнение), чтобы продукт отличался от generic BO-GUI:

| Приоритет | Фича | Зачем |
|-----------|------|--------|
| P0 (MVP каркас) | Campaign = first-class; cold start **или** continue-from-table | Базовый USP для лаб |
| P1 | Tolerant import (пропуски откликов, категории, маппинг колонок) | Реальные таблицы РГУПС |
| P1 | 2D срезы / проекции отклика и acquisition **в приложении** | Решение для инженера |
| P2 | Batch proposals (несколько точек за раз) | Один план на неделю / смену |
| P2 | Смена алгоритма и bounds **на лету** без потери кампании | Гибкость живого эксперимента |
| P3 | Literature pack → lab continuation (domain tag / вес) | Статья + РНФ/ОНК |
| P3 | Contrastive / delta proposals | Научный край (как delta-learning HEA) |
| P3 | Chamber constraints (общие процесс-параметры на батч) | Реализм PVD |

MVP **не обязан** закрыть P3, но модель данных и UI не должны их блокировать.

---

## 2. Стек и дистрибуция

| Слой | Выбор |
|------|--------|
| Язык | Python ≥ 3.10 |
| GUI | **PyQt5** (как optional GUI у autosaxs; единообразие для команды) |
| Данные | `pandas`, `numpy` |
| ML / DoE | `scikit-learn` (Ridge, ExtraTrees, …); стартовые дизайны (LHS/IHS — своя или лёгкая зависимость); позже опционально GP/BO-библиотека |
| Графика | `matplotlib` (встроенные виджеты `FigureCanvasQTAgg`); опционально `seaborn` |
| Упаковка | `src/` layout, `pyproject.toml` (setuptools), как autosaxs |
| VCS | **git** с первого коммита репозитория |

### 2.1. Установка (целевой UX)

```bash
pip install "doex @ git+https://github.com/<org>/doex.git"
# или editable:
pip install -e "/path/to/doex"
```

Запуск:

```bash
doex                 # GUI
doex --version
doex doctor          # быстрая проверка зависимостей / дисплея
```

Entry point: `[project.scripts] doex = "doex.cli:main"`.

### 2.2. Структура репозитория (обязательная)

```
doex/
├── README.md
├── TZ.md                 # это ТЗ (может позже переехать в docs/)
├── LICENSE
├── pyproject.toml
├── .gitignore
├── src/doex/
│   ├── __init__.py
│   ├── cli.py            # argparse: gui | doctor | version
│   ├── app.py            # QApplication bootstrap
│   ├── core/             # domain model, без Qt
│   │   ├── campaign.py
│   │   ├── schema.py     # Factor, Response, bounds, types
│   │   ├── table.py      # runs table I/O
│   │   ├── design.py     # initial DoE
│   │   ├── suggest.py    # next-batch algorithms
│   │   └── io.py         # import/export
│   ├── gui/              # только Qt
│   │   ├── main_window.py
│   │   ├── space_panel.py
│   │   ├── runs_panel.py
│   │   ├── next_panel.py
│   │   ├── viz_panel.py
│   │   └── widgets/      # progressive disclosure, editors
│   └── viz/
│       └── slices2d.py
├── examples/
│   └── toy_campaign.csv
└── tests/                # по запросу; не раздувать на старте
```

**Инвариант:** вся логика кампании живёт в `core/`; GUI только отображает и вызывает API. Один владелец состояния кампании — объект `Campaign` (или `CampaignStore`).

---

## 3. Модель данных

### 3.1. Campaign

- `id`, `name`, `created_at`, `updated_at`
- `schema`: факторы + отклики
- `runs`: таблица наблюдений
- `settings`: алгоритм, batch size, seed, advanced…
- `history`: журнал предложений / смен настроек (для воспроизводимости)
- опционально `source_tags` на строках: `experiment` | `literature` | `proposed`

Персистентность кампании: одна папка или один файл:

- **v0:** `.doex.json` + `runs.csv` рядом  
- **v1:** один `.doex.zip` / `.doex` (json + csv) для удобного шаринга  

### 3.2. Factor

- `name`, `type`: `continuous` | `integer` | `categorical` | `fixed`
- `bounds` / `levels`
- `unit` (опционально)
- `role`: `free` | `shared_batch` (задел под chamber constraints)

### 3.3. Response

- `name`, `goal`: `maximize` | `minimize` | `target` | `observe` (не оптимизировать, только моделировать)
- `bounds` желательности (опционально)
- допускаются **пропуски** в истории

### 3.4. Run row

- значения факторов  
- значения откликов (nullable)  
- `status`: `done` | `proposed` | `queued` | `rejected`  
- `sample_id` (авто или ручной, стиль `P.YYMMDD…`)  
- `note`, `source_tag`

---

## 4. Функциональные требования

### 4.1. Кампания: создать / открыть / продолжить

| ID | Требование | Приоритет |
|----|------------|-----------|
| F1 | Создать пустую кампанию: имя → редактор схемы | P0 |
| F2 | Импорт таблицы CSV/XLSX → мастер маппинга колонок → факторы/отклики | P0 |
| F3 | Продолжение: открыть сохранённую кампанию или дописать строки в текущую | P0 |
| F4 | Валидация схемы при импорте (типы, пустые имена, дубликаты) с понятными сообщениями | P0 |
| F5 | Экспорт: `runs.csv`, схема JSON, весь пакет кампании | P0 |
| F6 | Шаблоны импорта «как РГУПС» (опциональные пресеты имён колонок) | P2 |

### 4.2. Схема и кастомизация (в т.ч. на лету)

| ID | Требование | Приоритет |
|----|------------|-----------|
| F10 | Добавление/удаление/переименование факторов и откликов до и **во время** кампании | P0 |
| F11 | Изменение bounds / levels на лету; предложения после смены пересчитываются | P0 |
| F12 | Смена алгоритма предложения на лету без потери `done`-строк | P0 |
| F13 | Фиксация «замороженных» факторов (`fixed`) | P1 |
| F14 | Предупреждение, если смена схемы ломает интерпретацию старых строк (не молчаливый break) | P1 |

### 4.3. Цикл «генерация → эксперимент»

| ID | Требование | Приоритет |
|----|------------|-----------|
| F20 | Стартовый дизайн при пустой/`мало` истории: LHS/IHS (или Sobol), размер батча N | P0 |
| F21 | Предложить следующий батч из K точек при наличии измерений | P0 |
| F22 | Алгоритмы MVP: (a) space-filling / random-feasible; (b) ExtraTrees + uncertainty/exploit heuristic; (c) Ridge baseline | P0 |
| F23 | Алгоритмы позже: GP+EI/qEI, multi-objective desirability / Pareto | P2 |
| F24 | Пользователь вносит результаты в `proposed` → статус `done` → снова Suggest | P0 |
| F25 | Отклонить предложение / частично принять батч | P1 |
| F26 | Пояснение «почему эта точка» (explore / exploit / fill gap) — короткий текст | P1 |

### 4.4. Визуализация

| ID | Требование | Приоритет |
|----|------------|-----------|
| F30 | 2D scatter: два фактора vs цвет = отклик или status | P0 |
| F31 | 2D срез модели / acquisition: выбор пары осей, остальные факторы — слайдеры «заморозки» | P0 |
| F32 | Параллельный просмотр: таблица Runs ↔ подсветка точки на графике | P1 |
| F33 | Pareto preview для 2 откликов (если оба optimize) | P2 |
| F34 | Экспорт текущей фигуры PNG | P1 |

### 4.5. Нефункциональные

| ID | Требование |
|----|------------|
| N1 | Старт GUI ≤ 3 с на типичном ноутбуке (после импорта deps) |
| N2 | Кампания до ~5k строк / ≤30 факторов без деградации UI (виртуализация таблицы при необходимости) |
| N3 | Работа offline |
| N4 | Ошибки — диалоги на человеческом языке, traceback в лог/Details |
| N5 | `core` покрыт минимальными unit-тестами на I/O и suggest (по запросу; не блокировать UI-MVP) |

---

## 5. UX / UI — progressive disclosure

### 5.1. Принцип

> **При открытии видны только базовые вещи.**  
> Всё техническое — за «Advanced…» / вкладкой / раскрывающейся секцией (1–2 клика).

### 5.2. Первый экран (после splash/home)

**Home:**

- [ Новая кампания ]  
- [ Продолжить из файла… ]  
- [ Импорт таблицы… ]  
- список недавних кампаний  

**Главное окно кампании — три зоны (одна композиция, не «дашборд из карточек»):**

1. **Слева (всегда узкая колонка): Basics**  
   - Имя кампании  
   - Число done / proposed  
   - Batch size K  
   - Цель: какой отклик optimize (простой combo)  
   - Кнопка **Suggest next**  
   - Кнопки Import / Export  

2. **Центр: вкладки**  
   - **Runs** — таблица (главный рабочий объект)  
   - **Space** — факторы и bounds (базовый список; типы/fixed — advanced)  
   - **Maps** — 2D визуализация  

3. **Справа или bottom drawer: Advanced (свёрнуто по умолчанию)**  
   - Алгоритм + гиперпараметры  
   - Seed, acquisition / explore–exploit mix  
   - Multi-objective веса  
   - Constraints  
   - Domain tags (literature weight)  
   - Лог / история предложений  

### 5.3. Правила интерфейса

- Не показывать названия вроде `qLogEI`, `n_estimators` на первом уровне — только «Режим: быстрый / точный / исследование пространства».  
- Смена advanced-параметров **не** требует пересоздания кампании.  
- Destructive actions (удалить фактор с данными) — confirm.  
- Клавиатура: Del на proposed, Ctrl+S сохранить, Ctrl+Enter = Suggest (желательно).

### 5.4. Визуальный тон

Плоский, спокойный UI (Qt fusion / лёгкая кастомная палитра). Без «AI-slop»: без градиентных баннеров и эмодзи. Акцент на таблице и картах.

---

## 6. API ядра (контракт GUI ↔ core)

Псевдокод контракта (реализация может отличаться, семантика — нет):

```python
campaign = Campaign.create(name)
campaign = Campaign.load(path)
campaign.import_table(df, mapping: ColumnMapping)
campaign.set_factor(...); campaign.set_response(...)
campaign.update_settings(SuggestSettings(...))  # на лету

batch = campaign.suggest(k=5)           # -> list[Run] status=proposed
campaign.accept_proposal(run_id)
campaign.record_results(run_id, values)
campaign.reject_proposal(run_id)

grid = campaign.slice_2d(x, y, response_or="acquisition", frozen={...})
campaign.export(path)                   # csv / doex package
```

GUI **не** вызывает sklearn напрямую.

---

## 7. Алгоритмы MVP (детализация)

### 7.1. Initial design

- Independent sampling / LHS в Continuous+Integer; полный или сэмплированный перебор по categorical.  
- Уважение bounds и fixed.

### 7.2. Suggest (при n_done ≥ n_min, иначе initial)

Минимально рабочая схема (документировать в UI как «Модель: деревья»):

1. Обучить ExtraTrees (или Ridge) на `done` для активного отклика.  
2. Сэмплировать кандидатов в可行мой области.  
3. Ранжировать по score = exploit + λ · explore  
   - exploit: предсказанное значение с учётом maximize/minimize  
   - explore: std по деревьям или расстояние до ближайших done в нормированном пространстве  
4. Вернуть top-K с diversity (жадно по минимальному расстоянию).

λ и K — в Basics (K) и Advanced (λ / пресет режима).

### 7.3. Смена алгоритма на лету

`SuggestSettings.algorithm ∈ {lhs, trees, ridge, ...}` хранится в кампании; следующий `suggest()` использует новые настройки. История done не пересчитывается задним числом.

---

## 8. Импорт / экспорт

| Формат | Назначение |
|--------|------------|
| CSV | runs и быстрый обмен |
| XLSX | импорт «как из РГУПС» (первый лист / выбор листа) |
| JSON | schema + settings |
| `.doex` dir/zip | полный снимок кампании |
| PNG | текущая 2D карта |

Импорт: мастер из 2 шагов — (1) превью таблицы (2) маппинг колонок → Factor/Response/Ignore/Sample ID.

---

## 9. Этапы реализации

### Этап 0 — каркас пакета (1–2 дня)

- git repo, `pyproject.toml`, `doex` CLI → пустое окно Qt  
- `Campaign` skeleton + save/load json+csv  
- README: install from git  

### Этап 1 — MVP usable (основной)

- Import CSV + mapping  
- Space basics + Advanced drawer  
- Runs table edit  
- LHS start + trees suggest  
- Maps: scatter + model slice 2D  
- Export  

### Этап 2 — lab-ready

- XLSX, sample_id helpers  
- Propose explainers, reject/partial accept  
- Linked brush table↔plot  
- Presets режимов (explore / balanced / exploit)  
- `doex doctor`  

### Этап 3 — publishable differentiators

- Literature vs experiment tags + weighted fit  
- Contrastive proposals  
- Batch shared-factor constraints  
- Multi-objective Pareto + desirability  
- Опциональный GP backend  

---

## 10. Критерии приёмки MVP

1. `pip install -e .` и `doex` открывают GUI.  
2. Импорт `examples/toy_campaign.csv` → видны runs.  
3. Suggest даёт K proposed строк; после заполнения откликов повторный Suggest работает.  
4. Смена bounds и алгоритма в Advanced без перезапуска приложения влияет на следующий Suggest.  
5. Вкладка Maps показывает scatter и 2D срез.  
6. Export/Import кампании восстанавливает состояние.  
7. Пользователь без чтения кода проходит сценарий «импорт → suggest → ввод результатов → карта» за ≤15 минут (smoke с коллегой-экспериментатором).

---

## 11. Вне скоупа MVP (явно)

- Закрытый loop с железом / LIMS  
- Полноценный ELN  
- Авторазбор произвольных «кринжовых» Excel РГУПС без маппинга  
- LLM-агент внутри GUI  
- Платные лицензии / телеметрия  

---

## 12. Риски и решения

| Риск | Митигация |
|------|-----------|
| PyQt сложность UI | Тонкий GUI, толстый `core`; начинать с 3 вкладок |
| «Ещё один BO» без новизны | Не обещать GP-зоопарк; заложить P3 differentiators в модель данных |
| Грязные таблицы | Мастер маппинга + nullable responses с первого дня |
| Перегруз UI настройками | Progressive disclosure как жёсткое правило ревью |

---

## 13. Открытые решения (зафиксировать до конца этапа 1)

1. Имя репозитория / GitHub org (`doex` свободно? иначе `labdoex` / `campaigndoe`).  
2. PyQt5 vs PyQt6 — **по умолчанию PyQt5** (паритет с autosaxs); смена только если мешает.  
3. Формат файла кампании: directory vs zip — выбрать к концу этапа 1.  
4. Язык UI v1: EN / RU / оба (строки через один dict).  

---

## 14. Ссылки на контекст

- Анализ поля GUI DoE / BO и пробелов под РГУПС (чат 2026-09/10).  
- Кейсы данных: `RGUPS/Таблица сводных данных_TiN.xlsx`, HEA/DLC отчёты.  
- Паттерн упаковки: autosaxs (`pyproject.toml`, `pip install … @ git+…`, entry points).
