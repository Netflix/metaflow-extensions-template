# Metaflow Extension Framework

## Context

Metaflow is a growing project and, as more companies and partners adopt it, they may
want to develop their own integrations and extensions particularly to better integrate
with their own proprietary systems. This is what we do at Netflix and are therefore able
to use and benefit from the OSS release of Metaflow while still having Metaflow tightly
coupled with our execution environment. This document highlights the approach we use to
achieve this.

**Anything described in this document is not guaranteed to be supported as Metaflow
evolves. Metaflow will not actively break anything described here but internal APIs,
which this approach relies on, are not guaranteed to be stable or backward compatible
like the user-facing APIs. This is not meant for the casual user. Please let us know of
your use case if you choose to proceed.**


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
metaflow_extensions
├── __init__.py
├── config
│   ├── __init__.py
│   └── metaflow_config.py
├── datatools
│   └── __init__.py
├── exceptions
│   └── __init__.py
├── plugins
│   ├── __init__.py
│   ├── env_escape
│   │   ├── configurations
│   │   └── __init__.py
│   ├── atlas_monitor
│   │   ├── __init__.py
│   │   ├── atlas_monitor.py
│   │   └── spectator_mock.py
│   ├── ...
└── toplevel
    └── __init__.py
```


Note that it is preferable to at least provide the `__init__.py` files as well as the
`metaflow_config.py` file even if they are empty. 


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
     packages=find_packages(),
     py_modules=['metaflow_extensions', ],
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
`metaflow_config.py` file in the `config` directory of the customization plugin. Any
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

Everything present in the `__init__.py` file in the sub-directory for
`metaflow_extensions` will be imported into the respective metaflow module provided the
name does not start with a double underscore. Modules present are also not imported
except as detailed below. As a few examples, this is useful in the top-level directory
as demonstrated below:


```
# Provide functions at the TL
from ..plugins.longboard.util import get_longboard_path

# Alias certain functions/classes/objects at the TL
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
module will be present as `metaflow.plugins.conda._orig`.


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
you need to provide the following variables and functions:



* `get_plugin_cli()`: This function should return a list of CLIs that are to extend
  Metaflow’s CLI. An example of such a CLI is batch.
* `FLOW_DECORATORS`: This variable should contain a list of flow level decorators (ie:
  classes that extend `FlowDecorator`). Flow-level decorators are distinguished based on
  their `name` attribute.
* `STEP_DECORATORS`: This variable should contain a list of step level decorators (ie:
  classes that extend `StepDecorator`). Step-level decorators are distinguished based on
  their `name` attribute.
* `ENVIRONMENTS`: This variable should contain a list of environments (ie: classes that
  extend `MetaflowEnvironment`). Environments are distinguished based on their `TYPE`
  attribute.
* `METADATA_PROVIDERS`: This variable should contain a list of metadata providers (ie:
  classes that extend `MetadataProvider`). Metadata providers are distinguished based on
  their `TYPE` attribute.
* `SIDECARS`, `LOGGING_SIDECARS` and `MONITOR_SIDECARS`: These variables should contain
  dictionaries of sidecars (either logging, monitoring or neither). Note that you do not
  need to add the logging or monitoring sidecars explicitly to the `SIDECARS` variable.
* `AWS_CLIENT_PROVIDERS`: This variable should contain a list of classes implementing a
  static method `get_client` just like `Boto3ClientProvider`. Client providers are
  distinguished based on their `name` attribute.
* (coming soon) `DATASTORES`: in the convergence branch, the lower level of the
  datastore (so the part that talks to S3 or the part that talks to the filesystem) will
  be moved out to the plugins directory in the same way the metadata providers were
  moved out.

When loading the customization plugin, Metaflow will override (or extend) the plugins it
has based on the ones provided by the customization framework. A plugin is overridden if
it is equal based on the distinguishing feature (for example, if Metaflow provides a
step plugin with the `name` attribute set to `foobar` and the customization plugin does
too, Metaflow’s plugin will get overridden).
