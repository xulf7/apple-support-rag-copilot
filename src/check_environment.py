"""Read-only environment inventory; never enumerate environment variable values."""
from importlib.metadata import version, PackageNotFoundError
import json
import platform
import sys


def main():
    packages = {}
    for name in ["requests", "beautifulsoup4", "pypdf", "pytest", "numpy", "torch",
                 "transformers", "sentence-transformers", "faiss-cpu", "tokenizers"]:
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    print(json.dumps({"executable": sys.executable, "python": sys.version,
                      "platform": platform.platform(), "packages": packages}, indent=2))


if __name__ == "__main__":
    main()
