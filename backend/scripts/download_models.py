"""Download every pretrained checkpoint used by the platform.

Usage (from the ``backend`` directory, with the venv active)::

    python scripts/download_models.py [--force] [--with-ocr]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.registry import MODEL_SPECS, registry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch pretrained detection weights")
    parser.add_argument("--force", action="store_true", help="re-download existing weights")
    parser.add_argument(
        "--with-ocr", action="store_true", help="also pre-fetch EasyOCR plate-reading weights"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    failures: list[str] = []
    for key, spec in MODEL_SPECS.items():
        try:
            path = registry.download(key, force=args.force)
            print(f"[ok]   {spec.name:<28} {path} ({path.stat().st_size / 1e6:.1f} MB)")
        except Exception as exc:
            failures.append(key)
            print(f"[fail] {spec.name:<28} {exc}")

    if args.with_ocr:
        try:
            registry.ocr()
            print("[ok]   EasyOCR english_g2           ready")
        except Exception as exc:
            failures.append("ocr")
            print(f"[fail] EasyOCR english_g2           {exc}")

    if failures:
        print(f"\n{len(failures)} model(s) failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    print("\nAll models ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
