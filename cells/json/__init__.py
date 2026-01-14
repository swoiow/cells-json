"""JSON 序列化工具模块

提供通用的 JSON 序列化能力，处理 Python 中常见的序列化问题：
- datetime/date 对象序列化
- Decimal 对象序列化
- UUID 对象序列化
- numpy 数组序列化
- 自定义对象的序列化
- 复杂数据结构的序列化
- 多种 JSON 后端支持（json、orjson）
"""

from .adapter import dumps, JSONAdapter, loads
from .exceptions import CircularReferenceError, JSONSerializationError, UnsupportedTypeError
from .serializer import safe_json_dumps, UniversalSerializer


__all__ = [
    # 核心序列化器
    "UniversalSerializer",
    "safe_json_dumps",
    # 异常类
    "JSONSerializationError",
    "CircularReferenceError",
    "UnsupportedTypeError",
    # 适配器（支持多种 JSON 后端）
    "JSONAdapter",
    "dumps",
    "loads",
]
