"""수집이 어디까지 왔는지 보여 준다. 아무것도 바꾸지 않는다. 진행보기.bat이 부른다."""
import glob
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
import 수집 as m  # noqa: E402

tags = sorted(os.path.basename(p)[7:-4] for p in glob.glob(os.path.join(H, "prompt_*.txt")))
ok = [t for t in tags if m.done(t)]
left = len(tags) - len(ok)
print(f"\n묶음 {len(tags)}개 중 끝난 것 {len(ok)}개, 남은 것 {left}개 (한 묶음 5곳)")
log = os.path.join(H, "진행.txt")
if os.path.exists(log):
    lines = [x for x in open(log, encoding="utf-8", errors="replace").read().splitlines() if x.strip()]
    print("\n최근 기록:")
    for x in lines[-5:]:
        print("  ", x)
    age = (time.time() - os.path.getmtime(log)) / 60
    print(f"\n마지막 기록은 {age:.0f}분 전입니다.", "(30분 넘게 그대로면 검은 창이 꺼졌는지 보세요)" if age > 30 and left else "")
else:
    print("\n아직 시작하지 않았습니다. 수집시작.bat을 두 번 누르세요.")
if left:
    print(f"남은 시간은 대략 {left * 3 // 60}시간 {left * 3 % 60}분 ~ {left * 6 // 60}시간 {left * 6 % 60}분입니다.")
else:
    print("모두 끝났습니다. 합치기.bat을 두 번 누르세요.")
for name, msg in (("막힘.txt", "막힘.txt가 있습니다 → 안내.md '멈췄을 때'를 보세요."),
                  ("멈춤.txt", "멈춤.txt가 있습니다 → 이어서 하려면 지우고 수집시작.bat을 누르세요.")):
    if os.path.exists(os.path.join(H, name)):
        print("\n!!", msg)
        print("   ", open(os.path.join(H, name), encoding="utf-8", errors="replace").read().strip()[:200])
