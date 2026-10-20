from app.schemas import JobOptions
from app.services.five_shots import (
    PHOTO_PLAN,
    build_five_shot_prompts,
    build_series_prompt_text,
)
from app.services.prompts import normalize_options


def test_five_shot_plan_and_prompts():
    options = normalize_options("five_shots", JobOptions(size="1024x1024"))
    shots = build_five_shot_prompts(options, "套装，注意裤脚和腰头")
    assert len(shots) == 5
    assert [shot.name for shot in shots] == [
        "主图",
        "版型图",
        "细节图",
        "场景图",
        "补充信息图",
    ]
    assert shots[0].uses_anchor is False
    assert all(shot.uses_anchor for shot in shots[1:])
    assert "图3：内部生成的首张一致性参考" not in shots[0].prompt
    assert "图3：内部生成的首张一致性参考" in shots[1].prompt
    assert "第1张：主图" in shots[0].prompt
    assert "第5张：补充信息图" in shots[4].prompt
    assert "套装，注意裤脚和腰头" in shots[0].prompt
    assert "只输出当前第3张独立商品照片" in shots[2].prompt

    combined = build_series_prompt_text(shots)
    for shot in shots:
        assert f"【第{shot.order}张 · {shot.name}】" in combined
    assert len(PHOTO_PLAN) == 5
