from app.schemas import JobOptions
from app.services.prompts import build_prompt, normalize_options, validate_input_roles


def test_prompt_contains_preservation_and_style():
    options = normalize_options("try_on", JobOptions(style="street", size="1024x1536"))
    prompt = build_prompt("try_on", options, "自然通勤", ["garment", "model"])
    assert "Urban street style" in prompt
    assert "actual product reference is authoritative" in prompt
    assert "自然通勤" in prompt
    assert "Image 1: ACTUAL PRODUCT" in prompt
    assert "Image 2: MODEL IDENTITY" in prompt
    assert "No collage" in prompt


def test_ai_model_prompt_uses_gender_and_pose():
    options = normalize_options("try_on", JobOptions(gender="male", pose="editorial"))
    prompt = build_prompt("try_on", options, "", ["garment"])
    assert "adult male model" in prompt
    assert "controlled editorial pose" in prompt
    assert "Image 2: MODEL IDENTITY" not in prompt


def test_white_bg_prompt_uses_side():
    options = normalize_options("white_bg", JobOptions(style="flat_lay", side="back"))
    prompt = build_prompt("white_bg", options, "", ["garment"])
    assert "flat-lay" in prompt
    assert "back side" in prompt
    assert "No person is required" in prompt


def test_detail_prompt_contains_avoid_terms():
    options = normalize_options("detail", JobOptions(style="stitching"))
    prompt = build_prompt("detail", options, "", ["garment"])
    assert "stitching" in prompt
    assert "waxy skin" in prompt
    assert "No person is required" in prompt


def test_approved_and_edit_target_roles_are_explicit():
    options = normalize_options("try_on", JobOptions(style="studio"))
    prompt = build_prompt(
        "try_on",
        options,
        "站姿太僵，手指像展示式张开；保持脸和服装不变",
        ["garment", "model", "approved", "edit_target"],
    )
    assert "Image 3: USER-APPROVED RESULT" in prompt
    assert "Image 4: EDIT TARGET" in prompt
    assert "Image 4 (the edit target)" in prompt
    assert "User feedback: 站姿太僵" in prompt
    assert "Do not carry over the edit target's defects" in prompt


def test_roles_validation():
    class Item:
        def __init__(self, asset_id: str, role: str):
            self.asset_id = asset_id
            self.role = role

    validate_input_roles("try_on", [Item("a" * 32, "garment"), Item("b" * 32, "model")])
    validate_input_roles(
        "try_on",
        [
            Item("a" * 32, "garment"),
            Item("b" * 32, "model"),
            Item("c" * 32, "approved"),
        ],
    )
    try:
        validate_input_roles("white_bg", [Item("a" * 32, "reference")])
    except ValueError as exc:
        assert "服装主图" in str(exc)
    else:
        raise AssertionError("missing garment should fail")
    validate_input_roles(
        "try_on",
        [Item("a" * 32, "garment"), Item("b" * 32, "approved")],
    )
