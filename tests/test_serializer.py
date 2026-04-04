"""测试 JSON 序列化器

运行测试：python -m pytest tests/test_serializer.py -v
或者：python tests/test_serializer.py
"""

import json
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from io import StringIO
from pathlib import Path
from uuid import uuid4


# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from cells.json import (
    dump,
    dumps,
    JSONAdapter,
    load,
    loads,
    safe_json_dumps,
    UniversalSerializer,
    JSONEncodeError,
    CircularReferenceError,
)
from cells.json.utils import JsonSerializable, json_serializable, save_json, load_json, prettify_json
from cells.json.adapter import HAS_ORJSON


class Color(Enum):
    """颜色枚举"""
    RED = 1
    GREEN = 2
    BLUE = 3


def test_basic_types():
    """测试基本类型序列化"""
    print("测试基本类型...")
    data = {
        "string": "hello",
        "int": 42,
        "float": 3.14,
        "bool": True,
        "none": None
    }
    result = safe_json_dumps(data)
    parsed = json.loads(result)
    assert parsed == data
    print("✓ 基本类型测试通过")


def test_datetime():
    """测试 datetime 对象序列化"""
    print("测试 datetime...")
    data = {
        "datetime": datetime(2024, 1, 1, 12, 30, 45),
        "date": date(2024, 1, 1),
        "time": time(12, 30, 45),
        "timedelta": timedelta(hours=1, minutes=30)
    }
    result = safe_json_dumps(data)
    parsed = json.loads(result)
    assert parsed["datetime"] == "2024-01-01T12:30:45"
    assert parsed["date"] == "2024-01-01"
    assert parsed["time"] == "12:30:45"
    assert parsed["timedelta"] == 5400.0  # 1.5 小时 = 5400 秒
    print("✓ datetime 测试通过")


def test_decimal():
    """测试 Decimal 序列化"""
    print("测试 Decimal...")
    data = {
        "amount": Decimal("10.50"),
        "price": Decimal("99.99")
    }
    result = safe_json_dumps(data)
    parsed = json.loads(result)
    assert parsed["amount"] == 10.5
    assert parsed["price"] == 99.99
    print("✓ Decimal 测试通过")


def test_uuid():
    """测试 UUID 序列化"""
    print("测试 UUID...")
    uid = uuid4()
    data = {
        "id": uid
    }
    result = safe_json_dumps(data)
    parsed = json.loads(result)
    assert parsed["id"] == str(uid)
    print("✓ UUID 测试通过")


def test_enum():
    """测试 Enum 序列化"""
    print("测试 Enum...")
    data = {
        "color": Color.RED,
        "favorite": Color.BLUE
    }
    result = safe_json_dumps(data)
    parsed = json.loads(result)
    assert parsed["color"] == 1
    assert parsed["favorite"] == 3
    print("✓ Enum 测试通过")


def test_path():
    """测试 Path 序列化"""
    print("测试 Path...")
    data = {
        "path": Path("/home/user/documents")
    }
    result = safe_json_dumps(data)
    parsed = json.loads(result)
    assert parsed["path"] == "/home/user/documents"
    print("✓ Path 测试通过")


def test_set_and_tuple():
    """测试 set 和 tuple 序列化"""
    print("测试 set 和 tuple...")
    data = {
        "set": {1, 2, 3},
        "tuple": (1, 2, 3)
    }
    result = safe_json_dumps(data)
    parsed = json.loads(result)
    assert isinstance(parsed["set"], list)
    assert isinstance(parsed["tuple"], list)
    assert set(parsed["set"]) == {1, 2, 3}
    assert parsed["tuple"] == [1, 2, 3]
    print("✓ set 和 tuple 测试通过")


