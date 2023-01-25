# Metaflow Extension Framework

## Warning

**Anything described in this document is not guaranteed to be supported as Metaflow
evolves. While Metaflow will support an extension system similar to this, the exact
mechanism may evolve. Some of the possibilities offered through this mechanism also
require you to depend directly on internal APIs (for example the interface of a
decorator) which are not guaranteed to be stable or backward compatible like the user-facing
APIs.**

**Anything described here is therefore NOT meant for the casual user. If you choose to
proceed, we would, however, be interested in your use case and any features that would make
this more useful. Please open an issue with any feedback.**

## Context

Metaflow is a growing project and, as more companies and partners adopt it, they may
want to develop their own integrations and extensions particularly to better integrate
with their own proprietary systems. This is what we do at Netflix and are therefore able
to use and benefit from the OSS release of Metaflow while still having Metaflow tightly
coupled with our execution environment. This document highlights the approach we use to
achieve this.

## User stories

The following are motivating use cases for this framework.


### Modify default values

Company X wants to provide its users a seamless experience with Metaflow and does not
want them to have to configure much to use it. Metaflow provides a lot of customization
variables out of the box but they all rely on environment variables (present in
`metaflow_config.py`). Company X does not think that requiring its users to muck around
with environment variables is a friendly way to proceed. Company X would thus like a way
to override these defaults so that its users can simply do ``pip install
companyx-metaflow`` and get everything configured the way company X wants.


### Providing another Flow or Step level decorator

Company Y is very happy with Metaflow except that it would like to provide a decorator
that integrates with their own compute platform (like `@batch`). These decorators
typically need to interact with Metaflow during a task’s lifecycle and cannot be
developed completely independently of Metaflow.

Note that decorators that do not need to interact with Metaflow’s task’s lifecycle do
not need to be developed this way and can simply be developed externally and called from
the user code. A decorator, for example, that simply installs pip packages at the start
of every task, does not need deep integration with Metaflow.


### Integrating with internal logging systems

Company Z already has a system to log events to and would like to integrate Metaflow’s
events with that system.


## Definitions

We define the following:



* Metaflow **base**: currently everything that is included in the Metaflow public GitHub
  repository. This is the base code used to build the `metaflow` Python package.
* Metaflow **plugin**: anything that lives in the plugins folder, either as a python
  file (for some of the simpler plugins like the catch decorator) or as a directory (for
  the more complex plugins like batch for example)
* Metaflow **flavor**: a set of customization modules that modify Metaflow’s behavior.
  The **vanilla** flavor is Metaflow base (no additional customizations). This document
  lays out the aspects that can be customized to create, for example, the “Netflix”
  flavor.


## Basic concepts

The basic mechanism of providing all the functionalities described in the user stories
(and more) is to allow users to create a new Python package which installs a package
called `metaflow_extensions`. This special `metaflow_extensions` package will depend on
Metaflow (so installing it will install the Metaflow Python package) but, when Metaflow
runs, it will look for a package called `metaflow_extensions` and use it to modify and
enhance its functionality, integrating, in a way, the content of `metaflow_extensions`
into itself.

As a concrete example, within Netflix, a Metaflow user installs a package called
`nflx-metaflow` which installs itself as `metaflow_extensions` (the name of the
installed package and the Pypi package does not have to be the same so internally) and
this in turn installs the package `metaflow`. The user would then use `metaflow` (using
for example `from metaflow import FlowSpec`) which would include the functionality and
features defined within the `metaflow_extensions` package. With this setup, the company
providing the `metaflow_extensions` package has full control over the plugins provided,
the version of metaflow to import and the general default settings for the user.


### Evolution

Note that the current mechanism of **installing** a metaflow customization consists of
having the user install _another_ package (here `nflx_metaflow` instead of `metaflow`).
While this approach works well within Netflix as users are accustomed to installing
`nflx_metaflow`, it may not be an ideal approach for other use cases. It is entirely
possible to modify this and have users install metaflow and then run a metaflow command
(like `metaflow install my_customization`) or have metaflow look for an environment
variable. The point is that the exact mechanism by which the additional package gets
installed can vary. The overall architecture of having two packages installed side by
side (`metaflow` and `metaflow_extensions`) and their interaction is the focus of this
document.


### Structure of the metaflow_extensions package

A customization package has the following structure. We will explain the purpose of each
part in the following subsections.


```
metaflow_extensions/org
├── config
│   └── mfextinit_org.py
├── datatools
│   └── mfextinit_org.py
├── exceptions
│   └── __init__.py
├── plugins
│   ├── mfextinit_org.py
│   ├── env_escape
│   │   ├── configurations
│   │   └── __init__.py
│   ├── cards
│   │   ├── mycard1
│   │   └── mycard2
│   ├── atlas_monitor
│   │   ├── __init__.py
│   │   ├── atlas_monitor.py
│   │   └── spectator_mock.py
│   ├── ...
├── cmd
│   ├── mfextinit_org.py
└── toplevel
    └── mfextinit_org.py
```

Of importance is the fact that the `metaflow_extensions` package is a namespace package
(an implicit namespace package thus the lack of `__init__.py` file). The import mechanism
will complain if this is not the case.

