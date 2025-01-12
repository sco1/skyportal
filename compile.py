import platform
import subprocess
import time
from pathlib import Path

SOURCE_DIR = Path("./skyportal")
DEST_DIR = Path("./dist/lib/skyportal")

COMPILERS = {
    "Windows": Path("./mpy-cross/mpy-cross-windows-9.2.2.static.exe"),
    "Linux": Path("./mpy-cross/mpy-cross-linux-amd64-9.2.2.static"),
    "Darwin": Path("./mpy-cross/mpy-cross-macos-9.2.2-arm64"),
}


if __name__ == "__main__":
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    to_compile = list(SOURCE_DIR.glob("*.py"))
    print(f"Found {len(to_compile)} *.py files to compile")
    for filepath in to_compile:
        subprocess.run([COMPILERS[platform.system()], filepath])

    time.sleep(1)  # Lazy wait for subprocesses to finish

    compiled = list(SOURCE_DIR.glob("*.mpy"))
    if len(compiled) != len(to_compile):
        raise RuntimeError(
            f"Number of compiled files less than original source ({len(compiled)} < {len(to_compile)}), may need a longer wait"  # noqa: E501
        )

    print(f"Compiled {len(compiled)} files ... moving to {DEST_DIR}")
    for filepath in compiled:
        dest = DEST_DIR / filepath.name
        dest.unlink(missing_ok=True)

        filepath.rename(DEST_DIR / filepath.name)
