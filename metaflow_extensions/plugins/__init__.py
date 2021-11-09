###
# CONFIGURE: Define additional plugins here. Your defined plugins will typically fall
#            into one of the categories defined below
###

###
# CONFIGURE: Define any additional CLI-level plugins. As examples, batch and step-functions
#            are two such plugins.
###
def get_plugin_cli():
    return []


###
# CONFIGURE: Flow level decorators; implements FlowDecorator (from decorators.py)
###
FLOW_DECORATORS = []

###
# CONFIGURE: Step level decorators; implements StepDecorator (from decorators.py)
###
STEP_DECORATORS = []

###
# CONFIGURE: Environments; implements MetaflowEnvironment
###
ENVIRONMENTS = []

###
# CONFIGURE: Metadata providers; as examples plugins.metadata.local. Implements MetadataProvider
METADATA_PROVIDERS = []

###
# CONFIGURE: Various sidecars
###
SIDECARS = {"name": None}

LOGGING_SIDECARS = {"name": None}

MONITOR_SIDECARS = {"name": None}

###
# CONFIGURE: Your own AWS client provider
#            Class must implement a static method:
#            get_client(module, with_error=False, params={}, role=None) -> (Client, ClientError)
###
AWS_CLIENT_PROVIDERS = []

###
# CONFIGURE: Similar to datatools, you can make visible under metaflow.plugins.* other
#            submodules not referenced in this file
###
__mf_promote_submodules__ = []
