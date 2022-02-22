from metaflow.parameters import Parameter as _Parameter


class Parameter(_Parameter):
    def __init__(self, name, **kwargs):
        print("This is my very own parameter")
        super().__init__(name, **kwargs)
