"""cells-json 打包入口，支持 --release 生成 pyd/so。"""

import os
import sys
from pathlib import Path

from Cython.Build import cythonize
from setuptools import Extension, find_packages, setup
from setuptools.command.build_ext import build_ext as _build_ext


BASE_DIR = Path(__file__).resolve().parent
DIST_NAME = "cells-json"
MODULE_ROOT = "cells"
PKG_VERSION = "0.1.0"
PKG_ROOT = BASE_DIR / MODULE_ROOT

# === 可选保留文件（不会被删除）===
KEEP_FILES = {"__init__.py"}

# === 是否发布模式 ===
IS_RELEASE = "--release" in sys.argv
if IS_RELEASE:
    sys.argv.remove("--release")


def discover_py_sources():
    """发现需要编译的 .py 文件（排除 __init__.py）。"""
    sources = []
    for src in PKG_ROOT.rglob("*.py"):
        if src.name in KEEP_FILES:
            continue
        sources.append(src)
    return sorted(sources)


def make_extensions(srcs):
    """从 .py 源文件生成 Extension。"""
    exts = []
    for src in srcs:
        rel = src.relative_to(BASE_DIR)
        mod_name = str(rel.with_suffix("")).replace(os.sep, ".")
        exts.append(Extension(mod_name, [str(rel)]))
    return exts


class ReleaseBuild(_build_ext):
    def run(self):
        super().run()
        if IS_RELEASE:
            removed = 0
            for ext in ("*.py", "*.c"):
                for src_file in PKG_ROOT.rglob(ext):
                    if any(part in {".venv", "venv"} for part in src_file.parts):
                        continue
                    if src_file.name not in KEEP_FILES:
                        src_file.unlink()
                        removed += 1
            print(f"[CLEAN] 已删除源码（发布模式），共 {removed} 个文件（保留 {'/'.join(KEEP_FILES)}）")


# === 编译配置 ===
directives = {
    "language_level": "3",
    "binding": False,
    "boundscheck": False,
    "wraparound": False,
    "initializedcheck": False,
    "cdivision": True,
    "infer_types": True,
    "nonecheck": False,
    "profile": False,
    "linetrace": False,
    "emit_code_comments": False,
    "optimize.use_switch": True,
    "optimize.unpack_method_calls": True,
}

py_sources = discover_py_sources()
extensions = make_extensions(py_sources)

setup(
    name=DIST_NAME,
    version=PKG_VERSION,
    license="MPL-2.0",
    author="HarmonSir",
    author_email="git@pylab.me",
    description="Cells JSON serialization utilities",
    packages=find_packages(include=[f"{MODULE_ROOT}", f"{MODULE_ROOT}.*"]),
    include_package_data=True,
    zip_safe=False,
    python_requires=">=3.9",
    install_requires=[],
    cmdclass={"build_ext": ReleaseBuild},
    ext_modules=cythonize(extensions, compiler_directives=directives, annotate=False),
)
