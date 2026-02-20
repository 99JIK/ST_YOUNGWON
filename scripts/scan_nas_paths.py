"""NAS 디렉토리를 스캔하여 파일 경로 인덱스를 생성하는 스크립트.

사용법:
    python scripts/scan_nas_paths.py --root /volume1/shared --prefix "\\\\NAS_SERVER"
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.app.config import settings


def categorize_by_parent(file_path: Path, root: Path) -> str:
    """부모 폴더 기준으로 카테고리 추출."""
    relative = file_path.relative_to(root)
    parts = relative.parts
    if len(parts) > 1:
        return parts[0]
    return "기타"


def extract_tags(filename: str) -> list[str]:
    """파일명에서 태그 추출."""
    # 확장자 제거
    stem = Path(filename).stem
    # 특수문자로 분리
    import re

    tokens = re.split(r"[-_\s\[\]()（）.]+", stem)
    return [t.strip() for t in tokens if t.strip() and len(t.strip()) > 1]


def scan_directory(
    root: Path, nas_prefix: str = "\\\\NAS_SERVER"
) -> list[dict]:
    """디렉토리를 스캔하여 파일 경로 목록을 생성합니다."""
    entries = []
    for file_path in root.rglob("*"):
        if file_path.is_file() and not file_path.name.startswith("."):
            relative = file_path.relative_to(root)
            nas_path = f"{nas_prefix}\\{str(relative)}"

            entries.append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "name": file_path.stem,
                    "path": nas_path,
                    "category": categorize_by_parent(file_path, root),
                    "description": "",
                    "tags": extract_tags(file_path.name),
                }
            )

    return entries


def main():
    parser = argparse.ArgumentParser(description="NAS 디렉토리 스캔")
    parser.add_argument("--root", required=True, help="스캔할 루트 디렉토리")
    parser.add_argument(
        "--prefix",
        default=f"\\\\{settings.nas_server_name}",
        help="NAS UNC 경로 접두사",
    )
    parser.add_argument(
        "--output",
        default=str(settings.nas_paths_file),
        help="출력 JSON 파일 경로",
    )
    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"오류: {root} 디렉토리가 존재하지 않습니다.")
        sys.exit(1)

    entries = scan_directory(root, args.prefix)
    print(f"발견된 파일: {len(entries)}개")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {"paths": entries}
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"인덱스 저장 완료: {output_path}")


if __name__ == "__main__":
    main()
