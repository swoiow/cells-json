"""适配器模块：支持不同的 JSON 库。

支持 json、orjson 等不同的 JSON 序列化库。
"""

import json
from functools import lru_cache
from typing import Any, Optional, Tuple, Union

from .exceptions import CircularReferenceError, JSONDecodeError, JSONEncodeError
from .serializer import UniversalSerializer


try:
    import orjson


    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False
    orjson = None

# 后端可能抛出的原生编码异常
_NATIVE_ENCODE_EXCEPTIONS: Tuple[type[Exception], ...] = (TypeError, ValueError)


class JSONAdapter:
    """JSON 库适配器。

    自动适配不同的 JSON 库，并提供统一的接口。

    Examples:
        ```python
        adapter = JSONAdapter(backend="auto")
        data = {"key": "value", "date": datetime.now()}
        json_str = adapter.dumps(data)
        ```
    """

    def __init__(
        self,
        backend: Optional[str] = None,
        use_builtin: bool = True,
        **kwargs: Any,
    ):
        """初始化适配器。

        Args:
            backend: 后端库名称。可选 "auto" (自动选择)、"json" (强制标准库) 或 "orjson" (强制 orjson)。
            use_builtin: 是否使用后端库的内置类型支持。仅对 orjson 有效。
            **kwargs: 传递给序列化器的参数，如 strict, ignore_unknown, default。

        Raises:
            RuntimeError: 当强制指定 "orjson" 但环境未安装时抛出。
            ValueError: 当指定了不支持的后端时抛出。
        """
        if backend is None or backend == "auto":
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

        # 预计算 orjson 选项，避免每次序列化时的 getattr 开销
        self._orjson_option = 0
        if self._use_orjson and self._use_builtin:
            for opt_name in ["OPT_SERIALIZE_DATETIME", "OPT_NON_STR_KEYS", "OPT_SERIALIZE_NUMPY"]:
                self._orjson_option |= getattr(orjson, opt_name, 0)

    def dumps(self, obj: Any, ensure_str: bool = True, **kwargs: Any) -> Union[str, bytes]:
        """将对象序列化为 JSON 字符串或字节。

        Args:
            obj: 待序列化的 Python 对象。
            ensure_str: 是否强制返回字符串。默认为 True。
            **kwargs: 传递给底层后端 dumps 方法的额外参数。

        Returns:
            Union[str, bytes]: 默认返回字符串。如果 ensure_str 为 True 则返回字符串。

        Raises:
            JSONEncodeError: 序列化过程中发生错误时抛出。
            CircularReferenceError: 检测到循环引用时抛出。

        Examples:
            ```python
            adapter = JSONAdapter()
            adapter.dumps({"a": 1, "b": 2}, indent=2)
            # '{\n  "a": 1,\n  "b": 2\n}'
            ```
        """
        try:
            if self._use_orjson:
                res = self._orjson_dumps(obj, **kwargs)
            else:
                res = self._json_dumps(obj, **kwargs)

            if ensure_str and isinstance(res, bytes):
                return res.decode("utf-8")
            return res
        except (JSONEncodeError, CircularReferenceError):
            raise
        except _NATIVE_ENCODE_EXCEPTIONS as e:
            raise JSONEncodeError(obj, str(e)) from e

    def _json_dumps(self, obj: Any, **kwargs: Any) -> str:
        """使用标准库 json 进行序列化。

        Args:
            obj: 待序列化的对象。
            **kwargs: 额外参数。

        Returns:
            str: 序列化后的字符串。
        """
        kwargs.setdefault("ensure_ascii", False)
        return json.dumps(obj, default=self._serializer.default, **kwargs)

    def _orjson_dumps(self, obj: Any, **kwargs: Any) -> bytes:
        """使用 orjson 进行高性能序列化。

        Args:
            obj: 待序列化的对象。
            **kwargs: 额外参数。

        Returns:
            bytes: 序列化后的字节流。
        """
        option = kwargs.pop("option", self._orjson_option)
        if option != self._orjson_option:
            option |= self._orjson_option

        return orjson.dumps(obj, default=self._serializer.default, option=option, **kwargs)

    def dump(self, obj: Any, fp, **kwargs: Any) -> None:
        """序列化并将结果写入文件。

        Args:
            obj: 待序列化的对象。
            fp: 支持 write 方法的文件类对象。
            **kwargs: 序列化参数。
        """
        res = self.dumps(obj, ensure_str=False, **kwargs)
        if isinstance(res, str):
            fp.write(res)
        else:
            fp.write(res.decode("utf-8") if hasattr(fp, "encoding") and fp.encoding else res)

    def loads(self, s: Union[str, bytes], **kwargs: Any) -> Any:
        """将 JSON 字符串或字节反序列化为 Python 对象。

        Args:
            s: JSON 字符串或字节。
            **kwargs: 额外参数。

        Returns:
            Any: 反序列化后的 Python 对象。

        Raises:
            JSONDecodeError: 解码失败时抛出。

        Examples:
            ```python
            adapter = JSONAdapter()
            adapter.loads('{"a": 1}')
            # {'a': 1}
            ```
        """
        try:
            return orjson.loads(s) if self._use_orjson else json.loads(s, **kwargs)
        except (json.JSONDecodeError, getattr(orjson, "JSONDecodeError", json.JSONDecodeError)) as e:
            # 统一包装解码异常
            raise JSONDecodeError(str(e), getattr(e, "doc", ""), getattr(e, "pos", 0)) from e

    def load(self, fp, **kwargs: Any) -> Any:
        """从文件中读取并反序列化 JSON 数据。

        Args:
            fp: 支持 read 方法的文件类对象。
            **kwargs: 额外参数。

        Returns:
            Any: 反序列化后的 Python 对象。
        """
        return self.loads(fp.read(), **kwargs)


