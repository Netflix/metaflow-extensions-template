from metaflow.exception import MetaflowException

###
# CONFIGURE: Add any additional exception you wish to expose under metaflow.exception
#            here.
###


class MyMFException(MetaflowException):
    headline = "My very own exception"

    def __init__(self):
        super().__init__("Will be accessible as metaflow.exception.MyMFException")