def test_custom_object():
    """测试自定义对象序列化"""
    print("测试自定义对象...")

    class User:
        def __init__(self, name, age):
            self.name = name
            self.age = age

        def to_dict(self):
            return {"name": self.name, "age": self.age}

    user = User("Alice", 25)
    data = {
        "user": user
    }
    result = safe_json_dumps(data)
    parsed = json.loads(result)
    assert parsed["user"]["name"] == "Alice"
    assert parsed["user"]["age"] == 25
    print("✓ 自定义对象测试通过")


def test_json_serializable_base():
    """测试 JsonSerializable 基类"""
    print("测试 JsonSerializable 基类...")

    class User(JsonSerializable):
        def __init__(self, name, age):
            self.name = name
            self.age = age

    user = User("Bob", 30)
    json_str = user.to_json()
    parsed = json.loads(json_str)
    assert parsed["name"] == "Bob"
    assert parsed["age"] == 30
    print("✓ JsonSerializable 基类测试通过")


def test_json_serializable_decorator():
    """测试 @json_serializable 装饰器"""
    print("测试 @json_serializable 装饰器...")

    @json_serializable
    class Point:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    point = Point(10, 20)
    json_str = point.to_json()
    parsed = json.loads(json_str)
    assert parsed["x"] == 10
    assert parsed["y"] == 20
    print("✓ @json_serializable 装饰器测试通过")


def test_nested_structures():
    """测试嵌套结构"""
    print("测试嵌套结构...")
    data = {
        "user": {
            "name": "Alice",
            "details": {
                "age": 25,
                "address": {
                    "city": "Beijing",
                    "zip": "100000"
                }
            }
        },
        "timestamp": datetime.now()
    }
    result = safe_json_dumps(data)
    parsed = json.loads(result)
    assert parsed["user"]["name"] == "Alice"
    assert parsed["user"]["details"]["address"]["city"] == "Beijing"
    print("✓ 嵌套结构测试通过")


def test_circular_reference():
    """测试循环引用"""
    print("测试循环引用...")
    a = {}
    a["self"] = a

    # 默认行为：返回标记字符串
    result = safe_json_dumps(a)
    parsed = json.loads(result)
    assert "CircularReference" in parsed["self"]
    print("✓ 循环引用测试通过（默认模式）")

    # 严格模式：抛出异常
    try:
        safe_json_dumps(a, fail_on_circular=True)
        assert False, "应该抛出 CircularReferenceError"
    except CircularReferenceError as e:
        assert "Circular reference" in str(e)
    print("✓ 循环引用测试通过（严格模式）")


def test_mixed_types():
    """测试混合类型"""
    print("测试混合类型...")
    data = {
        "user": {
            "name": "Alice",
            "age": 25,
            "balance": Decimal("100.50"),
            "created_at": datetime.now(),
            "favorite_color": Color.BLUE,
            "id": uuid4()
        },
        "tags": ["python", "json", "serializer"],
        "count": 42,
        "active": True
    }
    result = safe_json_dumps(data)
    parsed = json.loads(result)
    assert parsed["user"]["name"] == "Alice"
    assert parsed["user"]["balance"] == 100.5
    assert parsed["user"]["favorite_color"] == 3
    assert isinstance(parsed["tags"], list)
    print("✓ 混合类型测试通过")


def test_strict_mode():
    """测试严格模式"""
    print("测试严格模式...")

    class CustomType:
        pass

    obj = CustomType()
    serializer = UniversalSerializer(strict=True)

    try:
        serializer.dumps({"obj": obj})
        assert False, "应该抛出异常"
    except JSONEncodeError:
        print("✓ 严格模式测试通过")


def test_ignore_unknown():
    """测试忽略未知类型"""
    print("测试忽略未知类型...")

    class CustomType:
        pass

    obj = CustomType()
    serializer = UniversalSerializer(ignore_unknown=True)

    result = serializer.dumps({"obj": obj})
    parsed = json.loads(result)
    assert parsed["obj"] is None
    print("✓ 忽略未知类型测试通过")


