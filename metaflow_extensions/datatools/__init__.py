###
# CONFIGURE: You can add additional datatools which will be made available to the user
#            as metaflow.datatools.*. In this example, a user would be able to import
#            metaflow.datatools.my_value (as well as metaflow.datatools.imported.my_value)
###
from .imported import my_value

###
# CONFIGURE: You can also make available sub-modules that are not explicitly referenced
#            here so that metaflow.datatools.non_imported also works. You do this
#            by setting the __mf_promote_submodules__ to a list of submodules to import.
#            Note that the name can contain "." and this will import those subpackages
###
__mf_promote_submodules__ = ["non_imported"]
