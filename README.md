# cells-json

通用 JSON 序列化工具，提供灵活的类型序列化能力，解决 Python 中常见的 JSON 序列化问题。

## 功能特性

- **丰富的类型支持**：datetime、Decimal、UUID、Enum、Path、numpy、pandas 等
- **自定义对象序列化**：支持带有 `to_dict()` 方法的对象或自动使用 `__dict__` 属性
- **循环引用检测**：自动检测并处理循环引用
- **灵活的配置**：支持严格模式、忽略未知类型、自定义序列化函数
- **便捷工具**：提供装饰器、基类和辅助函数简化使用

## 安装

```bash
pip install cells-json
```

## 快速开始

### 基本使用

```python
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from cells.json import safe_json_dumps


# 混合类型序列化
data = {
    "time": datetime.now(),
    "amount": Decimal("10.50"),
    "id": uuid4(),
    "active": True
}

json_str = safe_json_dumps(data)
print(json_str)
# {"time": "2024-01-01T12:00:00", "amount": 10.5, "id": "123e4567-e89b-12d3-a456-426614174000", "active": true}
```

### 使用 UniversalSerializer

```python
from cells.json import UniversalSerializer


# 创建序列化器实例
serializer = UniversalSerializer()

# 严格模式：遇到未知类型立即抛出异常
strict_serializer = UniversalSerializer(strict=True)

# 忽略未知类型：将无法序列化的字段替换为 None
lenient_serializer = UniversalSerializer(ignore_unknown=True)

# 序列化
json_str = serializer.dumps(data)
```

### 自定义对象序列化

#### 方式 1：使用 to_dict() 方法

```python
class User:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def to_dict(self):
        return {"name": self.name, "age": self.age}


user = User("Alice", 25)
json_str = safe_json_dumps(user)
```

#### 方式 2：使用 JsonSerializable 基类

```python
from cells.json.utils import JsonSerializable


class User(JsonSerializable):
    def __init__(self, name, age):
        self.name = name
        self.age = age


user = User("Alice", 25)
json_str = user.to_json()
```

#### 方式 3：使用 @json_serializable 装饰器

```python
from cells.json.utils import json_serializable


@json_serializable
class User:
    def __init__(self, name, age):
        self.name = name
        self.age = age


user = User("Alice", 25)
json_str = user.to_json()
```

### 文件操作

```python
from cells.json.utils import save_json, load_json


# 保存为 JSON 文件
data = {"name": "Alice", "age": 25}
save_json(data, "user.json")

# 从 JSON 文件加载
loaded_data = load_json("user.json")
```

### 美化输出

```python
from cells.json.utils import prettify_json


data = {"name": "Alice", "age": 25}
print(prettify_json(data))
# {
#   "name": "Alice",
#   "age": 25
# }
```

### numpy 和 pandas 支持

```python
import numpy as np
import pandas as pd
from cells.json import safe_json_dumps


# numpy 数组
arr = np.array([1, 2, 3])
json_str = safe_json_dumps({"array": arr})

# pandas DataFrame
df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
json_str = safe_json_dumps({"data": df})
```

### 自定义序列化函数

```python
from cells.json import UniversalSerializer


def custom_serializer(obj):
    """自定义序列化函数"""
    if hasattr(obj, "custom_method"):
        return obj.custom_method()
    return str(obj)


serializer = UniversalSerializer(default=custom_serializer)
json_str = serializer.dumps(data)
```

## 支持的数据类型

### 内置类型

- `datetime.date` → ISO 格式字符串
- `datetime.datetime` → ISO 格式字符串
- `datetime.time` → ISO 格式字符串
- `datetime.timedelta` → 总秒数 (float)
- `decimal.Decimal` → float
- `uuid.UUID` → 字符串
- `enum.Enum` → value
- `pathlib.Path` → 字符串
- `set` → 列表
- `tuple` → 列表

### 第三方库类型（可选依赖）

- `numpy.ndarray` → 列表
- `numpy.integer` → int
- `numpy.floating` → float
- `pandas.DataFrame` → dict (records)
- `pandas.Series` → dict

### 自定义对象

- 带有 `to_dict()` 方法的对象
- 使用 `__dict__` 属性的对象
- 使用 `__slots__` 的对象

## 异常处理

```python
from cells.json.exceptions import JSONSerializationError


try:
    json_str = safe_json_dumps(data)
except JSONSerializationError as e:
    print(f"序列化失败: {e}")
    print(f"对象类型: {e.obj_type}")
```

## 配置选项

### UniversalSerializer 参数

- `default` (Callable): 自定义序列化函数
- `strict` (bool): 严格模式，默认 False
- `ignore_unknown` (bool): 忽略未知类型，默认 False

### safe_json_dumps 参数

- `ignore_errors` (bool): 忽略错误返回默认值，默认 False
- `default_value` (str): 默认返回值，默认 "null"

## 高级用法

### 循环引用处理

```python
# 循环引用会自动检测并标记
a = {}
a['self'] = a

serializer = UniversalSerializer()
json_str = serializer.dumps(a)
# {"self": "<CircularReference dict>"}
```

### 与 json.dumps 集成

```python
import json
from cells.json.serializer import universal_serializer


data = {"time": datetime.now()}
json_str = json.dumps(data, default=universal_serializer)
```

## 模块结构

```
cells-json/
├── cells/
│   ├── json/
│   │   ├── __init__.py       # 模块入口
│   │   ├── serializer.py     # 核心序列化器
│   │   ├── exceptions.py     # 异常定义
│   │   └── utils.py          # 辅助工具
│   └── __init__.py
├── tests/
│   └── test_serializer.py    # 测试文件
├── docs/
├── setup.py
└── README.md
```

## 构建与发布

- 开发模式: `python setup.py build_ext --inplace`
- 发布模式: `python setup.py build_ext --inplace --release`

## 许可证

MPL-2.0