It is also required to "namespace" your extension under a unique name (your organization for
example -- here we used "org"). Under "org", you can obviously do whatever you want and
provide everything with one distribution/package but you also have the opportunity to use
namespace packages there allowing for different groups within your organization to contribute
to the extensions.

In the structure above, you will notice files starting with `mfextinit_`; these are replacements
for the `__init__.py` files. If you choose to not have namespace packages, all those files
can be named `__init__.py` instead. If not, each `mfextinit_X.py` file must be unique (the system
will complain if not).

### Import mechanism

This section gives a better understanding of the import mechanism present in `extensions_support.py`

#### Distribution and non-distribution packages

`metaflow_extensions` packages installed as a distribution are treated slightly differently because
the import mechanism will import the distributions in an order that respects the dependencies. In other
word, if you have a distribution X that provides `metaflow_extensions` as a top-level
package and that it depends on distribution Y which also provides `metaflow_extensions`,
anything in X will be loaded *after* things in Y.

Non-distribution packages, for example things located in `PYTHONPATH` are always loaded
last.

#### General concept

The import system looks for anything that provides `metaflow_extensions` and will verify
that they respect the syntax for extension packages as described in this document and
will then make them available to the other parts of metaflow.

#### Packaging extensions

By default, when metaflow needs to package itself, it will include all files in
all extensions. You can, however, override this behavior by providing a file named
`mfextmeta_X.py` right under `metaflow_extensions`. This file can include two values
`include_suffixes` and `exclude_suffixes` which should be lists of file suffixes:
- if `include_suffixes` is present, only those files ending in those suffixes are included;
- if `exclude_suffixes` is present, all files except those ending in those suffixes are
  included;
- if both are present, `include_suffixes` is used.

In the future, we may package only relevant extensions.

#### Debugging
To get a better understanding of what the import mechanism is doing, you can set the `METAFLOW_DEBUG_EXT`
environment variable to get a run-down of what the import system is doing.


#### setup.py 

Before delving into the specifics of the overrides, the following is a template that can
be used for the `metaflow_extensions` package’s `setup.py`:


```
version = '0.0.1'

setup(name='mycompany-metaflow',
     version=version,
     description='MyCompany Metaflow',
     author='Author',
     author_email='Email',
     packages=find_namespace_packages(include=["metaflow_extensions.*"]),
     install_requires = [
       # Any dependency your extensions depend on

       # Pinned version of Metaflow
       'metaflow=2.4.3'
     ])
```



#### Configuration overrides

The simplest overrides to provide are those that affect configuration values as provided
in `metaflow_config.py`. You can override any of the values within the original
`metaflow_config.py` and provide additional configuration options using the
`mfextinit_X.py` file in the `config` directory of the customization plugin. Any
value present will override (or, if not already present be imported into the main
configuration file) anything in the base `metaflow_config.py`. Additionally, you can
provide the DEBUG variable (it should be a list) to provide additional debugging
options. As an example:


```
###
# CONFIGURE: Your company specific configuration options can go in
#            this file.
#            Any settings present here will override the ones present in
#            metaflow_config.py. You can also optionally add additional
#            configuration options.
#
#            The entries below are simple examples
###

# EXAMPLE: Force a specific datastore
DEFAULT_DATASTORE = "s3"
# EXAMPLE: Configure the bucket to use
DATASTORE_SYSROOT_S3 = "s3://mycompany/mymetaflowbucket"


###
# CONFIGURE: You can also specify additional debugging options that are
#            activated using the METAFLOW_DEBUG_XXX environment variable. See debug.py
###
DEBUG_OPTIONS = ["myspecialdebug"]

###
# CONFIGURE: You can override any conda dependencies when a Conda environment is created
###
def get_pinned_conda_libs(python_version):
   return {
       "click>=8.0.0",
       "requests=2.24.0"
       # ...
   }
```



#### Exceptions

You can also provide exceptions that extend `MetaflowException` and are integrated
directly in `exceptions.py` in Metaflow. The use for this is to allow exceptions to look
as if they were Metaflow exceptions even if coming from the `metaflow_extensions`
package:


```
from metaflow.exception import MetaflowException

###
# CONFIGURE: Add any additional exception you wish to expose under metaflow.exception
#            here.
###


class MyMFException(MetaflowException):
   headline = "My very own exception"

   def __init__(self):
       super().__init__("Will be accessible as metaflow.exception.MyMFException")
```



#### Top-level, plugins and datatools

These three override points function in the same way and allow you to modify, what is
present, respectively, at the top level of metaflow (things accessed using metaflow.X),
in plugins (accessed using metaflow.plugins.Y) or in the datatools (accessed using
metaflow.datatools.Z). You can use any of the mechanisms described below in any of these
three integration points.


##### Adding an attribute

Everything present in the `mfextinit_X.py` (or `__init__.py`) file in the sub-directory for
`metaflow_extensions.org` will be imported into the respective metaflow module provided the
name does not start with a double underscore. Modules present are also not imported
except as detailed below. As a few examples, this is useful in the top-level directory
as demonstrated below:


