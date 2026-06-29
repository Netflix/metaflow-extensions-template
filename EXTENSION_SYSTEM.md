# The Metaflow Extension System

This document explains how Metaflow's extension mechanism works. The mechanism
lets a third party extend Metaflow — adding decorators, plugins, CLI commands,
config, top-level symbols, etc. — by shipping a Python package named
`metaflow_extensions`, **without** forking or patching Metaflow core.

This template allows you to extend Metaflow and this document is an explanation of what happens
when you write an extension.

Everything described here lives under `metaflow/metaflow/extension_support/`:

| File | Responsibility |
| --- | --- |
| `__init__.py` | The engine: package discovery, the import machinery (`MetaPathFinder`/`Loader`), aliasing, packaging. ~1264 lines. |
| `plugins.py` | The `plugins` extension point: decorators, datastores, sidecars, CLIs, etc. |
| `cmd.py` | The `cmd` extension point: top-level CLI commands (`metaflow <cmd>`). |
| `integrations.py` | The `alias` extension point: integration aliases exposed in `metaflow.integrations`. |
| `_empty_file.py` | A deliberately empty file used as a synthetic `__init__.py` when re-packaging. |

---

## 1. The big picture

An extension is a regular Python distribution (installed via `pip`/`conda`, or
just present on `PYTHONPATH`) that contributes a package called
`metaflow_extensions`. The constant driving everything is:

```python
EXT_PKG = "metaflow_extensions"     # extension_support/__init__.py:82
```

The system runs in **three phases**, mirrored in the module's own header comment:

1. **Package discovery** — find every distribution / path that provides a
   `metaflow_extensions` package and figure out, per *extension point*, which
   packages contribute and in what order. This is `_get_extension_packages()`.
2. **Integration** — at fixed *extension points* scattered through Metaflow
   core (`metaflow/__init__.py`, `plugins/__init__.py`, `metaflow_config.py`,
   …), core code calls helper functions (`get_modules`, `multiload_all`, …) to
   pull in the discovered modules and merge their contributions.
3. **Packaging** — when a flow runs remotely (or in a Conda env), the
   extensions must travel with the code package. `dump_module_info`,
   `package_mfext_package` and `package_mfext_all` collect the right files and
   record load order so the remote side reconstructs the same state.

Discovery runs **exactly once at import time**. The module body ends with:

```python
_all_packages, _pkgs_per_extension_point = _get_extension_packages()   # :1008
```

so by the time any other Metaflow module imports `extension_support`, the two
global tables are already populated.

---

## 2. The `metaflow_extensions` package layout

An extension distribution looks like this:

```
metaflow_extensions/                 # MUST be an implicit namespace package (no __init__.py)
  <org>/                             # a "top-level" (tl) package, e.g. "netflix"
    mfextmeta_<org>.py               # OPTIONAL: packaging rules (suffix filters)
    config/
      mfextinit_<org>.py             # config extension point
    plugins/
      mfextinit_<org>.py             # plugins extension point
      cards/ ...                     # plugins.cards sub-point
      datatools/ ...                 # plugins.datatools sub-point
      env_escape/ ...                # plugins.env_escape sub-point
    toplevel/
      mfextinit_<org>.py             # toplevel extension point
    cmd/
      mfextinit_<org>.py             # cmd extension point
    exceptions/
      mfextinit_<org>.py             # exceptions extension point
    alias/
      mfextinit_<org>.py             # alias (integration) extension point
```

Two structural rules are enforced during discovery (`process_file`,
`__init__.py:527`):

- **`metaflow_extensions/__init__.py` is forbidden.** If found, discovery raises
  `RuntimeError("... is not an implicit namespace package as required")`
  (`:536`). This is essential — see §2.1.
- **You cannot put an extension point directly under `metaflow_extensions/`.**
  A file like `metaflow_extensions/plugins/...` errors with a message telling you
  to use `metaflow_extensions.X.plugins` where `X` is your org's name (`:569`).
  The intermediate "top-level" component is what allows multiple independent
  extensions to coexist.

### 2.1 Why namespace packages matter

`metaflow_extensions` is an **implicit namespace package** (PEP 420). A
namespace package has *no* `__init__.py`, and Python is willing to stitch
together the package from **multiple directories on `sys.path`**. That is
precisely what lets distribution A and distribution B both ship
`metaflow_extensions/aorg/...` and `metaflow_extensions/borg/...` and have both
appear under the single `metaflow_extensions` package. Discovery leans on this
by reading `extensions_module.__spec__.submodule_search_locations` (the list of
directories that make up the namespace package) as its starting set of paths
(`:425`).

### 2.2 The two configuration-file conventions

A package declares its contribution to an extension point via a **config
module**, recognized by two regexps (`:83-84`):

```python
EXT_CONFIG_REGEXP = re.compile(r"^mfextinit_[a-zA-Z0-9_-]+\.py$")
EXT_META_REGEXP   = re.compile(r"^mfextmeta_[a-zA-Z0-9_-]+\.py$")
```

- `mfextinit_<name>.py` — the per-extension-point config module. Its globals
  (the `*_DESC`, `TOGGLE_*`, `ENABLED_*` variables, `toplevel`, etc.) are what
  Metaflow reads. An `__init__.py` in the extension-point directory is also
  accepted as the config module (`parts[-1] == "__init__.py"`, `:601`).
- `mfextmeta_<name>.py` — *packaging* metadata only (file suffix filters); see
  §8. At most one per distribution, else `RuntimeError` (`:546`).