def test_numpy_support():
    """测试 numpy 支持"""
    try:
        import numpy as np

        print("测试 numpy 支持...")
        data = {
            "array": np.array([1, 2, 3]),
            "int64": np.int64(42),
            "float64": np.float64(3.14),
            "bool_": np.bool_(True)
        }
        result = safe_json_dumps(data)
        parsed = json.loads(result)
        assert parsed["array"] == [1, 2, 3]
        assert parsed["int64"] == 42
        assert parsed["float64"] == 3.14
        assert parsed["bool_"] is True
        print("✓ numpy 支持测试通过")
    except ImportError:
        print("⊘ numpy 未安装，跳过测试")


def test_pandas_support():
    """测试 pandas 支持"""
    try:
        import pandas as pd

        print("测试 pandas 支持...")
        df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        series = pd.Series([1, 2, 3], name="values")

        data = {
            "df": df,
            "series": series
        }
        result = safe_json_dumps(data)
        parsed = json.loads(result)
        assert isinstance(parsed["df"], list)
        assert len(parsed["df"]) == 2
        assert parsed["series"]["values"][0] == 1
        print("✓ pandas 支持测试通过")
    except ImportError:
        print("⊘ pandas 未安装，跳过测试")


def test_file_operations():
    """测试文件操作"""
    print("测试文件操作...")

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "test.json"
        data = {"name": "Alice", "age": 25}

        # 保存
        save_json(data, filepath)
        assert filepath.exists()

        # 加载
        loaded = load_json(filepath)
        assert loaded == data

    print("✓ 文件操作测试通过")


def test_prettify():
    """测试美化输出"""
    print("测试美化输出...")
    data = {"name": "Alice", "age": 25}
    result = prettify_json(data)
    assert "\n" in result
    assert "  " in result
    print("✓ 美化输出测试通过")


def test_stdlib_style_dumps_and_loads():
    """测试标准库风格的 dump/dumps/load/loads 接口"""
    print("测试标准库风格接口...")

    payload = {"name": "Alice", "amount": Decimal("10.50")}
    json_text = dumps(payload, ensure_ascii=False, sort_keys=True)
    parsed = loads(json_text)

    assert "\"Alice\"" in json_text
    assert parsed["amount"] == 10.5

    buffer = StringIO()
    dump(payload, buffer, ensure_ascii=False)
    buffer.seek(0)
    loaded_payload = load(buffer)
    assert loaded_payload["name"] == "Alice"
    print("✓ 标准库风格接口测试通过")


def test_parse_float_falls_back_to_stdlib_decoder():
    """测试显式指定 json 后端处理标准库解析钩子"""
    print("测试 loads 显式 json 后端...")
    result = loads("{\"value\": 1.25}", parse_float=Decimal, backend="json")
    assert result["value"] == Decimal("1.25")
    print("✓ loads 显式 json 后端测试通过")


def test_parse_float_requires_json_backend():
    """测试 orjson 主路径下对不支持的解码参数显式报错"""
    print("测试 loads 不支持参数报错...")
    if not HAS_ORJSON:
        result = loads("{\"value\": 1.25}", parse_float=Decimal)
        assert result["value"] == Decimal("1.25")
        print("⊘ orjson 未安装，auto 已退回 json backend")
        return
    try:
        loads("{\"value\": 1.25}", parse_float=Decimal)
        assert False, "应该提示显式指定 json backend"
    except TypeError as exc:
        assert "backend=\"json\"" in str(exc)
        assert "parse_float" in str(exc)
    print("✓ loads 不支持参数报错测试通过")


def test_adapter_instance_stdlib_signature():
    """测试 JSONAdapter 实例调用方式"""
    print("测试 JSONAdapter 实例接口...")
    json_adapter = JSONAdapter()

    encoded = json_adapter.dumps({"amount": Decimal("8.50")}, ensure_ascii=False)
    decoded = json_adapter.loads(encoded)

    assert decoded["amount"] == 8.5
    print("✓ JSONAdapter 实例接口测试通过")