```
# Provide functions at the top-level
from ..plugins.longboard.util import get_longboard_path

# Alias certain functions/classes/objects at the top-level
from ..plugins.myplugin.subpackage import SomeClass

# Module aliasing
from ..plugins import myplugin

# json will not be imported as part of metaflow
import json
```


Note that if the attribute exists in the original module, it will be overridden.


##### Module aliasing or hoisting

Modules are an interesting case and their handling is a little different than regular
attributes. In general, modules are ignored when importing except if they are a
submodule of the `metaflow_extensions` package. As shown above, the hosting module is
“hoisted” to be accessible using `metaflow.hosting` instead of just
`metaflow.plugins.hosting`. Note that you can make present any module present in
`metaflow_extensions` (so you could do something like `from ..foobar import foo` to
provide `metaflow.foo`). This can provide additional comfort for your users.

By default, if modules or packages are not referenced in some way in the `__init__.py`
file, they will not be imported. As an example, if you provide a `baz` sub-package in
your `metaflow_extensions` plugins directory, you will not have access to
`metaflow.plugins.baz`. To remedy this, you can provide a special variable
`__mf_promote_submodules__` which is a list of submodules to make visible. All modules
are lazy loaded so only actually loaded on use.


##### Module override

Another feature provided is the possibility to override and redefine a module. Note that
this feature is potentially **dangerous** so you must exercise caution when using it. As
an example, Metaflow provides a conda module. You can choose to override this module by
providing a module with the same name. By default, you override the entire module and
must make sure that it therefore exposes the same attributes and sub-modules expected
from the overridden module. The overridden module is available as `&lt;name>._orig` so,
in the conda example, if you provide a conda module in `metaflow_extensions/plugins`,
accessing `metaflow.plugins.conda` will use the module you provide and the original
module will be present as `metaflow.plugins.conda._orig` (sub modules of the original
are also present as submodules of `_orig`).


#### Additional top-level options

The file __init__.py in toplevel allows the following additional customization:



* Providing a name for the customization using:

    ```
  __mf_customization__ = <name>
  ```


* Providing a version number of the customization package; this can be done in any way
  as long as it is made visible using `__version__`

You can also provide a file called `module_overrides.py` in the toplevel directory and
add imports that are imported ***first*** prior to anything in Metaflow’s `__init__.py`.
Note that anything imported there cannot depend on Metaflow (or anything in it) as
Metaflow will not have been loaded at this point.


#### Additional plugins options

You can provide additional plugins and this is the main way to extend Metaflow. You
should add all your plugins in the plugins directory and, in your `__init__.py` file,
you can provide zero or more of the following variables:
* `FLOW_DECORATORS_DESC`: Flow decorators
* `STEP_DECORATORS_DESC`: Step decorators
* `CLIS_DESC`: Additional CL top-level commands
* `ENVIRONMENTS_DESC`: Environments
* `METADATA_PROVIDERS_DESC`: Metadata providers
* `SIDECARS_DESC`, `LOGGING_SIDECARS_DESC`, `MONITOR_SIDECARS_DESC`: Sidecars (either
  non logging and non monitoring or logging or monitoring
* `AWS_CLIENT_PROVIDERS_DESC`: AWS S3 client providers (to get a client for S3 for
  example)
* `DATASTORES_DESC`: Datastore implementations

In all the cases above, each variable is a `List[Tuple[str, str]]`, the tuple contains:
* as a first element, the name of the plugin
* as a second element, the path to the class implementing the plugin. The path can
  be a relative path.

When loading the customization plugin, Metaflow will override (or extend) the plugins it
has based on the ones provided by the customization framework. A plugin is overridden if
it is equal based on the distinguishing feature (for example, if Metaflow provides a
step plugin with the `name` attribute set to `foobar` and the customization plugin does
too, Metaflow’s plugin will get overridden).

##### Selecting plugins/commands
You can also select the plugins that are visible to users of your extension. There are
two ways to configure which plugins are visible. We will use the example of step-decorators
but the same concept applies to all the plugins as well as the commands.

By default, all step-decorators defined by Metaflow and in any of the installed extensions
are enabled. Two variables can control this however:
* `ENABLED_STEP_DECORATOR` which is a list of enabled step-decorators
* `TOGGLE_STEP_DECORATOR` which is a list of toggled step-decorators where `+<step-decorator>`
  enables a decorator and `-<step-decorator>` disables it.

The `ENABLED_STEP_DECORATOR` can be set:
* by the user using an environment variable `METAFLOW_ENABLED_STEP_DECORATOR` or
  a configuration
* by any extension installed.

The latest value takes precedence (ie: extensions override what the users set and the
later loaded extension overrides previously loaded ones).

The `TOGGLE_STEP_DECORATOR` can be set by any extension and it forms an append list (so
all extensions can contribute to the list). It should be set in the same file as
`STEP_DECORATORS_DESC` for example.

The final set of step-decorators that are enabled is determined as follows:
* if `ENABLED_STEP_DECORATOR` is set: use that list
* if not, start with the list of all step-decorators (from core Metaflow and
  any extension) and apply the toggle rules previously described.
