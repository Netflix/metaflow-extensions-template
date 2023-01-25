###
# CONFIGURE: Your company specific configuration options can go in this file.
#            Any settings present here will override the ones present in
#            metaflow_config.py. You can also optionally add additional configuration
#            options.
#
#            The entries below are simple examples
###

from metaflow.metaflow_config_funcs import from_conf

# EXAMPLE: Force a specific datastore
DEFAULT_DATASTORE = "s3"

# EXAMPLE: Configure the bucket to use
DATASTORE_SYSROOT_S3 = "s3://mycompany/mymetaflowbucket"

# EXAMPLE: use from_conf to correctly allow values from the environment/configuration file

DEFAULT_METADATA = from_conf("DEFAULT_METADATA", "mymetadata") 

###
# CONFIGURE: You can also specify additional debugging options that are
#            activated using the METAFLOW_DEBUG_XXX environment variable. See debug.py
###
DEBUG_OPTIONS = ["myspecialdebug"]

###
# CONFIGURE: You can override any conda dependencies when a Conda environment is created
###
def get_pinned_conda_libs(python_version, datastore_type):
    return {
        "click>=8.0.0",
        "requests=2.24.0"
        # ...
    }
