"""JSON adapter with stdlib-shaped APIs and orjson-first behavior."""

from __future__ import annotations

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


_NATIVE_ENCODE_EXCEPTIONS: Tuple[type[Exception], ...] = (TypeError, ValueError)
_SERIALIZER_CONFIG_KEYS = {
    "strict",
    "ignore_unknown",
    "fail_on_circular",
    "use_dict",
}
_ORJSON_SAFE_DUMPS_KWARGS = {"default"}
_ORJSON_SAFE_LOADS_KWARGS = set()
_JSON_BASIC_KEY_TYPES = (str, int, float, bool, type(None))


def _escape_codepoint_for_json_ascii(character: str) -> str:
    codepoint = ord(character)
    if codepoint <= 0xFFFF:
        return f"\\u{codepoint:04x}"

    codepoint -= 0x10000
    high_surrogate = 0xD800 + (codepoint >> 10)
    low_surrogate = 0xDC00 + (codepoint & 0x3FF)
    return f"\\u{high_surrogate:04x}\\u{low_surrogate:04x}"


def _ensure_ascii_json_text(json_text: str) -> str:
    if json_text.isascii():
        return json_text

    ascii_chunks: list[str] = []
    for character in json_text:
        if character.isascii():
            ascii_chunks.append(character)
            continue
        ascii_chunks.append(_escape_codepoint_for_json_ascii(character))
    return "".join(ascii_chunks)


def _ensure_ascii_json_bytes(json_bytes: bytes) -> bytes:
    if json_bytes.isascii():
        return json_bytes
    return _ensure_ascii_json_text(json_bytes.decode("utf-8")).encode("ascii")


def _raise_orjson_parameter_error(function_name: str, parameter_name: str) -> None:
    raise TypeError(
        f"{function_name}() does not support parameter '{parameter_name}' with the active orjson backend. "
        f"Use backend=\"json\" for stdlib-compatible handling."
    )


def _is_json_basic_key(key: Any) -> bool:
    return isinstance(key, _JSON_BASIC_KEY_TYPES)


