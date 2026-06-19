# IndoorNav Admin — Design System

Дизайн-система панели администратора (`admin.html`), вынесенная в переиспользуемый вид.

- `styles.css` — токены (`--bg/--surface/--accent/--success/--warning/--danger…`) и классы
  компонентов: `btn-*`, `badge-*`, `stat-card`, `table`, `form-input`, `modal`, `toast`,
  `floors`, `status-dot`.
- Превью-карточки (каждая с первой строкой `<!-- @dsCard group="…" -->`):
  `buttons`, `badges`, `stat-cards`, `table`, `inputs`, `modal`, `feedback`, `graph-toolbar`.
- `index.html` — общий просмотр всех карточек (открыть в браузере).

## Синхронизация с Claude Design (claude.ai/design)

Набор уже в формате, который понимает Claude Design (per-component HTML + `@dsCard` + общий `styles.css`),
поэтому автоконвертер `/design-sync` не нужен — заливается вручную через `DesignSync`.

В текущей среде это сделать нельзя: `/login` недоступен, токен сессии без design-прав.
Когда будет интерактивная сессия с `/login`:

1. `/login` под своим claude.ai-аккаунтом.
2. Создать (или выбрать) design-system проект и загрузить содержимое `docs/design/admin/`
   через `DesignSync` (`finalize_plan` → `write_files`).
