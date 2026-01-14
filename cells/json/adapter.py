"""适配器模块：支持不同的 JSON 库

支持 json、orjson 等不同的 JSON 序列化库。
---

# 性能对比建议

性能对比（处理复杂对象）：

1. 纯基本类型：
   - orjson >> json （orjson 快 2-3 倍）

2. 混合类型（datetime, Decimal 等）：
   - orjson + use_builtin=True >> json
   - orjson + use_builtin=False ≈ json（自定义序列化）

3. 大量小对象：
   - orjson 的优势更明显

4. 特殊类型（numpy）：
   - 如果 use_builtin=False，两种库都依赖自定义序列化器
   - 如果 use_builtin=True，orjson 可能有优化
"""

import json
from typing import Any, Optional

from .serializer import UniversalSerializer


try:
    import orjson


    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False


class JSONAdapter:
    """JSON 库适配器

    自动适配不同的 JSON 库，统一接口。

    Example:
        >>> adapter = JSONAdapter()  # 自动选择最佳库
        >>> adapter.dumps({"time": datetime.now()})

        >>> adapter = JSONAdapter(backend="json")  # 强制使用标准库
        >>> adapter.dumps({"time": datetime.now()})

        >>> adapter = JSONAdapter(backend="orjson")  # 强制使用 orjson
        >>> adapter.dumps({"time": datetime.now()})
    """

    def __init__(
        self,
        backend: Optional[str] = None,
        use_builtin: bool = True,
        **kwargs: Any,
    ):
        """初始化适配器

        :param backend: 后端库，可选 "auto"（默认）、"json"、"orjson"
        :param use_builtin: 是否使用后端库的内置类型支持
                         - True: orjson 的 datetime 等类型直接处理
                         - False: 统一通过自定义序列化器处理
        :param kwargs: 传递给序列化器的额外参数
        """
        if backend is None:
            backend = "auto"

        if backend == "auto":
            self._use_orjson = HAS_ORJSON
        elif backend == "json":
            self._use_orjson = False
        elif backend == "orjson":
            if not HAS_ORJSON:
                raise RuntimeError("orjson is not installed")
            self._use_orjson = True
        else:
            raise ValueError(f"Unsupported backend: {backend}")

        self._use_builtin = use_builtin
        self._serializer = UniversalSerializer(**kwargs)

    def dumps(self, obj: Any, **kwargs: Any) -> str | bytes:
        """序列化为 JSON 字符串

        :param obj: 待序列化的对象
        :param kwargs: JSON 库的额外参数
        :return: JSON 字符串（str 或 bytes）
        """
        if self._use_orjson:
            return self._orjson_dumps(obj, **kwargs)
        else:
            return self._json_dumps(obj, **kwargs)

    def _json_dumps(self, obj: Any, **kwargs: Any) -> str:
        """使用标准库 json 序列化"""
        kwargs.setdefault("ensure_ascii", False)
        return json.dumps(obj, default=self._serializer.default, **kwargs)

    def _orjson_dumps(self, obj: Any, **kwargs: Any) -> bytes:
        """使用 orjson 序列化"""
        if self._use_builtin:
            # 使用 orjson 内置支持，不传 default
            default = None
        else:
            # 统一使用自定义序列化器
            default = self._serializer.default

        # orjson 默认返回 bytes，不需要 ensure_ascii
        result = orjson.dumps(obj, default=default, **kwargs)
        return result

    def dump(self, obj: Any, fp, **kwargs: Any) -> None:
        """序列化并写入文件

        :param obj: 待序列化的对象
        :param fp: 文件对象
        :param kwargs: JSON 库的额外参数
        """
        if self._use_orjson:
            content = self._orjson_dumps(obj, **kwargs)
            fp.write(content if isinstance(content, bytes) else content.encode())
        else:
            json.dump(obj, fp, default=self._serializer.default, **kwargs)

    def loads(self, s: str | bytes, **kwargs: Any) -> Any:
        """从 JSON 字符串或字节加载数据

        :param s: JSON 字符串或字节
        :param kwargs: JSON 库的额外参数
        :return: 解析后的数据
        """
        if self._use_orjson:
            return orjson.loads(s, **kwargs)
        else:
            return json.loads(s, **kwargs)

    def load(self, fp, **kwargs: Any) -> Any:
        """从文件加载数据

        :param fp: 文件对象
        :param kwargs: JSON 库的额外参数
        :return: 解析后的数据
        """
        if self._use_orjson:
            return orjson.loads(fp.read())
        else:
            return json.load(fp, **kwargs)


def dumps(obj: Any, backend: str = "auto", use_builtin: bool = True, **kwargs: Any) -> str | bytes:
    """便捷的序列化函数

    :param obj: 待序列化的对象
    :param backend: 后端库，"auto"、"json" 或 "orjson"
    :param use_builtin: 是否使用后端库的内置类型支持
    :param kwargs: JSON 库的额外参数
    :return: JSON 字符串（str 或 bytes）

    Example:
        >>> import orjson
        >>> from datetime import datetime
        >>>
        >>> # 使用 orjson 内置支持
        >>> result = dumps({"time": datetime.now()}, backend="orjson", use_builtin=True)
        >>> isinstance(result, bytes)
        True
        >>>
        >>> # 使用自定义序列化器
        >>> result = dumps({"time": datetime.now()}, backend="orjson", use_builtin=False)
        >>> isinstance(result, bytes)
        True
    """
    adapter = JSONAdapter(backend=backend, use_builtin=use_builtin, **kwargs)
    return adapter.dumps(obj)


def loads(s: str | bytes, backend: str = "auto", **kwargs: Any) -> Any:
    """便捷的反序列化函数

    :param s: JSON 字符串或字节
    :param backend: 后端库，"auto"、"json" 或 "orjson"
    :param kwargs: JSON 库的额外参数
    :return: 解析后的数据
    """
    adapter = JSONAdapter(backend=backend)
    return adapter.loads(s, **kwargs)
