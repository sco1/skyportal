import time
from pathlib import Path

import mpy_cross

SOURCE_DIR = Path("./skyportal")
DEST_DIR = Path("./dist/lib/skyportal")


if __name__ == "__main__":
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    to_compile = list(SOURCE_DIR.glob("*.py"))
    print(f"Found {len(to_compile)} *.py files to compile")
    for filepath in to_compile:
        mpy_cross.run(filepath)

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
