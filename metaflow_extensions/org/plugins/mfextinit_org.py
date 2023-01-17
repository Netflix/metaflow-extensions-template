###
# CONFIGURE: Define additional plugins here. Your defined plugins will typically fall
#            into one of the categories defined below
###

from metaflow.extension_support.plugins import process_plugins_description

###
# CONFIGURE: Define any additional CLI-level plugins. As examples, batch and step-functions
#            are two such plugins.
###
CLIS_DESC = []

###
# CONFIGURE: Flow level decorators; implements FlowDecorator (from decorators.py)
###
# `name` field must match first element of tuple
FLOW_DECORATORS_DESC = [("myflowdecorator", ".my_decorators.FlowDecorator")]

###
# CONFIGURE: Step level decorators; implements StepDecorator (from decorators.py)
###
# `name` field must match first element of tuple
STEP_DECORATORS_DESC = []

###
# CONFIGURE: Environments; implements MetaflowEnvironment
###
# `TYPE` field must match first element of tuple
ENVIRONMENTS_DESC = []

###
# CONFIGURE: Datastores; implements DataStoreStorage
###
# `TYPE` field must match first element of tuple
DATASTORES_DESC = []

###
# CONFIGURE: Metadata providers; as examples plugins.metadata.local. Implements MetadataProvider
###
# `TYPE` field must match first element of tuple
METADATA_PROVIDERS_DESC = []

###
# CONFIGURE: Various sidecars
###
# Sidecars do not have a field corresponding to their name
SIDECARS_DESC = []

LOGGING_SIDECARS_DESC = [] 

MONITOR_SIDECARS_DESC = []

###
# CONFIGURE: Your own AWS client provider
#            Class must implement a static method:
#            get_client(module, with_error=False, params={}, role=None) -> (Client, ClientError)
###
# `name` field must match first element of tuple
AWS_CLIENT_PROVIDERS_DESC = []

###
# Toggle decorators
###
# EXAMPLE: This example disables the kubernetes step decorator
TOGGLE_STEP_DECORATOR = [
    "-kubernetes"
]

###
# Force a certain set of decorators
###
# EXAMPLE: This example sets a given set of decorators and will ignore all toggles and
# user settings
ENABLED_STEP_DECORATOR = ["batch", "airflow_internal"]


# Do *NOT* forget this line
process_plugins_description()

###
# CONFIGURE: Similar to datatools, you can make visible under metaflow.plugins.* other
#            submodules not referenced in this file
###
__mf_promote_submodules__ = []
