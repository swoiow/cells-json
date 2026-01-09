"""JSON 序列化器核心模块

提供通用的 JSON 序列化器，支持多种 Python 数据类型的序列化。
"""

import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Set
from uuid import UUID

from cells.json.exceptions import CircularReferenceError, JSONSerializationError


try:
    import numpy as np


    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import pandas as pd


    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


class UniversalSerializer:
    """通用 JSON 序列化器

    提供灵活的类型序列化能力，支持以下类型：
    - datetime/date/time/timedelta: 转换为 ISO 格式字符串
    - Decimal: 转换为 float
    - UUID: 转换为字符串
    - Enum: 转换为 value
    - Path: 转换为字符串
    - numpy 数组: 转换为列表
    - pandas Series/DataFrame: 转换为 dict/list
    - 带有 to_dict 方法的对象: 调用 to_dict()
    - 其他对象: 使用 __dict__ 属性

    Example:
        >>> serializer = UniversalSerializer()
        >>> serializer.dumps({"time": datetime.now()})
        '{"time": "2024-01-01T12:00:00"}'
    """

    def __init__(
        self,
        default: Optional[Callable[[Any], Any]] = None,
        strict: bool = False,
        ignore_unknown: bool = False,
        fail_on_circular: bool = False,
    ):
        """初始化序列化器

        :param default: 自定义的序列化函数，会在内置处理之后调用
        :param strict: 严格模式，遇到未知类型立即抛出异常
        :param ignore_unknown: 忽略无法序列化的字段，替换为 None
        :param fail_on_circular: 循环引用时抛出异常，默认 False（返回标记字符串）
        """
        self._default = default
        self._strict = strict
        self._ignore_unknown = ignore_unknown
        self._fail_on_circular = fail_on_circular
        self._seen: Set[int] = set()

    def _serialize_datetime(self, obj: datetime) -> str:
        """序列化 datetime 对象

        :param obj: datetime 对象
        :return: ISO 格式字符串
        """
        return obj.isoformat()

    def _serialize_date(self, obj: date) -> str:
        """序列化 date 对象

        :param obj: date 对象
        :return: ISO 格式字符串
        """
        return obj.isoformat()

    def _serialize_time(self, obj: time) -> str:
        """序列化 time 对象

        :param obj: time 对象
        :return: ISO 格式字符串
        """
        return obj.isoformat()

    def _serialize_timedelta(self, obj: timedelta) -> float:
        """序列化 timedelta 对象

        :param obj: timedelta 对象
        :return: 总秒数
        """
        return obj.total_seconds()

    def _serialize_decimal(self, obj: Decimal) -> float:
        """序列化 Decimal 对象

        :param obj: Decimal 对象
        :return: float 值
        """
        return float(obj)

    def _serialize_uuid(self, obj: UUID) -> str:
        """序列化 UUID 对象

        :param obj: UUID 对象
        :return: UUID 字符串
        """
        return str(obj)

    def _serialize_enum(self, obj: Enum) -> Any:
        """序列化 Enum 对象

        :param obj: Enum 对象
        :return: Enum 的值
        """
        return obj.value

    def _serialize_path(self, obj: Path) -> str:
        """序列化 Path 对象

        :param obj: Path 对象
        :return: 路径字符串（使用 POSIX 格式，跨平台兼容）
        """
        return obj.as_posix()

    def _serialize_numpy(self, obj: Any) -> Any:
        """序列化 numpy 对象

        :param obj: numpy 对象
        :return: Python 原生类型
        """
        if not HAS_NUMPY:
            raise JSONSerializationError(obj, "numpy is not installed")

        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.integer, np.int8, np.int16, np.int32, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float16, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        else:
            return obj.item()

    def _serialize_pandas(self, obj: Any) -> Any:
        """序列化 pandas 对象

        :param obj: pandas 对象
        :return: dict 或 list
        """
        if not HAS_PANDAS:
            raise JSONSerializationError(obj, "pandas is not installed")

        if isinstance(obj, pd.DataFrame):
            return obj.to_dict("records")
        elif isinstance(obj, pd.Series):
            # Series.to_dict() 返回 {index: value} 格式
            # 转换为更直观的格式: {name: [values]} 或直接转换为值列表
            if obj.name is not None:
                return {str(obj.name): obj.tolist()}
            else:
                return obj.to_dict()
        else:
            raise JSONSerializationError(obj, f"Unsupported pandas type: {type(obj)}")

    def _serialize_object(self, obj: Any) -> Any:
        """序列化普通对象

        尝试以下方法：
        1. 调用 to_dict() 方法
        2. 使用 __dict__ 属性
        3. 使用 __slots__ 属性

        :param obj: 普通对象
        :return: dict 或原始对象
        :raises CircularReferenceError: 如果 fail_on_circular=True 且检测到循环引用
        """
        # 检查循环引用
        obj_id = id(obj)
        if obj_id in self._seen:
            if self._fail_on_circular:
                # 严格模式：抛出异常
                raise CircularReferenceError(obj)
            else:
                # 宽松模式：返回标记字符串
                return f"<CircularReference {type(obj).__name__}>"
        self._seen.add(obj_id)

        try:
            # 尝试调用 to_dict
            if hasattr(obj, "to_dict") and callable(obj.to_dict):
                result = obj.to_dict()
                if isinstance(result, dict):
                    return {k: self._serialize(v) for k, v in result.items()}
                return result

            # 尝试使用 __dict__
            if hasattr(obj, "__dict__"):
                return {k: self._serialize(v) for k, v in obj.__dict__.items()}

            # 尝试使用 __slots__
            if hasattr(obj, "__slots__"):
                result = {}
                for slot in obj.__slots__:
                    if hasattr(obj, slot):
                        result[slot] = self._serialize(getattr(obj, slot))
                return result

            raise JSONSerializationError(obj)
        finally:
            self._seen.discard(obj_id)

    def _serialize(self, obj: Any) -> Any:
        """递归序列化对象

        :param obj: 待序列化的对象
        :return: 可序列化的 Python 对象
        :raises CircularReferenceError: 如果 fail_on_circular=True 且检测到循环引用
        """
        # 处理 None
        if obj is None:
            return None

        # 处理基本类型
        if isinstance(obj, (str, int, float, bool)):
            return obj

        # 处理 datetime 相关类型
        if isinstance(obj, datetime):
            return self._serialize_datetime(obj)
        if isinstance(obj, date):
            return self._serialize_date(obj)
        if isinstance(obj, time):
            return self._serialize_time(obj)
        if isinstance(obj, timedelta):
            return self._serialize_timedelta(obj)

        # 处理 Decimal
        if isinstance(obj, Decimal):
            return self._serialize_decimal(obj)

        # 处理 UUID
        if isinstance(obj, UUID):
            return self._serialize_uuid(obj)

        # 处理 Enum
        if isinstance(obj, Enum):
            return self._serialize_enum(obj)

        # 处理 Path
        if isinstance(obj, Path):
            return self._serialize_path(obj)

        # 处理 numpy
        if HAS_NUMPY and isinstance(obj, np.generic) or (
            hasattr(obj, "__class__") and obj.__class__.__module__ == "numpy"
        ):
            return self._serialize_numpy(obj)

        # 处理 pandas
        if HAS_PANDAS:
            if isinstance(obj, (pd.DataFrame, pd.Series)):
                return self._serialize_pandas(obj)

        # 处理字典
        if isinstance(obj, dict):
            return {k: self._serialize(v) for k, v in obj.items()}

        # 处理列表/元组/集合
        if isinstance(obj, (list, tuple)):
            return [self._serialize(item) for item in obj]
        if isinstance(obj, set):
            return [self._serialize(item) for item in obj]

        # 处理普通对象
        try:
            return self._serialize_object(obj)
        except JSONSerializationError:
            if self._strict:
                raise
            if self._ignore_unknown:
                return None
            if self._default:
                return self._default(obj)
            raise

    def default(self, obj: Any) -> Any:
        """JSON encoder 的 default 方法

        :param obj: 待序列化的对象
        :return: 可序列化的值
        :raises JSONSerializationError: 如果对象无法被序列化
        :raises CircularReferenceError: 如果 fail_on_circular=True 且检测到循环引用
        """
        return self._serialize(obj)

    def dumps(self, obj: Any, **kwargs: Any) -> str:
        """将对象序列化为 JSON 字符串

        :param obj: 待序列化的对象
        :param kwargs: json.dumps 的额外参数
        :return: JSON 字符串
        :raises JSONSerializationError: 如果序列化失败
        :raises CircularReferenceError: 如果 fail_on_circular=True 且检测到循环引用
        """
        # 禁用 json.dumps 的循环引用检测，因为我们已经在 _serialize 中处理了
        kwargs.setdefault("check_circular", False)
        try:
            return json.dumps(obj, default=self.default, **kwargs)
        except (TypeError, ValueError) as e:
            raise JSONSerializationError(obj, str(e)) from e

    def dump(self, obj: Any, fp, **kwargs: Any) -> None:
        """将对象序列化并写入文件

        :param obj: 待序列化的对象
        :param fp: 文件对象
        :param kwargs: json.dump 的额外参数
        :raises JSONSerializationError: 如果序列化失败
        :raises CircularReferenceError: 如果 fail_on_circular=True 且检测到循环引用
        """
        # 禁用 json.dump 的循环引用检测
        kwargs.setdefault("check_circular", False)
        try:
            json.dump(obj, fp, default=self.default, **kwargs)
        except (TypeError, ValueError) as e:
            raise JSONSerializationError(obj, str(e)) from e