A global sanity check (`config_to_pkg` / `meta_to_pkg`, `:879-898`) makes sure
**no two distributions define the same config or meta module path**, since one
would silently shadow the other on `sys.path`.

---

## 3. Extension points

The fixed list of extension points is (`__init__.py:343`):

```python
_extension_points = [
    "plugins.env_escape",
    "plugins.cards",
    "plugins.datatools",
    "plugins",
    "config",
    "exceptions",
    "toplevel",
    "cmd",
    "alias",
]
```

Order matters: **more specific paths must come first**. `process_file` walks this
list in order and assigns a directory to the *first* matching point (`:591`,
"`break`" at `:651`), so `plugins/cards/...` is attached to `plugins.cards`, not
to `plugins`.

`get_modules(extension_point)` is the public entry that returns the list of
`MFExtModule` (named tuple `package_name, tl_package, module`) contributing to a
point, in dependency order (`:109`). It raises if you ask for a point not in the
list.

Where each point is consumed in core:

| Extension point | Consumed by | What it contributes |
| --- | --- | --- |
| `toplevel` | `metaflow/__init__.py` | symbols & submodules promoted to the `metaflow.*` namespace; `module_overrides` |
| `config` | `metaflow/metaflow_config.py` | config vars, `DEBUG_OPTIONS`, `TOGGLE_DECOSPECS`, merge of `get_pinned_conda_libs`, `get_click_to_python_types` |
| `exceptions` | `metaflow/exception.py` | exception classes loaded into that module's globals |
| `plugins` | `metaflow/plugins/__init__.py` | decorators, datastores, metadata providers, sidecars, secrets, CLIs, … |
| `plugins.cards` | `plugins/cards/card_modules/__init__.py` | custom card modules (NS-package friendly) |
| `plugins.datatools` | `plugins/datatools/__init__.py` | datatools (`multiload_all`) |
| `plugins.env_escape` | `plugins/env_escape/__init__.py` | environment-escape configs |
| `cmd` | `metaflow/cmd/main_cli.py` | top-level CLI commands |
| `alias` | `metaflow/integrations.py` | integration aliases |

---

## 4. Phase 1 — Package discovery (`_get_extension_packages`)

This is the heart of the system (`__init__.py:363`). It produces two tables:

- `mf_ext_packages` — keyed by distribution name (or a synthetic
  `_pythonpath_N` name), holding `root_paths`, `meta_module`, `files`,
  `full_path_files`, `version`.
- `extension_points_to_pkg` — keyed by extension point, value is an
  **ordered** list of `MFExtPackage(package_name, tl_package, config_module)`.

### 4.1 Short-circuit via the INFO file

If a precomputed INFO file exists (the case when running from a saved code
package), discovery does **not** scan the filesystem; it reads back the tables
directly (`:367-376`):

```python
info_content = read_info_file()
if not ignore_info_file and info_content:
    all_pkg, ext_to_pkg = info_content.get("ext_info", (None, None))
    ...
    return all_pkg, ext_to_pkg
```

This makes remote execution deterministic — see §8.

#### The INFO file and the packaged `__init__.py` are two halves of one design

There is a deliberate interplay between this short-circuit and packaging. When
Metaflow packages extensions for a remote run (§8.2), it flattens **all**
discovered extension files into a single `metaflow_extensions/` directory and
**injects an `__init__.py`** into it (the empty `_empty_file.py`). This is
intentional: the packaged `metaflow_extensions` is made into a *self-contained
regular package* precisely so that other `metaflow_extensions` contributions
installed on the remote machine cannot "pollute" the packaged code — the runtime
should see exactly the extensions that were present when the code was packaged,
and nothing else.

But that self-containment **breaks the namespace-package assumption** that
discovery relies on (§2.1, §4.2): the injected `__init__.py` would normally
trigger the `"... is not an implicit namespace package as required"` error
(`:536`), and flattening everything into one directory has also **erased the
per-distribution load order** derived from dependencies (§4.7).

The INFO file is what resolves both problems. Its job is *not* just caching —
it has two essential roles:

1. **Skip the namespace-package check entirely.** Because discovery returns
   early from the INFO tables (`:367-376`), it never imports
   `metaflow_extensions` to scan it, so the injected `__init__.py` is harmless.
2. **Restore the load order** (and the per-extension-point package lists) that
   was lost when all files were collapsed into a single directory.

This also explains a **common failure mode**: if the packaged
`metaflow_extensions/` directory is present but the INFO file is *missing* (or
not found), discovery falls through to the filesystem path, finds the
self-contained `metaflow_extensions` package, sees the injected `__init__.py`,
and raises the "not a namespace package" error. The fix is to make sure the
INFO file travels with — and is found alongside — the packaged code.

### 4.2 Bail out cleanly if there are no extensions

```python
try:
    extensions_module = importlib.import_module(EXT_PKG)
except ImportError as e:
    if not (isinstance(e, ModuleNotFoundError) and e.name == EXT_PKG):
        raise          # a *transitive* import error is real — re-raise
    return {}, {}      # simply no extensions installed
```

The subtle part (`:389`): a bare "no `metaflow_extensions`" is swallowed, but if
the extension itself imports something broken, that `ModuleNotFoundError` has a
different `e.name` and is correctly propagated.

### 4.3 Two kinds of providers

The code deliberately distinguishes (`:398`):

