# GUI-01 tokens and component contract

Source of truth: `app/static/css/gui-v2/tokens.css`. No CSS framework/build step.

| Family | Tokens / values |
|---|---|
| Background | app `#0c121b`; sidebar `#101822`; surface `#141e2a`; raised `#1a2635`; input `#101a26`; hover `#1d2b3b`; selected `#16332f` |
| Border | subtle `#243140`; default `#344456`; strong `#53687d` |
| Text | primary `#edf3f8`; secondary `#b3c1d0`; muted `#91a3b7`; disabled `#728296` |
| Primary | `#45d6b0` |
| Success | foreground `#62dfb5`; background `#123c30` |
| Information | foreground `#83bcff`; background `#182f4b` |
| Warning | foreground `#f0c16b`; background `#3b301c` |
| Danger | foreground `#ff9199`; background `#40252c` |
| Spacing | `--space-1/2/3/4/5/6/8/10/12` = 4/8/12/16/20/24/32/40/48px |
| Radius | `--radius-sm/md/lg` = 4/6/8px |
| Typography | `--type-page/section/card/body/secondary/label/caption/metric` = 24/18/14/14/13/12/11/26px |
| Fonts | `--font-ui`: Inter/system sans; `--font-mono`: ui-monospace/Cascadia Code/Consolas |
| Shell | sidebar 244px; collapsed 68px; top bar 58px; content max 1760px |
| Density | default controls 34px, row padding 10×12px; `[data-density="compact"]` controls 30px, rows 6×10px |

Use semantic tokens, not status colors for decoration. Old variables are aliases solely for unmigrated pages. Disabled text is not a replacement for a readable explanation. New textual errors must be associated with their field via `aria-describedby` and `aria-invalid`.

## CSS layers

1. `tokens.css`: canonical values + compatibility aliases.
2. `app.css`: legacy styles pending feature migration.
3. `base.css`: typography/focus/visibility/motion.
4. `layout.css`: shell, page-header, metric-row, toolbar, split-view.
5. `components.css`: shared surfaces/forms/tables/dialogs/status.
6. `utilities.css`: stack/cluster/semantic text/technical metrics.

Future page-specific CSS belongs after shared layers and should not redefine tokens globally.

## Components

| Component | Interface | Behavior / ownership |
|---|---|---|
| Page header | Jinja `page_header(title, description)` with caller actions | Caller provides already-authorized controls |
| Surface | `.card`, `--interactive/selected/success/warning/danger` variants | Compatibility for panel/status-card/dash-kpi |
| Metric row | `.metric-row`, `.metric-value` | Wraps compact cards; values supplied by page |
| Toolbar/split | `.toolbar`, `.toolbar-actions`, `.split-view` | Layout only |
| Badge | Jinja `badge(label,tone)` / `NetOpsUI.badge(label,tone)` | Escapes text; allowlists tone; does not calculate status |
| Buttons | `.btn-primary/secondary/danger/ghost`, `.btn-small` | Use semantic `<button type="button">`; busy via aria-busy |
| Fields | Existing native inputs/selects/textarea, `.field-label/hint/success` | Caller owns labels, errors and actual validation |
| Table | `.table-scroll`, `.data-table`, `.table-pagination` | Row selection and aria-sort styles; no invented data behavior |
| Filters | `.filter-bar`, `.filter-chip` | Caller owns supported filtering and accessible remove labels |
| Empty/error | Jinja `empty(title,description)`, `error(title,message)` | Optional caller content; no automatic Add action |
| Loading | `loading(label)`, `.spinner`, `.skeleton`, `.table-skeleton` | Use role=status/aria-busy appropriately |
| Help | Jinja `help(title)` caller content | Native details/summary; preserves explanations |
| Small dialog | `NetOpsUI.openDialog(options)` | Text/DOM content only; focus trap and safe close |
| Drawer | `NetOpsUI.openDrawer(options)` | Responsive right panel with header/body/tabs/footer |
| Chart hook | `NetOpsUI.chartOptions()` | Theme colors/font/border/motion plus palette; opt-in |

Jinja import: `{% import 'partials/gui_components.html' as ui %}`. Existing complex forms are not automatically migrated.

```javascript
const body = document.createElement('p');
body.textContent = 'Details supplied by the existing API.';
const drawer = NetOpsUI.openDrawer({
  title: 'Details', body,
  beforeClose: () => !hasUnsavedChanges // caller may return a Promise
});
// Optional footer/tabs: supply DOM nodes. A new dialog cannot replace an open one.
// drawer.close() follows the same veto. panel aria-busy=true prevents closure.
```

Tabs/steps are caller-supplied navigation, not an implemented policy wizard. Supply correct labels/keyboard behavior when a future feature implements real tabs. Do not inject untrusted HTML or duplicate IDs. Dialog titles are escaped using textContent. Legacy dialog behavior is intentionally separate to avoid changing existing dirty-form handling.

For charts, use `const {palette,...theme}=NetOpsUI.chartOptions()` and deliberately map the theme into Chart.js options (font/color are commonly plugin/scale options). `palette` is application metadata, not a Chart.js option. Do not replace backend calculations with client-derived values.
