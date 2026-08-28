"""
ST영원 스마트 오피스 — 테스트 결과서 생성기
==========================================
test_api.py의 JSON 결과를 HTML 보고서로 변환합니다.

사용법:
    python -m backend.tests.generate_report test_report_20260316_xxxx.json
    python -m backend.tests.generate_report test_report.json -o QA_결과서.html
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ST영원 스마트 오피스 — QA 테스트 결과서</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Pretendard', 'Malgun Gothic', sans-serif; background: #f5f5f5; color: #333; padding: 40px 20px; }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  .header {{ background: #1a1a2e; color: #fff; padding: 32px 40px; border-radius: 12px 12px 0 0; }}
  .header h1 {{ font-size: 22px; margin-bottom: 4px; }}
  .header .sub {{ color: #aaa; font-size: 13px; }}
  .summary {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 0; background: #fff; border-bottom: 2px solid #eee; }}
  .summary .item {{ padding: 20px; text-align: center; border-right: 1px solid #eee; }}
  .summary .item:last-child {{ border-right: none; }}
  .summary .value {{ font-size: 28px; font-weight: 700; }}
  .summary .label {{ font-size: 12px; color: #888; margin-top: 4px; }}
  .pass {{ color: #22c55e; }}
  .fail {{ color: #ef4444; }}
  .category {{ margin-top: 24px; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .category-header {{ background: #f8f9fa; padding: 14px 20px; font-weight: 600; font-size: 15px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; }}
  .category-header .badge {{ font-size: 12px; padding: 2px 10px; border-radius: 10px; }}
  .badge-pass {{ background: #dcfce7; color: #166534; }}
  .badge-fail {{ background: #fee2e2; color: #991b1b; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #fafafa; text-align: left; padding: 10px 16px; font-weight: 600; color: #666; border-bottom: 1px solid #eee; }}
  td {{ padding: 10px 16px; border-bottom: 1px solid #f0f0f0; }}
  tr:last-child td {{ border-bottom: none; }}
  .status {{ font-weight: 700; font-size: 12px; }}
  .status.pass {{ color: #22c55e; }}
  .status.fail {{ color: #ef4444; }}
  .time {{ font-family: 'Consolas', monospace; font-size: 12px; color: #666; text-align: right; }}
  .detail {{ color: #888; font-size: 12px; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .footer {{ text-align: center; margin-top: 32px; font-size: 12px; color: #aaa; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>ST영원 스마트 오피스 — QA 테스트 결과서</h1>
    <div class="sub">서버: {server_url} &nbsp;|&nbsp; 실행: {executed_at} &nbsp;|&nbsp; 총 소요: {duration}초</div>
  </div>

  <div class="summary">
    <div class="item"><div class="value">{total}</div><div class="label">전체</div></div>
    <div class="item"><div class="value pass">{passed}</div><div class="label">통과</div></div>
    <div class="item"><div class="value fail">{failed}</div><div class="label">실패</div></div>
    <div class="item"><div class="value">{pass_rate}%</div><div class="label">통과율</div></div>
    <div class="item"><div class="value">{duration}s</div><div class="label">소요 시간</div></div>
  </div>

  {categories_html}

  <div class="footer">
    생성 일시: {generated_at} &nbsp;|&nbsp; ST영원 스마트 오피스 QA
  </div>
</div>
</body>
</html>
"""

CATEGORY_TEMPLATE = """\
  <div class="category">
    <div class="category-header">
      <span>{cat_name}</span>
      <span class="badge {badge_cls}">{cat_passed}/{cat_total} 통과</span>
    </div>
    <table>
      <thead><tr><th style="width:40px">결과</th><th>테스트 항목</th><th style="width:100px;text-align:right">응답 시간</th><th>비고</th></tr></thead>
      <tbody>
{rows}
      </tbody>
    </table>
  </div>
"""

ROW_TEMPLATE = """\
        <tr>
          <td><span class="status {cls}">{icon}</span></td>
          <td>{name}</td>
          <td class="time">{time}</td>
          <td class="detail" title="{detail_full}">{detail}</td>
        </tr>"""


def generate_html(report: dict) -> str:
    # 카테고리별 그룹
    categories: dict[str, list] = {}
    for r in report["results"]:
        cat = r["category"]
        categories.setdefault(cat, []).append(r)

    cats_html = []
    for cat_name, items in categories.items():
        cat_passed = sum(1 for i in items if i["passed"])
        cat_total = len(items)
        badge_cls = "badge-pass" if cat_passed == cat_total else "badge-fail"

        rows = []
        for item in items:
            cls = "pass" if item["passed"] else "fail"
            icon = "PASS" if item["passed"] else "FAIL"
            ms = item.get("response_ms", 0)
            time_str = f"{ms:,.0f}ms" if ms else "-"
            detail = item.get("detail", "")
            detail_short = detail[:60] + "..." if len(detail) > 60 else detail
            rows.append(ROW_TEMPLATE.format(
                cls=cls, icon=icon, name=item["name"],
                time=time_str, detail=detail_short, detail_full=detail,
            ))

        cats_html.append(CATEGORY_TEMPLATE.format(
            cat_name=cat_name, badge_cls=badge_cls,
            cat_passed=cat_passed, cat_total=cat_total,
            rows="\n".join(rows),
        ))

    total = report["total"]
    passed = report["passed"]
    failed = report["failed"]
    duration = f"{report['total_duration_ms'] / 1000:.1f}"
    pass_rate = round(passed / total * 100) if total else 0

    return HTML_TEMPLATE.format(
        server_url=report.get("server_url", ""),
        executed_at=report.get("executed_at", "")[:19].replace("T", " "),
        duration=duration,
        total=total,
        passed=passed,
        failed=failed,
        pass_rate=pass_rate,
        categories_html="\n".join(cats_html),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def main():
    parser = argparse.ArgumentParser(description="테스트 JSON → HTML 결과서")
    parser.add_argument("json_file", help="test_api.py가 생성한 JSON 파일")
    parser.add_argument("-o", "--output", default=None, help="출력 HTML 경로")
    args = parser.parse_args()

    with open(args.json_file, encoding="utf-8") as f:
        report = json.load(f)

    html = generate_html(report)

    out = args.output or args.json_file.replace(".json", ".html")
    Path(out).write_text(html, encoding="utf-8")
    print(f"결과서 생성 완료: {out}")


if __name__ == "__main__":
    main()