1. **Installed distributions** — discovered via `importlib.metadata`
   (vendored as `metaflow._vendor.v3_7/v3_6.importlib_metadata` on old Pythons,
   `:330-335`). These carry rich metadata: the file manifest and, crucially,
   **dependencies** (used for load ordering).
2. **`PYTHONPATH` packages** — directories that appear in the namespace
   package's search locations but don't belong to any distribution. Less
   information is available (in particular, no dependency metadata to order
   them by), so they're handled separately and always loaded *last*. Their
   order is still **deterministic**: the leftover paths are collected into a set
   and then **sorted alphabetically by resolved path** before being appended to
   the load list (`all_paths_list.sort()`, `:822-823`). They are also given
   synthetic names `_pythonpath_0`, `_pythonpath_1`, … in that sorted order
   (`:847`) and version `"_local_"`.

### 4.4 Collecting all candidate paths (path hooks)

Starting from `extensions_module.__spec__.submodule_search_locations`, the code
walks a worklist of paths (`:424-482`). For each path it either:

- adds it directly if it's a real directory, or
- consults `sys.path_importer_cache[p]` / `sys.path_hooks` and calls
  `finder.find_spec(EXT_PKG)` to resolve *virtual* paths into real directories.

This is what makes **editable installs** work. A modern editable install drops a
`__editable__.<name>.py` finder rather than a real directory on `sys.path`. The
code derives the finder's filename from the path-hook key:

```python
finder_name = p[:-14].translate(FINDER_TRANS) + ".py"   # :442
# FINDER_TRANS = str.maketrans(".-", "__")   (:87) — the synthetic
# "<path>.__path_hook__" key has its trailing ".__path_hook__" (14 chars)
# stripped, dots/dashes normalized to underscores, ".py" appended.
```

and records `finders_to_paths[finder_name] = [real dirs…]` so it can later be
tied back to the owning distribution (which lists `__editable__….py` among its
files, `:706`).

### 4.5 `process_file` — classifying every file

`process_file(state, root_dir, file)` (`:527`) is the per-file classifier. Given
a path like `metaflow_extensions/netflix/plugins/mfextinit_netflix.py` it:

- records the file (minus a `.pyc`, `EXT_EXCLUDE_SUFFIXES`, `:86`) into
  `state["files"]` / `state["full_path_files"]` so packaging can include it;
- detects the meta module (`mfextmeta_*.py`) at the second level;
- enforces the "no `__init__.py` at `metaflow_extensions/` top level" and
  "no extension point directly under `metaflow_extensions/`" rules;
- for paths of the form `metaflow_extensions/<tl>/<ext-point parts…>/…`, matches
  against `list_ext_points` (`:591`) and, when the file is the config module
  (`mfextinit_*.py` or `__init__.py` at exactly the right depth, `:599`),
  records an `MFExtPackage` into `extension_points_to_pkg[point][dist][tl]`.

Duplicate config modules within one tl-package for the same point are an error
(`:617`).

### 4.6 Walking distributions

For each installed distribution whose `top_level.txt` lists `metaflow_extensions`
(`:654-657`), the code:

- computes `dist_root = dist.locate_file(EXT_PKG)`;
- iterates `dist.files`, handling three cases (`:699-718`):
  - `.pth` files → read the directory they point at, add to `addl_dirs`;
  - `__editable__*` finder files → pull dirs from `finders_to_paths`;
  - files starting with `metaflow_extensions` → `process_file`;
- for any `addl_dirs` it can't get from the manifest, it physically walks the
  tree with `walk_without_cycles` (a symlink-cycle-safe `os.walk`, imported from
  `metaflow.util`, `:745`).
- respects `restrict_to_directories` (from `METAFLOW_EXTENSIONS_SEARCH_DIRS`,
  `:96`) — a package is skipped unless one of the restriction dirs is a parent.

### 4.7 Load order: topological sort by dependency

The order extensions load in is **derived from `pip` dependencies** (`:766-817`):

> If distribution A depends on distribution B and both provide
> `metaflow_extensions`, then B is returned before A.

Implementation: count, for each package, how many of its requirements
(`metadata.requires`, parsed with `REQ_NAME`, `:85`) are themselves extension
packages; seed the worklist with the zero-dependency roots (sorted
alphabetically for determinism); Kahn's algorithm from there. A leftover count
means a cycle / unresolved dep → `RuntimeError` (`:811`). `PYTHONPATH` packages
are appended afterward, alphabetically, with version `"_local_"` (`:872`).

This ordering is what gives extensions a well-defined override priority:
**later-loaded packages override earlier ones**.

### 4.8 Special-case: `plugins.cards` may be a pure namespace package

In the final per-point assembly (`:903-930`), every point requires a config
module *except* `plugins.cards`, which is permitted to be a bare namespace
package (no `mfextinit_*.py`), in which case only the first occurrence per
tl-package is kept. Every other point raises
`"Package … does not define a configuration file for '<point>'"` if the config
module is missing.

This exemption exists for **historical reasons**. Cards were designed to be
*easily* extendable — the intent was that you could drop a simpler package
(a bare namespace package of card modules) under `plugins/cards/` without
having to author a `mfextinit_*.py` config module. That lightweight path still
works, but the **regular way of extending** (with a `mfextinit_*.py`, exactly
like every other point) works for cards too and is the recommended approach for
anything beyond the simplest case.

---

## 5. Phase 2 — Integration & the import machinery

This is where the most interesting Python is used. Metaflow wants three distinct
effects, and has a helper for each:

