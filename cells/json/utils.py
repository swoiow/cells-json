"""JSON 序列化辅助工具模块

提供便捷的装饰器和辅助函数。
"""

from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

from cells.json.serializer import safe_json_dumps, UniversalSerializer


T = TypeVar("T")


class JsonSerializable:
    """可序列化的基类

    子类可以通过继承此类获得自动的 JSON 序列化能力。

    Example:
        >>> class User(JsonSerializable):
        ...     def __init__(self, name, age):
        ...         self.name = name
        ...         self.age = age
        ...
        >>> user = User("Alice", 25)
        >>> user.to_json()
        '{"name": "Alice", "age": 25}'
    """

    def to_dict(self) -> dict:
        """将对象转换为字典

        :return: 对象的字典表示
        """
        result = {}
        if hasattr(self, "__dict__"):
            result.update(self.__dict__)
        return result

    def to_json(self, **kwargs: Any) -> str:
        """将对象序列化为 JSON 字符串

        :param kwargs: json.dumps 的额外参数
        :return: JSON 字符串
        """
        serializer = UniversalSerializer()
        return serializer.dumps(self.to_dict(), **kwargs)

    @classmethod
    def from_dict(cls: type[T], data: dict) -> T:
        """从字典创建对象

        :param data: 包含对象数据的字典
        :return: 创建的对象实例
        """
        return cls(**data)


def json_serializable(cls: type[T]) -> type[T]:
    """类装饰器，使类具有 JSON 序列化能力

    Example:
        >>> @json_serializable
        ... class Point:
        ...     def __init__(self, x, y):
        ...         self.x = x
        ...         self.y = y
        ...
        >>> point = Point(10, 20)
        >>> point.to_json()
        '{"x": 10, "y": 20}'
    """

    original_init = cls.__init__

    @wraps(original_init)
    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)

    def to_dict(self) -> dict:
        """将对象转换为字典"""
        result = {}
        if hasattr(self, "__dict__"):
            result.update(self.__dict__)
        elif hasattr(self, "__slots__"):
            for slot in self.__slots__:
                if hasattr(self, slot):
                    result[slot] = getattr(self, slot)
        return result

    def to_json(self, **kwargs: Any) -> str:
        """将对象序列化为 JSON 字符串"""
        serializer = UniversalSerializer()
        return serializer.dumps(self.to_dict(), **kwargs)

    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建对象"""
        return cls(**data)

    cls.__init__ = __init__
    cls.to_dict = to_dict
    cls.to_json = to_json
    cls.from_dict = from_dict

    return cls


def save_json(data: Any, filepath: str | Path, **kwargs: Any) -> None:
    """将数据保存为 JSON 文件

    :param data: 待保存的数据
    :param filepath: 文件路径
    :param kwargs: json.dump 的额外参数
    :raises JSONSerializationError: 如果序列化失败

    Example:
        >>> data = {"name": "Alice", "age": 25}
        >>> save_json(data, "user.json")
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    serializer = UniversalSerializer()
    with open(filepath, "w", encoding="utf-8") as f:
        serializer.dump(data, f, **kwargs)


def load_json(filepath: str | Path, **kwargs: Any) -> Any:
    """从 JSON 文件加载数据

    :param filepath: 文件路径
    :param kwargs: json.load 的额外参数
    :return: 加载的数据

    Example:
        >>> data = load_json("user.json")
        >>> print(data)
        {'name': 'Alice', 'age': 25}
    """
    import json

    filepath = Path(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f, **kwargs)


def prettify_json(data: Any, indent: int = 2, **kwargs: Any) -> str:
    """格式化 JSON 字符串（美化输出）

    :param data: 待序列化的数据
    :param indent: 缩进空格数，默认为 2
    :param kwargs: json.dumps 的额外参数
    :return: 格式化后的 JSON 字符串

    Example:
        >>> data = {"name": "Alice", "age": 25}
        >>> print(prettify_json(data))
        {
          "name": "Alice",
          "age": 25
        }
    """
    kwargs.setdefault("ensure_ascii", False)
    kwargs.setdefault("sort_keys", False)
    return safe_json_dumps(data, indent=indent, **kwargs)
