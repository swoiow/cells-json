from pathlib import Path

from setuptools import find_namespace_packages, setup


BASE_DIR = Path(__file__).resolve().parent
DIST_NAME = "cells-json"
MODULE_ROOT = "cells"
VERSION_FILE = BASE_DIR / MODULE_ROOT / "json" / "version.py"


def read_version() -> str:
    """从 version.py 中读取版本号，避免导入包导致依赖冲突"""
    version_scope: dict[str, str] = {}
    try:
        content = VERSION_FILE.read_text(encoding="utf-8")
        exec(content, version_scope)
        return version_scope["__VERSION__"]
    except Exception as e:
        # 备选方案，防止读取失败
        return "0.1.0"


setup(
    name=DIST_NAME,
    version=read_version(),
    license="MPL-2.0",
    author="HarmonSir",
    author_email="git@pylab.me",
    description="Cells JSON serialization utilities",
    packages=find_namespace_packages(include=[f"{MODULE_ROOT}.*"]),
    include_package_data=True,
    zip_safe=False,
    python_requires=">=3.9",
    install_requires=[
        "orjson"
    ],
)