| Helper | Effect |
| --- | --- |
| `load_globals(module, dst_globals)` | Copy non-dunder, non-module attributes from an extension module into a target `globals()`. |
| `alias_submodules(module, tl, point)` | Compute a dict of *alias name → real module/path* so `metaflow.X` can mean `metaflow_extensions.<tl>.<point>.X`. |
| `lazy_load_aliases(aliases)` | Install those aliases **lazily** via a custom `sys.meta_path` finder. |
| `multiload_globals` / `multiload_all` | Convenience wrappers that run the above across all modules from `get_modules`. |

### 5.1 `load_globals` — flattening symbols

```python
def load_globals(module, dst_globals, extra_indent=False):       # :234
    for n, o in module.__dict__.items():
        if not n.startswith("__") and not isinstance(o, types.ModuleType):
            dst_globals[n] = o
```

Dunders and submodules are skipped (submodules are handled by aliasing instead).
This is how `config`/`exceptions`/`toplevel` extensions inject plain symbols.

### 5.2 `alias_submodules` — computing the alias map

```python
def alias_submodules(module, tl_package, extension_point, extra_indent=False):  # :246
```

It produces a dict mapping a `metaflow.…` name to the real
`metaflow_extensions.<tl>.…` target. Two sources feed it:

1. **Explicit promotion** via `__mf_promote_submodules__` — a list the extension
   author defines in their config module. For a top-level override
   (`extension_point is None`) it maps `metaflow.<k>` →
   `metaflow_extensions.<tl>.<k>`; otherwise `metaflow.<point>.<k>` →
   `metaflow_extensions.<tl>.<point>.<k>` (`:255-284`).
