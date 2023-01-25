
# Metaflow 2.7.20
Metaflow 2.7.20 changes how plugins and commands are loaded and makes it possible to
load only those plugins and commands you want (as opposed to everything included in Metaflow).

This allows you to design extensions which, for example, can disable certain functionality (like azure
or kubernetes) and tailor Metaflow to your specific environment.

This does, however, change the way extensions need to specify their plugins and commands. Existing
extensions will cease to function with Metaflow 2.7.20 unless they are updated.

The change is very straightforward and simply consists of replacing statements like:
```
from .my_decorators import MyStepDecorator
STEP_DECORATORS = [MyStepDecorator]
```
with
```
STEP_DECORATORS_DESC = [("mystepdecorator", ".my_decorators.MyStepDecorator")]
```

In other words, you simply convert the import path to a string and add the name of the
plugin (in this case `mystepdecorator`). Sidecars previously had names (they were
defined in dictionaries). For everything else, the name corresponds to the `name` or
`TYPE` field of your decorator/plugin.

# Metaflow 2.7.13
The `cmd` extension point was added allowing you to add additional top-level command
options to the `metaflow` command line tool.