# 1. 固化核心逻辑：使用标准 LRU 缓存 (线程安全，自动淘汰)
@lru_cache(maxsize=32)
def _create_adapter(backend: str, config_items: tuple) -> JSONAdapter:
    """底层工厂函数，被 lru_cache 装饰以实现对象重用。"""
    return JSONAdapter(backend=backend, **dict(config_items))


# 默认单例
_DEFAULT_ADAPTER = JSONAdapter(backend="auto")

# 配置项白名单
_CONFIG_KEYS = {"use_builtin", "strict", "ignore_unknown", "fail_on_circular", "use_dict", "default"}


def _get_adapter(backend: str = "auto", **config: Any) -> JSONAdapter:
    """获取适配器的入口逻辑。"""
    if backend == "auto" and not config:
        return _DEFAULT_ADAPTER

    try:
        # 将配置字典转换为可哈希的元组，以便 lru_cache 识别
        config_items = tuple(sorted(config.items()))
        return _create_adapter(backend, config_items)
    except (TypeError, AttributeError):
        # 逃生路径：如果包含不可哈希对象（如 lambda），降级为直接创建
        return JSONAdapter(backend=backend, **config)


def dumps(obj: Any, backend: str = "auto", **kwargs: Any) -> str:
    """序列化为 JSON 字符串。

    Args:
        obj: 待序列化的对象。
        backend: 使用的后端，默认为 auto；支持：auto, json, orjson。
        **kwargs: 额外参数。支持:
            - 配置类: use_builtin, strict, ignore_unknown, fail_on_circular, use_dict, default
            - 运行类: indent, ensure_ascii, ensure_str, sort_keys 等

    Returns:
        str: 默认返回字符串。

    Examples:
        ```python
        from cells.json import dumps
        dumps({"a": 1})
        # '{"a": 1}'
        ```
    """
    # 1. 剥离配置类参数
    config = {k: kwargs.pop(k) for k in _CONFIG_KEYS if k in kwargs}

    # 2. 处理包装层特有参数
    ensure_str = kwargs.pop("ensure_str", True)

    # 3. 获取（缓存的）适配器
    adapter = _get_adapter(backend=backend, **config)

    # 4. 执行序列化，剩余的 kwargs (如 indent) 透传给底层 dumps 方法
    return adapter.dumps(obj, ensure_str=ensure_str, **kwargs)


def loads(s: Union[str, bytes], backend: str = "auto", **kwargs: Any) -> Any:
    """快捷反序列化函数。

    Args:
        s: JSON 字符串或字节。
        backend: 使用的后端，默认为 "auto"。
        **kwargs: 额外参数。

    Returns:
        Any: 反序列化结果。

    Examples:
        ```python
        from cells.json import loads
        loads('{"a": 1}')
        # {'a': 1}
        ```
    """
    adapter = _get_adapter(backend=backend)
    return adapter.loads(s, **kwargs)
