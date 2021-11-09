###
# CONFIGURE: Name of this extension; will be shown as part of MF's version number as
#            <mf version>+EXTENSION(<extension version>)
###
__mf_extensions__ = "mycompany"

###
# CONFIGURE: Import any subpackages you want to expose directly under metaflow.*.
#            You can make individul objects visible as well as whole submodules
###

# EXAMPLE: Will be accessible as metaflow.my_value
from ..datatools import my_value


###
# CONFIGURE: Override anything present in the __init__.py.
#            This allows you to modify the code base even more invasively. Be careful
#            using this feature as you can potentially cause hard-to-detect breakages.
###
from .parameter_override import Parameter

###
# CONFIGURE: You can also promote anything present in the metaflow_extensions plugin
#            to also be accessible using metaflow.*. For example, listing something like
#            client.client_extension will make metaflow.client.client_extension alias
#            metaflow_extensions.client.client_extension.
###
__mf_promote_submodules__ = []

import pkg_resources

try:
    __version__ = pkg_resources.get_distribution("<package name>").version
except:
    # this happens on remote environments since the job package
    # does not have a version
    __version__ = None