def _filter_unsupported_keys(obj: Any) -> Any:
    if isinstance(obj, dict):
        filtered_dict: dict[Any, Any] = {}
        for key, value in obj.items():
            if not _is_json_basic_key(key):
                continue
            filtered_dict[key] = _filter_unsupported_keys(value)
        return filtered_dict
    if isinstance(obj, list):
        return [_filter_unsupported_keys(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(_filter_unsupported_keys(item) for item in obj)
    if isinstance(obj, set):
        return {_filter_unsupported_keys(item) for item in obj}
    return obj


def _is_default_json_encoder(cls: Any) -> bool:
    return cls is None or cls is json.JSONEncoder


def _is_default_json_decoder(cls: Any) -> bool:
    return cls is None or cls is json.JSONDecoder


def _validate_orjson_dumps_parameters(
    *,
    skipkeys: bool,
    check_circular: bool,
    allow_nan: bool,
    cls: Any,
    indent: Any,
    separators: Any,
    sort_keys: bool,
    extra_kwargs: dict[str, Any],
) -> int:
    option = 0
    if not allow_nan:
        _raise_orjson_parameter_error("dumps", "allow_nan")
    if not _is_default_json_encoder(cls):
        _raise_orjson_parameter_error("dumps", "cls")
    if indent is not None:
        if indent == 2:
            option |= getattr(orjson, "OPT_INDENT_2", 0)
        else:
            _raise_orjson_parameter_error("dumps", "indent")
    if separators is not None:
        if separators != (",", ":"):
            _raise_orjson_parameter_error("dumps", "separators")
    if sort_keys:
        option |= getattr(orjson, "OPT_SORT_KEYS", 0)
    unsupported_keys = [key for key in extra_kwargs if key not in _ORJSON_SAFE_DUMPS_KWARGS]
    if unsupported_keys:
        _raise_orjson_parameter_error("dumps", unsupported_keys[0])
    return option


def _validate_orjson_loads_parameters(
    *,
    cls: Any,
    object_hook: Any,
    parse_float: Any,
    parse_int: Any,
    parse_constant: Any,
    object_pairs_hook: Any,
    extra_kwargs: dict[str, Any],
) -> None:
    if not _is_default_json_decoder(cls):
        _raise_orjson_parameter_error("loads", "cls")
    if object_hook is not None or parse_float is not None or parse_int is not None:
        parameter_name = "object_hook" if object_hook is not None else "parse_float" if parse_float is not None else "parse_int"
        _raise_orjson_parameter_error("loads", parameter_name)
    if parse_constant is not None or object_pairs_hook is not None:
        parameter_name = "parse_constant" if parse_constant is not None else "object_pairs_hook"
        _raise_orjson_parameter_error("loads", parameter_name)
    unsupported_keys = [key for key in extra_kwargs if key not in _ORJSON_SAFE_LOADS_KWARGS]
    if unsupported_keys:
        _raise_orjson_parameter_error("loads", unsupported_keys[0])


class JSONAdapter:
    """Adapter that preserves stdlib-style APIs and can accelerate with orjson."""

    def __init__(
        self,
        backend: Optional[str] = None,
        use_builtin: bool = True,
        **kwargs: Any,
    ) -> None:
        if backend is None or backend == "auto":
            self._backend = "auto"
        elif backend == "json":
            self._backend = "json"
        elif backend == "orjson":
            if not HAS_ORJSON:
                raise RuntimeError("orjson is not installed")
            self._backend = "orjson"
        else:
            raise ValueError(f"Unsupported backend: {backend}")

        self._ensure_str = kwargs.pop("ensure_str", None)
        self._use_builtin = use_builtin
        self._serializer = UniversalSerializer(**kwargs)
        self._orjson_option = 0
        if HAS_ORJSON and self._use_builtin:
            for opt_name in [
                "OPT_SERIALIZE_DATETIME",
                "OPT_NON_STR_KEYS",
                "OPT_SERIALIZE_NUMPY",
            ]:
                self._orjson_option |= getattr(orjson, opt_name, 0)

    def dumps(
        self,
        obj: Any,
        *,
        skipkeys: bool = False,
        ensure_ascii: bool = True,
        check_circular: bool = True,
        allow_nan: bool = True,
        cls: Any = None,
        indent: int | str | None = None,
        separators: tuple[str, str] | None = None,
        default: Any = None,
        sort_keys: bool = False,
        ensure_str: bool = True,
        option: int | None = None,
        **kwargs: Any,
    ) -> Union[str, bytes]:
        ensure_str = self._ensure_str if self._ensure_str is not None else ensure_str
        try:
            if HAS_ORJSON and self._backend != "json":
                validated_option = _validate_orjson_dumps_parameters(
                    skipkeys=skipkeys,
                    check_circular=check_circular,
                    allow_nan=allow_nan,
                    cls=cls,
                    indent=indent,
                    separators=separators,
                    sort_keys=sort_keys,
                    extra_kwargs=kwargs,
                )
                serialized_obj = _filter_unsupported_keys(obj) if skipkeys else obj
                result = self._orjson_dumps(
                    serialized_obj,
                    default=default,
                    option=validated_option if option is None else (option | validated_option),
                    **kwargs,
                )
                if ensure_ascii:
                    result = _ensure_ascii_json_bytes(result)
            else:
                result = self._json_dumps(
                    obj,
                    skipkeys=skipkeys,
                    ensure_ascii=ensure_ascii,
                    check_circular=check_circular,
                    allow_nan=allow_nan,
                    cls=cls,
                    indent=indent,
                    separators=separators,
                    default=default,
                    sort_keys=sort_keys,
                    **kwargs,
                )

            if ensure_str and isinstance(result, bytes):
                return result.decode("utf-8")
            return result
        except (JSONEncodeError, CircularReferenceError):
            raise
        except _NATIVE_ENCODE_EXCEPTIONS as exc:
            raise JSONEncodeError(obj, str(exc)) from exc

    def _json_dumps(
        self,
        obj: Any,
        *,
        skipkeys: bool,
        ensure_ascii: bool,
        check_circular: bool,
        allow_nan: bool,
        cls: Any,
        indent: int | str | None,
        separators: tuple[str, str] | None,
        default: Any,
        sort_keys: bool,
        **kwargs: Any,
    ) -> str:
        effective_default = self._serializer.default if default is None else default
        json_cls = json.JSONEncoder if cls is None else cls
        return json.dumps(
            obj,
            skipkeys=skipkeys,
            ensure_ascii=ensure_ascii,
            check_circular=check_circular,
            allow_nan=allow_nan,
            cls=json_cls,
            indent=indent,
            separators=separators,
            default=effective_default,
            sort_keys=sort_keys,
            **kwargs,
        )

    def _orjson_dumps(
        self,
        obj: Any,
        *,
        default: Any,
        option: int | None,
        **kwargs: Any,
    ) -> bytes:
        effective_option = self._orjson_option if option is None else (option | self._orjson_option)
        effective_default = self._serializer.default if default is None else default
        return orjson.dumps(obj, default=effective_default, option=effective_option, **kwargs)

    def dump(
        self,
        obj: Any,
        fp: Any,
        *,
        skipkeys: bool = False,
        ensure_ascii: bool = True,
        check_circular: bool = True,
        allow_nan: bool = True,
        cls: Any = None,
        indent: int | str | None = None,
        separators: tuple[str, str] | None = None,
        default: Any = None,
        sort_keys: bool = False,
        option: int | None = None,
        **kwargs: Any,
    ) -> None:
        result = self.dumps(
            obj,
            skipkeys=skipkeys,
            ensure_ascii=ensure_ascii,
            check_circular=check_circular,
            allow_nan=allow_nan,
            cls=cls,
            indent=indent,
            separators=separators,
            default=default,
            sort_keys=sort_keys,
            ensure_str=False,
            option=option,
            **kwargs,
        )
        if isinstance(result, str):
            fp.write(result)
            return
        try:
            fp.write(result)
        except TypeError:
            fp.write(result.decode("utf-8"))

    def loads(
        self,
        s: Union[str, bytes, bytearray],
        *,
        cls: Any = None,
        object_hook: Any = None,
        parse_float: Any = None,
        parse_int: Any = None,
        parse_constant: Any = None,
        object_pairs_hook: Any = None,
        **kwargs: Any,
    ) -> Any:
        try:
            if HAS_ORJSON and self._backend != "json":
                _validate_orjson_loads_parameters(
                    cls=cls,
                    object_hook=object_hook,
                    parse_float=parse_float,
                    parse_int=parse_int,
                    parse_constant=parse_constant,
                    object_pairs_hook=object_pairs_hook,
                    extra_kwargs=kwargs,
                )
                return orjson.loads(s)
            return json.loads(
                s,
                cls=cls,
                object_hook=object_hook,
                parse_float=parse_float,
                parse_int=parse_int,
                parse_constant=parse_constant,
                object_pairs_hook=object_pairs_hook,
                **kwargs,
            )
        except (json.JSONDecodeError, getattr(orjson, "JSONDecodeError", json.JSONDecodeError)) as exc:
            raise JSONDecodeError(str(exc), getattr(exc, "doc", ""), getattr(exc, "pos", 0)) from exc

    def load(
        self,
        fp: Any,
        *,
        cls: Any = None,
        object_hook: Any = None,
        parse_float: Any = None,
        parse_int: Any = None,
        parse_constant: Any = None,
        object_pairs_hook: Any = None,
        **kwargs: Any,
    ) -> Any:
        return self.loads(
            fp.read(),
            cls=cls,
            object_hook=object_hook,
            parse_float=parse_float,
            parse_int=parse_int,
            parse_constant=parse_constant,
            object_pairs_hook=object_pairs_hook,
            **kwargs,
        )


@lru_cache(maxsize=32)
def _create_adapter(backend: str, use_builtin: bool, config_items: tuple[tuple[str, Any], ...]) -> JSONAdapter:
    return JSONAdapter(backend=backend, use_builtin=use_builtin, **dict(config_items))


_DEFAULT_ADAPTER = JSONAdapter(backend="auto")


def _extract_serializer_config(kwargs: dict[str, Any]) -> dict[str, Any]:
    config: dict[str, Any] = {}
    for key in _SERIALIZER_CONFIG_KEYS:
        if key in kwargs:
            config[key] = kwargs.pop(key)
    return config


def _get_adapter(
    *,
    backend: str = "auto",
    use_builtin: bool = True,
    config: dict[str, Any] | None = None,
) -> JSONAdapter:
    config = {} if config is None else config
    if backend == "auto" and use_builtin and not config:
        return _DEFAULT_ADAPTER
    try:
        config_items = tuple(sorted(config.items()))
        return _create_adapter(backend, use_builtin, config_items)
    except (TypeError, AttributeError):
        return JSONAdapter(backend=backend, use_builtin=use_builtin, **config)


def dumps(
    obj: Any,
    *,
    skipkeys: bool = False,
    ensure_ascii: bool = True,
    check_circular: bool = True,
    allow_nan: bool = True,
    cls: Any = None,
    indent: int | str | None = None,
    separators: tuple[str, str] | None = None,
    default: Any = None,
    sort_keys: bool = False,
    backend: str = "auto",
    use_builtin: bool = True,
    ensure_str: bool = True,
    option: int | None = None,
    **kwargs: Any,
) -> str:
    serializer_config = _extract_serializer_config(kwargs)
    adapter = _get_adapter(backend=backend, use_builtin=use_builtin, config=serializer_config)
    return adapter.dumps(
        obj,
        skipkeys=skipkeys,
        ensure_ascii=ensure_ascii,
        check_circular=check_circular,
        allow_nan=allow_nan,
        cls=cls,
        indent=indent,
        separators=separators,
        default=default,
        sort_keys=sort_keys,
        ensure_str=ensure_str,
        option=option,
        **kwargs,
    )


def dump(
    obj: Any,
    fp: Any,
    *,
    skipkeys: bool = False,
    ensure_ascii: bool = True,
    check_circular: bool = True,
    allow_nan: bool = True,
    cls: Any = None,
    indent: int | str | None = None,
    separators: tuple[str, str] | None = None,
    default: Any = None,
    sort_keys: bool = False,
    backend: str = "auto",
    use_builtin: bool = True,
    option: int | None = None,
    **kwargs: Any,
) -> None:
    serializer_config = _extract_serializer_config(kwargs)
    adapter = _get_adapter(backend=backend, use_builtin=use_builtin, config=serializer_config)
    adapter.dump(
        obj,
        fp,
        skipkeys=skipkeys,
        ensure_ascii=ensure_ascii,
        check_circular=check_circular,
        allow_nan=allow_nan,
        cls=cls,
        indent=indent,
        separators=separators,
        default=default,
        sort_keys=sort_keys,
        option=option,
        **kwargs,
    )


def loads(
    s: Union[str, bytes, bytearray],
    *,
    cls: Any = None,
    object_hook: Any = None,
    parse_float: Any = None,
    parse_int: Any = None,
    parse_constant: Any = None,
    object_pairs_hook: Any = None,
    backend: str = "auto",
    use_builtin: bool = True,
    **kwargs: Any,
) -> Any:
    adapter = _get_adapter(backend=backend, use_builtin=use_builtin)
    return adapter.loads(
        s,
        cls=cls,
        object_hook=object_hook,
        parse_float=parse_float,
        parse_int=parse_int,
        parse_constant=parse_constant,
        object_pairs_hook=object_pairs_hook,
        **kwargs,
    )


def load(
    fp: Any,
    *,
    cls: Any = None,
    object_hook: Any = None,
    parse_float: Any = None,
    parse_int: Any = None,
    parse_constant: Any = None,
    object_pairs_hook: Any = None,
    backend: str = "auto",
    use_builtin: bool = True,
    **kwargs: Any,
) -> Any:
    adapter = _get_adapter(backend=backend, use_builtin=use_builtin)
    return adapter.load(
        fp,
        cls=cls,
        object_hook=object_hook,
        parse_float=parse_float,
        parse_int=parse_int,
        parse_constant=parse_constant,
        object_pairs_hook=object_pairs_hook,
        **kwargs,
    )
