import decimal
import gc
import json
import sys
import timeit
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


# 添加父目录到路径，确保使用本地代码
sys.path.insert(0, str(Path(__file__).parent.parent))

from cells.json.adapter import JSONAdapter


# --- 1. 测试数据构造 (Test Data Suites) ---

def get_simple_data(size: int = 1000) -> Dict[str, Any]:
    """基础类型数据"""
    return {f"key_{i}": i for i in range(size)}


def get_complex_data(size: int = 1000) -> Dict[str, Any]:
    """复杂类型数据：包含适配器需要介入的类型"""
    return {
        f"id_{i}": {
            "uuid": uuid.uuid4(),
            "time": datetime.now(),
            "price": decimal.Decimal("199.99"),
            "path": Path("/usr/bin/python"),
            "tags": [f"tag_{i}"] * 5
        }
        for i in range(size)
    }


# --- 2. 性能测试核心类 (Performance Benchmark) ---

class PerformanceRunner:
    """Design Intent: 自动化对比不同后端的序列化吞吐量"""

    def __init__(self, data: Any, iterations: int = 100):
        self.data = data
        self.iterations = iterations
        # 统一关闭 ensure_str 以对比核心序列化性能
        self.adapter_auto = JSONAdapter(backend="auto", use_builtin=True)
        self.adapter_custom = JSONAdapter(backend="auto", use_builtin=False)

    def run_benchmark(self, label: str):
        print(f"\n🚀 Benchmarking: {label} ({self.iterations} iterations)")
        print("-" * 60)

        # 强制执行 GC 并禁用，排除波动
        gc.collect()
        gc.disable()

        try:
            # 1. 原生 json
            t_json = timeit.timeit(lambda: json.dumps(self.data, default=str), number=self.iterations)

            # 2. 原生 orjson (修正版：开启原生处理并提供必要兜底)
            t_orjson = "N/A"
            try:
                import orjson

                def orjson_default(obj):
                    if isinstance(obj, decimal.Decimal):
                        return float(obj)
                    if isinstance(obj, Path):
                        return str(obj)
                    raise TypeError

                # 使用原生支持的选项
                option = 0
                for opt in ["OPT_SERIALIZE_DATETIME", "OPT_SERIALIZE_UUID", "OPT_NON_STR_KEYS"]:
                    option |= getattr(orjson, opt, 0)

                t_orjson = timeit.timeit(
                    lambda: orjson.dumps(self.data, option=option, default=orjson_default),
                    number=self.iterations
                )
            except Exception as e:
                t_orjson = f"Error: {type(e).__name__}"

            # 3. Adapter (Built-in mode)
            # 设置 ensure_str=False 避免字符串解码开销
            t_adapter_builtin = timeit.timeit(
                lambda: self.adapter_auto.dumps(self.data, ensure_str=False),
                number=self.iterations
            )

            # 4. Adapter (Universal mode)
            t_adapter_custom = timeit.timeit(
                lambda: self.adapter_custom.dumps(self.data, ensure_str=False),
                number=self.iterations
            )
        finally:
            gc.enable()

        # 输出结果
        results = [
            ("Standard json.dumps", t_json),
            ("Native orjson.dumps", t_orjson),
            ("Adapter (Built-in)", t_adapter_builtin),
            ("Adapter (Universal)", t_adapter_custom),
        ]

        for name, duration in results:
            if isinstance(duration, float):
                ops_per_sec = self.iterations / duration
                print(f"{name:<25}: {duration:.4f}s | {ops_per_sec:>10.2f} ops/sec")
            else:
                print(f"{name:<25}: {duration}")


def core_main():
    """执行性能评估"""
    # 场景 A: 简单字典
    simple_data = get_simple_data(2000)
    PerformanceRunner(simple_data, 500).run_benchmark("Simple Dictionary (2k keys)")

    # 场景 B: 复杂对象
    complex_data = get_complex_data(500)
    PerformanceRunner(complex_data, 100).run_benchmark("Complex Objects (500 entries)")


if __name__ == "__main__":
    core_main()