2. **Implicit** — the function scans the config module's own namespace for
   attributes that are themselves modules. For every attribute bound under name
   `n` to a module object `o` whose `__package__` starts with
   `metaflow_extensions.<tl>` (`:285-296`), it creates an alias **keyed by the
   attribute name `n`, pointing at the module object `o` itself**:
   - if `extension_point` is set: `metaflow.<point>.<n>` → `o`
   - if `extension_point` is `None` (top-level override): `metaflow.<n>` → `o`

   In other words, whatever submodules the config module has *imported into its
   own namespace* become reachable under the `metaflow` namespace using the same
   local name. Concretely, if `metaflow_extensions/netflix/plugins/mfextinit_netflix.py`
   does `from . import foo`, then `foo` (a module object) is aliased so that
   `import metaflow.plugins.foo` resolves to it. Note the alias value here is the
   already-loaded **module object**, not a string — `_AliasLoader` returns it
   directly (§5.4). The `startswith` guard deliberately prevents aliasing across
   `tl_package` boundaries (you cannot alias another org's submodules).

The alias keys are also appended to the module-global `_aliased_modules`
(`:301`), which `get_aliased_modules()` exposes to Pylint
(`pylint_wrapper.py`) and the stub generator (`cmd/develop/stub_generator.py`)
so static tools don't flag the synthetic names.

### 5.3 `lazy_load_aliases` and `_LazyFinder` — the PEP 302 finder

```python
def lazy_load_aliases(aliases):                                  # :305
    if aliases:
        sys.meta_path = [_LazyFinder(aliases)] + sys.meta_path
```

This is the core trick. Rather than importing aliased modules eagerly (which
could trigger heavy/circular imports), Metaflow **prepends a custom
`MetaPathFinder` to `sys.meta_path`**. The alias only resolves to a real import
the first time someone actually imports `metaflow.X`.

`_LazyFinder.find_spec(fullname, path, target)` (`:1159`) handles four cases:

1. **Directly handled name** → return a spec backed by `_AliasLoader` (`:1169`).
2. **A `._orig.` name** → the module is *shadowed* and the caller wants the
   original. The finder temporarily removes the shadowing module from
   `sys.modules`, swaps in the `_orig` parent, calls
   `importlib.util.find_spec` to locate what *would* have been imported absent
   the finder, then wraps the result in `_OrigLoader` (`:1184-1233`). This is
   the mechanism that lets an extension **override** a core `metaflow` module
   while still being able to reach the original under a `._orig` suffix.
3. **A relative import from within an `_orig` tree** → it redirects the lookup
   into the `_orig` namespace using `_orig_search_paths` (`:1235-1245`).
4. **A submodule of a handled alias** → it finds the most specific handled
   parent prefix (longest match by chopping name components, `:1246-1263`) and
   aliases the submodule onto the original's `__orig_name__`.

`_temp_excluded_prefix` (`:1165`) prevents infinite recursion: while the finder
is resolving the *original* of a shadowed module, it declares it does not handle
anything under that prefix.

### 5.4 `_AliasLoader` and `_OrigLoader`

`_AliasLoader` (`:1061`) is a minimal `Loader`:

- `create_module` returns the target module — importing it by string if the
  alias value is a string, or returning the already-loaded module object
  directly if the alias value is a `ModuleType` (`:1066-1081`).
- `exec_module` renames the module to its alias and stashes the original under
  `__orig_name__` (`:1083-1088`), so e.g. the module loaded as
  `metaflow_extensions.netflix.plugins.foo` will report `__name__ ==
  "metaflow.plugins.foo"` while remembering its real name.

`_OrigLoader` (`:1091`) is used when reconstructing a shadowed original. It
delegates `create_module`/`exec_module` to the real loader, then:

- renames the freshly loaded module to the requested `_orig` `fullname`, fixes
  `__spec__.name`, `__package__`, registers it in `sys.modules` and deletes the
  temporary original name (`:1118-1125`);
- in a `finally`, **restores** the previously loaded module and parent module
  back into `sys.modules` (`:1127-1136`) so the shadow stays in place and only
  the `_orig` view is added.

This pair is what makes "override but keep access to the original" possible
purely through Python's import system, with no monkey-patching of source.

### 5.5 `multiload_globals` / `multiload_all`

```python
def multiload_all(modules, extension_point, dst_globals):        # :315
    for m in modules:
        lazy_load_aliases(
            alias_submodules(m.module, m.tl_package, extension_point, extra_indent=True)
        )
        load_globals(m.module, dst_globals)
```

Aliases are installed **per module, before** loading the next module's globals,
so later extensions can depend on aliases registered by earlier ones (`:317`).

### 5.6 Worked example: top-level loading in `metaflow/__init__.py`

`metaflow/__init__.py` shows the full pattern (`:62-92`, `:169-179`):

1. `get_modules("toplevel")` returns the `toplevel` config modules.
2. For each, it reads two optional globals from the config module:
   - `module_overrides` → name of a module that *overrides* core metaflow
     modules; loaded **first** (`:87-92`) via `load_module` +
     `lazy_load_aliases(alias_submodules(..., None))`. The `None` extension
     point means "promote into the `metaflow` top-level namespace directly".
   - `toplevel` → name of a module whose symbols are flattened into the
     `metaflow` namespace with `load_globals`, and whose submodules are aliased,
     **after** core metaflow has finished importing (`:171-179`). These get
     recorded in `__ext_tl_modules__`.

The file also shows a non-extension use of the same machinery — the historical
alias `metaflow.datatools → metaflow.plugins.datatools` (`:119`).

Finally it deletes the imported helpers from its namespace (`:182+`) to avoid
leaking `alias_submodules`, `get_modules`, etc. into `import metaflow`.

---

## 6. The `*_DESC` / `TOGGLE_*` / `ENABLED_*` protocol

`plugins.py`, `cmd.py` and `integrations.py` share an identical pattern (the
latter two say so in comments). Plugins are **not** imported at discovery time;
they are declared as `(name, "dotted.class.path")` tuples and resolved lazily.

### 6.1 Declaration: `*_DESC` lists

Core declares plugins in `metaflow/plugins/__init__.py` as `*S_DESC` lists keyed
by category, e.g. `STEP_DECORATORS_DESC`, `CLIS_DESC`, `TRAMPOLINE_CLIS_DESC`,
`DATASTORES_DESC`, … The categories themselves and how to extract a plugin's
canonical name are defined in `_plugin_categories` (`plugins.py:201`):

```python
_plugin_categories = {
    "step_decorator": lambda x: x.name,
    "flow_decorator": lambda x: x.name,
    "environment": lambda x: x.TYPE,
    "metadata_provider": lambda x: x.TYPE,
    "datastore": lambda x: x.TYPE,
    "dataclient": lambda x: x.TYPE,
    "secrets_provider": lambda x: x.TYPE,
    "gcp_client_provider": lambda x: x.name,
    "deployer_impl_provider": lambda x: x.TYPE,
    "azure_client_provider": lambda x: x.name,
    "sidecar": None,                 # no self-naming field
    "logging_sidecar": None,
    "monitor_sidecar": None,
    "aws_client_provider": lambda x: x.name,
    "cli": lambda x: list(x.commands)[0] if len(x.commands) == 1 else "too many commands",
    "runner_cli": lambda x: x.name,
    "tl_plugin": None,
}
```

The naming lambda doubles as a validation hook: when a plugin is finally
imported, `get_plugin` checks the class's self-reported name matches the
declared name and errors otherwise (`plugins.py:129-134`).

### 6.2 Relative path resolution

An extension may declare paths relative to its own package
(`.foo.Bar`). `_resolve_relative_paths` (`plugins.py:257`, mirrored in the other
two files) rewrites a leading-dot path into a fully-qualified one using the
module's `__package__`, counting leading dots to climb package levels, and
raising if a path "exits out of the Metaflow module" (`:272`).

### 6.3 `process_plugins` — merge order

`process_plugins(module_globals)` (`plugins.py:15`) runs once from
`plugins/__init__.py:196`. It:

1. Reads `ENABLED_<CATEGORY>` from configuration (`from_conf`) and initializes an
   empty `_TOGGLE_<CATEGORY>` per category (`:20-25`).
2. Seeds `_all_<category>s` from **core** Metaflow's `*_DESC` (`:28`).
3. Merges core `TRAMPOLINE_CLIS_DESC` into the `cli` list and records their names
   in `_trampoline_cli_names` (`:32-38`) — these are compute-backend CLI groups
   (`batch`, `kubernetes`) tracked separately so `system_context` can detect the
   trampoline phase.
4. For every module from `get_modules("plugins")`, installs aliases, then scans
   the module globals for:
   - `TOGGLE_<CATEGORY>` → **append** to the toggle list (`:49-51`);
   - `ENABLED_<CATEGORY>` → **override** the enabled value (`:52-54`);
   - `<CATEGORY>S_DESC` → append the extension's plugins (`:57-61`);
   - `TRAMPOLINE_CLIS_DESC` → merge & track (`:62-66`).
5. The whole loop is wrapped in `try/except` that, on any import error, prints a
   warning and **silently drops all plugins** rather than crashing Metaflow
   (`:67-73`). (`cmd.py` and `integrations.py` do the same.)
6. Builds `_all_<category>s_dict`, where **later entries override earlier ones by
   name** — i.e. extensions override core (`:79-86`).

### 6.4 `ENABLED_*` resolution — two philosophies

The toggle/enabled logic (`plugins.py:98-101`, identical in `cmd.py`/
`integrations.py`) supports both styles of configuration:

- **Explicit**: if `ENABLED_<CATEGORY>` is set (by the user via config/CLI or by
  an extension), that list is honored verbatim and the `TOGGLE_` lists are
  ignored.
- **Configuration-less**: if `ENABLED_<CATEGORY>` is `None`, it is synthesized as
  *everything discovered* plus the accumulated `TOGGLE_` entries — so merely
  *installing* an extension activates its plugins.

### 6.5 `resolve_plugins` — the lazy import

`resolve_plugins(category, path_only=False)` (`plugins.py:140`) is called from
`plugins/__init__.py` to produce the final lists (`STEP_DECORATORS`,
`ENVIRONMENTS`, `DATASTORES`, …). It:

1. Walks the `ENABLED_<CATEGORY>` list, interpreting `+name` / `-name` prefixes
   as add/remove toggles against a `set` (`:151-157`).
2. For each surviving name, looks up the class path and, unless `path_only`,
   **imports the module and grabs the class** via `get_plugin` (`:172-185`).
   `path_only=True` returns the dotted paths without importing — used to defer
   heavy imports (e.g. CLI groups).

`get_plugin` (`:115`) does the `importlib.import_module` + `getattr`, validates
the name, caches the class into the module globals, and raises descriptive
`ValueError`s if the module or class is missing.

So the full chain for, say, a step decorator is:
**discovery → `process_plugins` (merge `*_DESC`) → `resolve_plugins`
(`ENABLED_STEP_DECORATOR` → set → `get_plugin` import) → `STEP_DECORATORS`.**

### 6.6 `cmd` and `alias` points

- `cmd.py` is "identical in functionality" to `plugins.py` but for a single
  category. `CMDS_DESC` tuples become click command classes; `resolve_cmds`
  enforces exactly one command per class and a name match (`cmd.py:103-110`).
  Consumed by `metaflow/cmd/main_cli.py:73` (`process_cmds`) +
  `:78` (`resolve_cmds()` feeds the click `CommandCollection`).
- `integrations.py` resolves `ALIASES_DESC` into actual objects and **injects
  them directly into `module_globals`** of `metaflow/integrations.py:31`, so
  `from metaflow.integrations import <alias>` works.

### 6.7 `config` and `exceptions` points

These don't use the DESC protocol — they use raw globals merging:

- `metaflow_config.py:701` iterates `get_modules("config")` and copies globals
  with special handling: `DEBUG_OPTIONS` extend, `TOGGLE_DECOSPECS` accumulate,
  and `get_pinned_conda_libs` / `get_click_to_python_types` are **wrapped** so
  the extension's function is merged with core's rather than replacing it
  (`:712-750`). Everything else non-dunder/non-module is copied verbatim.
- `exception.py:167` is a one-liner: `multiload_globals(get_modules("exceptions"),
  globals())`.

### 6.8 `plugins.cards` point

Cards are special because a card extension may be a pure namespace package.
`card_modules/__init__.py:31` iterates `get_modules("plugins.cards")` and, for
each, either uses the module directly (if it has a real `__file__`, i.e. a
`mfextinit_*.py` or regular package) or walks its submodules with
`pkgutil.iter_modules` over the namespace `__path__` (`:42-55`), importing each
sub-package. This is the reason `plugins.cards` is exempted from the
"must have a config module" rule in §4.8.

---

## 7. Configuration knobs (environment variables)

Read directly from `os.environ` (not `metaflow_config`, to avoid a circular
import, `:91-98`):

| Variable | Effect |
| --- | --- |
| `METAFLOW_DEBUG_EXT` | When truthy, `_ext_debug` prints verbose `metaflow_extensions:` traces to `stderr` (`:92`, `:356`). |
| `METAFLOW_EXTENSIONS_SEARCH_DIRS` | `os.pathsep`-separated list restricting discovery to packages whose root is under one of these dirs (`:96`, applied at `:379`, `:667`, `:725`, `:831`). |

---

## 8. Phase 3 — Packaging extensions for remote/Conda execution

When a flow runs on a remote backend or in a Conda env, the `metaflow_extensions`
files must ride along in the code package, and the discovery tables must be
reproduced exactly. Three pieces cooperate.

### 8.1 Recording the tables: `dump_module_info`

`dump_module_info` (`:129`) returns `("ext_info", [sanitized_all_packages,
pkgs_per_extension_point])`. It **strips** `root_paths` and `full_path_files`
(both set to `None`) so the user's local directory layout isn't leaked, but
keeps `meta_module`, `files`, `version`, `package_version`, `extension_name`.
This is written into the INFO file via
`metaflow_environment.get_environment_info(include_ext_info=True)`
(`metaflow_environment.py:276-278`). On the remote side, `_get_extension_packages`
reads it back through `read_info_file()` (§4.1) — so discovery on the remote
does **zero filesystem scanning** and reconstructs identical load order.

### 8.2 Collecting the files: `package_mfext_package` / `package_mfext_all`

`package_mfext_package(name)` (`:190`) yields `(source_path, archive_path)`
tuples for one package's files, where `archive_path` is rooted at
`metaflow_extensions/...`. It has two modes (`:196-213`):

- **Initial packaging** (local, `full_path_files` known): map each
  `full_path_files[i]` to `metaflow_extensions/<files[i]>`.
- **Re-packaging** (running already inside a packaged env): reconstruct from
  `root_paths` + `files`, existence-checking each file when there are multiple
  roots.

`package_mfext_all` (`:216`) yields every package's files **plus** a synthetic
`metaflow_extensions/__init__.py` taken from `_empty_file.py` (`:221-224`). This
deliberately turns the packaged `metaflow_extensions` into a **self-contained
regular package** so that, on the remote, Python doesn't go hunting elsewhere on
the system for more `metaflow_extensions` namespace fragments. (`_empty_file.py`
is intentionally empty and documents exactly this purpose.)

Consumed by `packaging_sys/v1.py` (`package_mfext_all()` at `:423`,
descriptions at `:426`, and the `_empty_file.py` reference at `:526`).

### 8.3 Meta-module file filters: `_filter_files_package`

If a package ships an `mfextmeta_<name>.py`, `_filter_files_package` (`:957`)
loads it and applies, in priority order (`:976-1003`):

1. `filter_function(path)` — called per file (path always begins with
   `metaflow_extensions/`); include if it returns truthy. Exceptions are caught
   and the file dropped.
2. `include_suffixes` — whitelist of suffixes.
3. `exclude_suffixes` — blacklist (only consulted if no `include_suffixes`).
4. Otherwise include everything.

Filtering is applied when files were discovered by *walking* a directory (so the
manifest is unreliable) — i.e. for `.pth`/editable `addl_dirs` (`:756-765`) and
always for `PYTHONPATH` packages (`:874-875`). When the distribution fully
specifies its files, the meta module is ignored for filtering.

### 8.4 `root_paths` back-fill on load

When `_get_extension_config` (`:1011`) loads a config module and the package's
`root_paths` is `None` (the INFO-file case where it was stripped), it derives the
root from the loaded module's `__file__` by chopping the right number of path
components — `strip_from_filepath` differs by 1 between the `mfextinit_*.py` case
and the `__init__.py` case (`:1012-1024`). For NS-package cards (no `__file__`),
it derives roots from `__path__` instead (`:1043-1050`). This re-enables
re-packaging from inside a remote/Conda environment.

---

## 9. Other integrations & metadata

- **Version reporting.** `metaflow_version.py` uses `update_package_info`
  (`:171`) to attach `extension_name`/`package_version` to packages, derived
  from the `toplevel` module's `__mf_extensions__` / `__version__`
  (`metaflow_version.py:217`). `extension_info()` (`:154`) summarizes installed
  extensions for `_graph_info` (`flowspec.py`).
- **Artifact serializers.** `datastore/artifacts/serializer.py:284` pulls
  `get_modules("plugins")` to discover extension-provided
  `ARTIFACT_SERIALIZERS_DESC`.
- **Static analysis.** `get_aliased_modules()` (`:186`) feeds the Pylint wrapper
  (`pylint_wrapper.py`) and stub generator (`cmd/develop/stub_generator.py`) so
  the synthetic `metaflow.*` aliases don't produce false "no such module" errors.

---

## 10. Summary of the Python mechanisms used

| Mechanism | Where | Purpose |
| --- | --- | --- |
| **PEP 420 implicit namespace packages** | `metaflow_extensions` (no `__init__.py`) | Let multiple distributions merge into one package. |
| **`importlib.metadata` distributions** | `_get_extension_packages` | Enumerate providers, read `top_level.txt`, file manifests, and `requires` for ordering. |
| **`sys.path_hooks` / `path_importer_cache` / `find_spec`** | `:435-481` | Resolve editable-install finders and `.pth` redirects into real directories. |
| **Topological sort (Kahn's algorithm)** | `:766-817` | Order extensions by `pip` dependency so overrides are deterministic. |
| **`sys.meta_path` + custom `MetaPathFinder`** (`_LazyFinder`) | `lazy_load_aliases` | Lazily resolve `metaflow.X` aliases to `metaflow_extensions...` only on first import. |
| **Custom `Loader`s** (`_AliasLoader`, `_OrigLoader`) | `:1061-1136` | Return aliased modules and reconstruct shadowed originals under a `._orig` view, with `sys.modules` swapping. |
| **`module.__dict__` introspection** | `load_globals`, `process_plugins`, config merge | Copy/merge symbols, detect `*_DESC`/`TOGGLE_*`/`ENABLED_*`. |
| **Lazy class loading via dotted paths** | `get_plugin`/`resolve_*` | Declare plugins as strings; `importlib.import_module` + `getattr` only when enabled. |
| **`__mf_promote_submodules__` convention** | `alias_submodules` | Author-controlled explicit promotion of submodules into the `metaflow` namespace. |
| **INFO-file precomputation** | `dump_module_info` / `read_info_file` | Reproduce discovery exactly on remote/Conda without rescanning. |
| **Vendored `importlib_metadata`** | `:330-335` | Support Python 3.6/3.7 where stdlib `importlib.metadata` is absent. |

---

## 11. End-to-end example: adding a step decorator

1. Create distribution `my-mf-ext` shipping
   `metaflow_extensions/myorg/plugins/mfextinit_myorg.py` (and **no**
   `metaflow_extensions/__init__.py`).
2. In `mfextinit_myorg.py`:
   ```python
   STEP_DECORATORS_DESC = [("mydeco", ".my_decorator.MyDecorator")]
   # MyDecorator.name must == "mydeco"
   ```
3. `pip install my-mf-ext`. Discovery finds it, attaches it to the `plugins`
   point, orders it after its deps.
4. `metaflow/plugins/__init__.py` runs `process_plugins`, which resolves the
   relative path to `metaflow_extensions.myorg.plugins.my_decorator.MyDecorator`,
   appends it to `_all_step_decorators`, and (since `ENABLED_STEP_DECORATOR` is
   likely `None`) adds `"mydeco"` to the enabled set.
5. `STEP_DECORATORS = resolve_plugins("step_decorator")` imports
   `MyDecorator`, validating `MyDecorator.name == "mydeco"`.
6. `@mydeco` is now usable in any flow; on remote runs the files are packaged via
   `package_mfext_all` and the tables travel in the INFO file.

---

## 12. Choosing a mechanism: what to use when

Not every customization needs the full `metaflow_extensions` machinery. There
are three broad situations, and the lighter-weight options are usually the right
choice.

### 12.1 Additive — adding something that doesn't already exist

This is **by far the most common case**: you want a new step/flow decorator, a
new datastore, a new metadata provider, a new CLI command, etc. that does not
exist in core. You declare it through the relevant extension point's `*_DESC`
list (or `CMDS_DESC` / `ALIASES_DESC`) and, optionally, toggle it on by default
via the `TOGGLE_*`/`ENABLED_*` protocol (§6). Nothing in core is replaced — your
plugin simply joins the list. The §11 example is exactly this.

### 12.2 Replacement — overriding part of core

Sometimes you need to *replace* a piece of core, e.g. swap out
`metaflow.conda`/`metaflow.parameters`-style modules or substitute a core plugin
with your own implementation. There are **two distinct ways** to do this, and
they operate at different layers:

- **Replace a plugin (by name), through the `plugins` point.** Because
  `process_plugins` builds its dictionaries so that **later entries override
  earlier ones by name** (§6.3), an extension that declares a `*_DESC` entry with
  the *same name* as a core plugin (e.g. another `("conda", …)` step decorator)
  shadows core's. This is the right tool when the thing you want to replace *is a
  plugin* — it stays within the plugin registry and the `ENABLED_*`/toggle rules.

- **Replace a module (by import path), through `toplevel`.** When you need to
  override an actual importable module in the `metaflow.*` namespace (not just a
  registered plugin), a `toplevel` config module sets `module_overrides`
  (`metaflow/__init__.py:68`). These are loaded **first**, before core finishes
  importing, and aliased with `extension_point = None` so they map directly onto
  `metaflow.<name>`. This rides the `_orig` shadowing machinery (§5.3–5.4):
  `metaflow.<name>` becomes your module while the original remains reachable at
  `metaflow.<name>._orig`, so your override can delegate to the code it replaces.
  Use this when the override target is a *module*, or when a plugin-level
  override isn't expressive enough.

### 12.3 Without extensions at all — mutators and `METAFLOW_PACKAGE_POLICY`

You do **not** need `metaflow_extensions` to extend Metaflow in many cases. Two
much lighter mechanisms exist and avoid all of the discovery / aliasing / INFO
machinery above:

- **Mutators (`FlowMutator` / `StepMutator`)** — defined in
  `metaflow/user_decorators/`. These let user (or library) code programmatically
  rewrite a flow/step at definition time (add decorators, mutate config, etc.)
  without registering anything as a plugin. Critically, the module that *defines*
  a mutator is auto-tracked (`FlowMutatorMeta._import_modules` /
  `UserStepDecoratorMeta._import_modules`) so it is **automatically included in
  the code package** (`metaflow/package/__init__.py:75-94`) and ships to remote
  runs.

- **`METAFLOW_PACKAGE_POLICY = "include"`** — any module that sets this
  module-level attribute is picked up by the same packaging `_module_selector`
  (`package/__init__.py:87-89`) and bundled into the code package. This lets a
  plain library travel with the flow without being a Metaflow extension at all.

### 12.4 Decision table

| You want to… | Use | Heavy machinery? |
| --- | --- | --- |
| Add a new decorator / datastore / provider / sidecar / CLI / alias | The matching extension point's `*_DESC` (`plugins`, `cmd`, `alias`) + `TOGGLE_*`/`ENABLED_*` | Yes (`metaflow_extensions`) |
| Add config defaults, debug options, decospecs, pinned conda libs | `config` extension point | Yes |
| Add exception classes / top-level symbols | `exceptions` / `toplevel` extension points | Yes |
| Replace a **plugin** with your own (same name) | `plugins` point, later override wins (§6.3) | Yes |
| Replace / wrap a core **module** (`metaflow.X`) | `toplevel` `module_overrides` + `._orig` (§5.3) | Yes |
| Rewrite a flow/step at definition time | `FlowMutator` / `StepMutator` | **No** |
| Ship an ordinary library module with the flow | `METAFLOW_PACKAGE_POLICY = "include"` | **No** |

Rule of thumb: reach for `metaflow_extensions` only when you are contributing to
a **named extension point** that many flows should pick up implicitly (or that
must be distributed as an installable package). For per-flow or per-library
behavior, prefer mutators and `METAFLOW_PACKAGE_POLICY` — they are simpler, need
no discovery, and package themselves automatically.