def test_orjson_indent_and_sort_keys():
    """测试 orjson 主路径支持的标准库风格参数"""
    print("测试 orjson 参数适配...")
    result = dumps({"b": 1, "a": 2}, ensure_ascii=False, sort_keys=True, indent=2)
    assert result.index("\"a\"") < result.index("\"b\"")
    assert "\n" in result
    print("✓ orjson 参数适配测试通过")


def test_orjson_ensure_ascii_is_adapted():
    """测试 ensure_ascii=True 在 orjson 主路径下会做兼容转换"""
    print("测试 dumps ensure_ascii 适配...")
    result = dumps({"name": "中文", "emoji": "😀"}, ensure_ascii=True)
    assert result.isascii()
    assert "\\u4e2d\\u6587" in result
    assert "\\ud83d\\ude00" in result
    parsed = loads(result)
    assert parsed == {"name": "中文", "emoji": "😀"}
    if not HAS_ORJSON:
        print("⊘ orjson 未安装，当前由 json backend 原生处理")
        return
    print("✓ dumps ensure_ascii 适配测试通过")


def test_orjson_skipkeys_is_adapted():
    """测试 skipkeys 在 orjson 主路径下会进行预处理"""
    print("测试 dumps skipkeys 适配...")
    result = dumps(
        {"valid": 1, object(): 2, "nested": {"ok": 3, object(): 4}},
        skipkeys=True,
        ensure_ascii=False,
    )
    parsed = loads(result)
    assert parsed == {"valid": 1, "nested": {"ok": 3}}
    print("✓ dumps skipkeys 适配测试通过")


def test_orjson_compact_separators_is_adapted():
    """测试紧凑 separators 在 orjson 主路径下可用"""
    print("测试 dumps separators 适配...")
    result = dumps({"a": 1, "b": 2}, ensure_ascii=False, separators=(",", ":"))
    assert result == "{\"a\":1,\"b\":2}"
    print("✓ dumps separators 适配测试通过")


def test_orjson_check_circular_false_is_accepted():
    """测试 check_circular=False 在 orjson 主路径下可接受"""
    print("测试 dumps check_circular 参数...")
    result = dumps({"name": "Alice"}, ensure_ascii=False, check_circular=False)
    assert "\"Alice\"" in result
    print("✓ dumps check_circular 参数测试通过")


def test_from_cells_import_json_usage():
    """测试 from cells import json 的替代用法"""
    print("测试 from cells import json...")
    from cells import json as cells_json

    result = cells_json.dumps({"amount": Decimal("12.30")}, ensure_ascii=False)
    parsed = cells_json.loads(result)

    assert parsed["amount"] == 12.3
    print("✓ from cells import json 测试通过")


def run_all_tests():
    """运行所有测试"""
    print("=" * 50)
    print("开始运行 JSON 序列化器测试")
    print("=" * 50)
    print()

    test_basic_types()
    test_datetime()
    test_decimal()
    test_uuid()
    test_enum()
    test_path()
    test_set_and_tuple()
    test_custom_object()
    test_json_serializable_base()
    test_json_serializable_decorator()
    test_nested_structures()
    test_circular_reference()
    test_mixed_types()
    test_strict_mode()
    test_ignore_unknown()
    test_numpy_support()
    test_pandas_support()
    test_file_operations()
    test_prettify()
    test_stdlib_style_dumps_and_loads()
    test_parse_float_falls_back_to_stdlib_decoder()
    test_parse_float_requires_json_backend()
    test_adapter_instance_stdlib_signature()
    test_orjson_indent_and_sort_keys()
    test_orjson_ensure_ascii_is_adapted()
    test_orjson_skipkeys_is_adapted()
    test_orjson_compact_separators_is_adapted()
    test_orjson_check_circular_false_is_accepted()
    test_from_cells_import_json_usage()

    print()
    print("=" * 50)
    print("所有测试通过 ✓")
    print("=" * 50)


if __name__ == "__main__":
    run_all_tests()
