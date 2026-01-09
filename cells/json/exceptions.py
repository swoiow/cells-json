"""JSON 序列化异常模块

定义 JSON 序列化过程中可能出现的异常。
"""


class JSONSerializationError(TypeError):
    """JSON 序列化异常

    当对象无法被序列化时抛出此异常。

    :param obj: 无法序列化的对象
    :param message: 错误消息，默认会自动生成包含类型信息的消息

    Example:
        >>> raise JSONSerializationError(complex_object)
        JSONSerializationError: Object of type ComplexType is not JSON serializable
    """

    def __init__(self, obj, message: str = None):
        self.obj = obj
        self.obj_type = type(obj)
        if message is None:
            message = f"Object of type {self.obj_type.__name__} is not JSON serializable"
        super().__init__(message)


class CircularReferenceError(JSONSerializationError):
    """循环引用异常

    当检测到循环引用时抛出此异常。

    :param obj: 引用循环的对象
    :param path: 引用路径

    Example:
        >>> a = {}
        >>> a['self'] = a
        >>> serializer.dumps(a)  # 可能抛出 CircularReferenceError
    """

    def __init__(self, obj, path: str = ""):
        message = f"Circular reference detected for object of type {type(obj).__name__}"
        if path:
            message += f" at path: {path}"
        super().__init__(obj, message)
        self.path = path


class UnsupportedTypeError(JSONSerializationError):
    """不支持类型异常

    当遇到无法处理的类型时抛出此异常。

    :param obj: 不支持的对象
    :param hint: 提示信息，说明如何处理该类型

    Example:
        >>> raise UnsupportedTypeError(custom_obj, hint="Add a to_dict() method")
    """

    def __init__(self, obj, hint: str = ""):
        message = f"Unsupported type: {type(obj).__name__}"
        if hint:
            message += f". {hint}"
        super().__init__(obj, message)
        self.hint = hint
