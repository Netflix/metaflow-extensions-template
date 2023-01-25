from metaflow.decorators import FlowDecorator

class FlowDeco(FlowDecorator):
    # `name` must match FLOW_DECORATORS_DESC
    name = "myflowdecorator"