def universal_serializer(obj: Any) -> Any:
    """通用的序列化函数

    这是一个独立的函数版本，方便作为 json.dumps 的 default 参数使用。

    :param obj: 待序列化的对象
    :return: 可序列化的值
    :raises TypeError: 如果对象无法被序列化

    Example:
        >>> import json
        >>> data = {"time": datetime.now(), "amount": Decimal("10.5")}
        >>> json.dumps(data, default=universal_serializer)
        '{"time": "2024-01-01T12:00:00", "amount": 10.5}'
    """
    serializer = UniversalSerializer()
    try:
        return serializer.default(obj)
    except JSONSerializationError as e:
        raise TypeError(str(e)) from e


def safe_json_dumps(
    data: Any,
    fail_on_circular: bool = True,
    **kwargs: Any,
) -> str:
    """安全的 JSON 序列化函数

    使用 UniversalSerializer 进行序列化，如果失败则返回空对象或默认值。

    :param data: 待序列化的数据
    :param fail_on_circular: 循环引用时抛出异常，默认 False（返回标记字符串）
    :param kwargs: json.dumps 的额外参数
    :return: JSON 字符串
    :raises JSONSerializationError: 如果序列化失败且未设置 ignore_errors
    :raises CircularReferenceError: 如果 fail_on_circular=True 且检测到循环引用

    Example:
        >>> data = {"time": datetime.now(), "amount": Decimal("10.5")}
        >>> safe_json_dumps(data)
        '{"time": "2024-01-01T12:00:00", "amount": 10.5}'
        >>>
        >>> # 循环引用（默认静默处理）
        >>> a = {}
        >>> a['self'] = a
        >>> safe_json_dumps(a)
        '{"self": "<CircularReference dict>"}'
        >>>
        >>> # 循环引用（严格模式）
        >>> safe_json_dumps(a, fail_on_circular=True)
        CircularReferenceError: Circular reference detected for object of type dict
    """
    ignore_errors = kwargs.pop("ignore_errors", False)
    default_value = kwargs.pop("default_value", "null")

    try:
        serializer = UniversalSerializer(fail_on_circular=fail_on_circular)
        return serializer.dumps(data, **kwargs)
    except JSONSerializationError as e:
        if ignore_errors:
            return default_value
        raise
