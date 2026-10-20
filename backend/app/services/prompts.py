"""Prompt construction adapted from the user's apparel-product-photography skill.

The original skill lives outside this repository. This module turns its reference
roles, product/identity locks, natural-photography guidance and revision rules
into the final prompt sent to the relay.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas import InputAssetIn, JobOptions, WorkflowId
from .five_shots import plan_meta

GLOBAL_PRESERVE = (
    "The actual product reference is authoritative. Match visible construction, color, fit, "
    "fasteners, pockets, piping, prints, and existing marks. Keep the design consistent; "
    "add no unsupported design features. Describe material appearance, not unverified fiber "
    "composition. Reproduce existing garment lettering where visible; add no advertising text."
)

GLOBAL_NATURAL = (
    "Use coherent soft directional light with gentle fill, believable contact shadows and "
    "natural tonal variation. Preserve modest, scale-appropriate skin texture, relaxed facial "
    "expression, credible hand anatomy and natural finger curvature. Fabric should fold under "
    "gravity, body movement and local tension. Maintain accurate product colors and readable "
    "garment details. Avoid waxy skin, smoothing filters, rigid mannequin posing, floating feet, "
    "pasted-on edges, physically inconsistent shadows, glossy fabric when the reference is matte, "
    "and decorative changes to the garment. Do not manufacture realism with excessive grain, "
    "dirt, sharp pores or deep wrinkles."
)

GLOBAL_OUTPUT = (
    "One standalone image. No collage, inset, border, watermark, caption, price badge or new "
    "logo. Existing garment marks follow the product reference. Generate a new camera photograph "
    "guided by the references, not a layout sheet of the inputs."
)


@dataclass(frozen=True)
class StyleDefinition:
    id: str
    label: str
    description: str
    prompt: str

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
        }


TRY_ON_STYLES = (
    StyleDefinition(
        "studio",
        "高级棚拍",
        "浅灰无缝背景，柔和棚灯，适合主图",
        "高级商业影棚，浅灰无缝背景，柔光箱主光与柔和侧光，整体干净克制，低饱和配色",
    ),
    StyleDefinition(
        "street",
        "都市街拍",
        "自然日光与城市街区，生活感",
        "都市街拍，自然日光，现代建筑与街道轻微虚化，真实生活感，抓拍式自然氛围",
    ),
    StyleDefinition(
        "commute",
        "通勤办公",
        "落地窗自然光，低饱和精致感",
        "现代通勤办公空间，落地窗自然光，低饱和色调，精致克制的都市氛围",
    ),
    StyleDefinition(
        "resort",
        "度假暖阳",
        "海边或庭院，轻松通透",
        "度假场景，海边或庭院暖阳，轻松自然的空气感，明亮通透的色调",
    ),
)

WHITE_BG_STYLES = (
    StyleDefinition(
        "white",
        "纯白底",
        "标准电商白底主图",
        "纯白无缝背景 #FFFFFF，柔和接触阴影，主体居中完整露出，符合主流电商平台主图规范",
    ),
    StyleDefinition(
        "light_gray",
        "浅灰底",
        "更有层次的棚拍质感",
        "浅灰无缝背景 #F2F2F0，柔和渐变光影，主体居中完整露出，干净且有层次",
    ),
    StyleDefinition(
        "flat_lay",
        "平铺图",
        "正面俯拍，整理平整",
        "服装平铺于纯白台面，正面俯拍，衣身整理平整，轮廓舒展，纽扣与细节自然呈现",
    ),
    StyleDefinition(
        "ghost_mannequin",
        "隐形人台",
        "立体轮廓，无人物出镜",
        "隐形人台立体支撑，正面展示，服装轮廓饱满自然，领口与袖型挺括，无人物出镜",
    ),
)

SCENE_STYLES = (
    StyleDefinition(
        "city",
        "都市街拍",
        "建筑、街道与现代城市光",
        "现代都市街区，玻璃建筑与街道轻微虚化，午后自然光，都市通勤氛围",
    ),
    StyleDefinition(
        "outdoor",
        "自然户外",
        "柔和日光与绿植",
        "自然户外环境，柔和日光，绿植与远景虚化，清新通透，真实环境光",
    ),
    StyleDefinition(
        "resort",
        "度假海边",
        "暖阳、海风与松弛感",
        "度假海边，暖色日光，海面与天空柔和虚化，轻松通透，空气感",
    ),
    StyleDefinition(
        "interior",
        "极简室内",
        "白墙、木地板与自然窗光",
        "极简室内空间，白墙与浅木地板，窗边自然光，低饱和、安静、有质感",
    ),
    StyleDefinition(
        "gray_studio",
        "高级灰棚",
        "干净背景与商业光效",
        "高级灰商业棚拍，干净无缝背景，柔光与轮廓光结合，主体立体，质感高级",
    ),
)

DETAIL_STYLES = (
    StyleDefinition(
        "fabric",
        "面料纹理",
        "微距呈现织物肌理",
        "面料微距特写，浅景深，经纬纹理、织法、厚度与垂坠感清晰可见，颜色准确",
    ),
    StyleDefinition(
        "neckline",
        "领口结构",
        "领型、包边与走线",
        "领口细节特写，清晰呈现领型、包边、内里与走线结构，边缘干净",
    ),
    StyleDefinition(
        "cuff",
        "袖口细节",
        "袖型、收口与纽扣",
        "袖口细节特写，清晰呈现袖型、收口、纽扣与缝线，构图简洁",
    ),
    StyleDefinition(
        "stitching",
        "走线工艺",
        "缝线密度与工艺",
        "缝制工艺特写，清晰呈现走线密度、针脚、拼接与包边，突出做工质感",
    ),
    StyleDefinition(
        "print",
        "印花图案",
        "图案清晰、色彩准确",
        "印花与图案局部特写，完整呈现图案边缘、颜色与套印质感，避免色偏",
    ),
    StyleDefinition(
        "hardware",
        "拉链五金",
        "拉链、纽扣与金属件",
        "拉链、纽扣或金属配件特写，清晰呈现材质、光泽、刻字与安装工艺",
    ),
)

FIVE_SHOTS_STYLES = (
    StyleDefinition(
        "five",
        "五图套图",
        "两张商品图自动生成主图、版型、细节、场景、补充信息",
        "两张原始商品图决定商品；首张成片作为后续四张的人物与系列一致性参考",
    ),
)

STYLE_GROUPS: dict[str, tuple[StyleDefinition, ...]] = {
    "try_on": TRY_ON_STYLES,
    "white_bg": WHITE_BG_STYLES,
    "scene": SCENE_STYLES,
    "detail": DETAIL_STYLES,
    "five_shots": FIVE_SHOTS_STYLES,
}

STYLE_PROMPTS_EN: dict[str, dict[str, str]] = {
    "try_on": {
        "studio": "Premium commercial studio, pale grey seamless background, soft key light with gentle fill, restrained low-saturation styling.",
        "street": "Urban street style, natural daylight, softly separated architectural background, candid everyday mood.",
        "commute": "Modern office interior, window daylight, refined low-saturation palette and understated styling.",
        "resort": "Resort setting, warm natural sunlight, airy and relaxed atmosphere, transparent tonal range.",
    },
    "white_bg": {
        "white": "Pure white seamless background #FFFFFF, soft contact shadow, product centered and fully visible, marketplace main-image discipline.",
        "light_gray": "Light grey seamless background #F2F2F0, gentle gradient and soft shadow, clean layered studio light.",
        "flat_lay": "Top-down flat-lay on a clean white surface, garment arranged smoothly with visible closures and construction.",
        "ghost_mannequin": "Invisible mannequin support, three-dimensional garment shape, no visible person, clean neckline and sleeve structure.",
    },
    "scene": {
        "city": "Modern urban street, glass architecture and street detail softly separated, afternoon daylight, polished city mood.",
        "outdoor": "Natural outdoor setting, soft daylight, greenery and distant scenery gently blurred, fresh and airy.",
        "resort": "Resort coast, warm sunlight, sea and sky softly separated, relaxed editorial atmosphere.",
        "interior": "Minimal interior, white walls and pale wood floor, natural window light, quiet low-saturation mood.",
        "gray_studio": "Premium grey studio, seamless background, soft key with subtle rim light, crisp dimensional product presentation.",
    },
    "detail": {
        "fabric": "Macro fabric detail, shallow depth of field, visible weave, thickness and drape.",
        "neckline": "Close detail of the neckline, showing the collar shape, binding and topstitching clearly.",
        "cuff": "Close detail of the cuff, showing the sleeve finish, closures and stitching.",
        "stitching": "Close detail of seam construction, stitch density, topstitching and edge finishing.",
        "print": "Close detail of the print, preserving pattern edges, registration and color.",
        "hardware": "Close detail of zipper, buttons or metal hardware, preserving material, finish and installation.",
    },
    "five_shots": {
        "five": "Five coordinated e-commerce photographs from two original product images.",
    },
}

DEFAULTS: dict[str, dict] = {
    "try_on": {
        "style": "studio",
        "gender": "female",
        "shot": "full_body",
        "pose": "natural",
        "side": "front",
        "size": "1024x1536",
        "quality": "auto",
    },
    "white_bg": {
        "style": "white",
        "gender": "female",
        "shot": "full_body",
        "pose": "natural",
        "side": "front",
        "size": "1024x1024",
        "quality": "auto",
    },
    "scene": {
        "style": "city",
        "gender": "female",
        "shot": "full_body",
        "pose": "natural",
        "side": "front",
        "size": "1024x1536",
        "quality": "auto",
    },
    "detail": {
        "style": "fabric",
        "gender": "female",
        "shot": "half_body",
        "pose": "natural",
        "side": "front",
        "size": "1024x1024",
        "quality": "auto",
    },
    "five_shots": {
        "style": "five",
        "gender": "female",
        "shot": "full_body",
        "pose": "natural",
        "side": "front",
        "size": "1024x1024",
        "quality": "auto",
    },
}

INSTRUCTION_HINTS: dict[str, list[str]] = {
    "try_on": ["自然站姿", "手指放松", "保留皮肤纹理", "真实的接触阴影", "衣服褶皱自然"],
    "white_bg": ["边缘干净", "完整露出", "轻微接触阴影", "不要漂浮感"],
    "scene": ["午后暖光", "阴天柔光", "背景更虚化", "阴影方向一致"],
    "detail": ["纹理更清晰", "颜色更准确", "浅景深", "突出做工"],
    "five_shots": ["套装要完整展示", "保持同一模特", "背面只按原图证据", "细节不要重复"],
}

WORKFLOW_LABELS = {
    "try_on": "模特试穿",
    "white_bg": "白底 / 平铺",
    "scene": "场景换背景",
    "detail": "面料 / 细节",
    "five_shots": "五图套图",
}

WORKFLOW_DESCRIPTIONS = {
    "try_on": "服装图 + 模特图，或让 AI 生成模特穿着效果",
    "white_bg": "生成电商白底主图、平铺图或隐形人台图",
    "scene": "保留服装主体，替换为街拍、户外、度假等场景",
    "detail": "生成面料、领口、走线、印花等卖点特写",
    "five_shots": "上传两张同款商品图，一次生成主图、版型、细节、场景、补充信息五张独立照片",
}

INPUT_LABELS = {
    "try_on": [
        {"role": "garment", "label": "服装图", "required": True, "hint": "实物商品图，决定颜色与细节"},
        {"role": "model", "label": "模特图", "required": False, "hint": "可选；可上传正面/侧面/背面三视图"},
        {"role": "approved", "label": "认可成片", "required": False, "hint": "可选；用于统一质感与上身比例"},
    ],
    "white_bg": [
        {"role": "garment", "label": "服装图", "required": True, "hint": "建议正面或背面完整平铺/挂拍"},
        {"role": "reference", "label": "补充参考", "required": False, "hint": "可选，用于补充背面或细节"},
    ],
    "scene": [
        {"role": "garment", "label": "主体图", "required": True, "hint": "服装或穿着效果图均可"},
        {"role": "reference", "label": "补充参考", "required": False, "hint": "可选，用于补充细节"},
    ],
    "detail": [
        {"role": "garment", "label": "服装图", "required": True, "hint": "建议清晰展示目标细节区域"},
        {"role": "reference", "label": "补充参考", "required": False, "hint": "可选，用于补充纹理或背面"},
    ],
    "five_shots": [
        {"role": "garment", "label": "商品图 1", "required": True, "hint": "优先确定主体颜色与款式"},
        {"role": "reference", "label": "商品图 2", "required": True, "hint": "补充上身比例、角度或局部信息"},
    ],
}

VALID_SIZES = ("1024x1024", "1024x1536", "1536x1024")
VALID_QUALITIES = ("auto", "low", "medium", "high")


class PromptValidationError(ValueError):
    pass


def get_styles(workflow: WorkflowId) -> tuple[StyleDefinition, ...]:
    return STYLE_GROUPS[workflow]


def normalize_options(workflow: WorkflowId, options: JobOptions) -> JobOptions:
    data = options.model_dump()
    default = DEFAULTS[workflow]
    if not data.get("style"):
        data["style"] = default["style"]
    style_ids = {item.id for item in get_styles(workflow)}
    if data["style"] not in style_ids:
        raise PromptValidationError(f"不支持的风格：{data['style']}")
    if data["size"] not in VALID_SIZES:
        raise PromptValidationError("不支持的图片尺寸")
    if data["quality"] not in VALID_QUALITIES:
        raise PromptValidationError("不支持的画质档位")
    return JobOptions(**data)


def validate_input_roles(workflow: WorkflowId, inputs: list[InputAssetIn]) -> None:
    if not inputs:
        raise PromptValidationError("请至少上传一张服装图")
    if len(inputs) > 4:
        raise PromptValidationError("参考图最多 4 张（含改图对象）")
    asset_ids = [item.asset_id for item in inputs]
    if len(asset_ids) != len(set(asset_ids)):
        raise PromptValidationError("同一张图片不能重复作为不同角色")

    counts: dict[str, int] = {}
    for item in inputs:
        counts[item.role] = counts.get(item.role, 0) + 1
    if workflow == "five_shots":
        if len(inputs) != 2:
            raise PromptValidationError("五图套图需要恰好 2 张同款商品图")
        if counts.get("garment", 0) != 1 or counts.get("reference", 0) != 1:
            raise PromptValidationError("五图套图需要商品图 1 和商品图 2 各一张")
        if counts.get("model") or counts.get("approved") or counts.get("edit_target"):
            raise PromptValidationError("五图套图不需要模特图、认可成片或改图对象")
        return
    if counts.get("garment", 0) != 1:
        raise PromptValidationError("需要且只能有 1 张服装主图")
    for role in ("model", "approved", "edit_target"):
        if counts.get(role, 0) > 1:
            raise PromptValidationError(f"{role} 参考图最多 1 张")
    if workflow != "try_on" and counts.get("model", 0):
        raise PromptValidationError("当前模式不支持模特图")
    if workflow == "try_on":
        if counts.get("reference", 0) > 2:
            raise PromptValidationError("试穿模式最多 2 张补充参考图")
    elif workflow == "white_bg":
        if counts.get("reference", 0) > 3:
            raise PromptValidationError("白底模式最多 3 张补充参考图")
    elif workflow == "scene":
        if counts.get("reference", 0) > 3:
            raise PromptValidationError("场景模式最多 3 张补充参考图")
    elif workflow == "detail":
        if counts.get("reference", 0) > 2:
            raise PromptValidationError("细节模式最多 2 张补充参考图")


def _style_prompt(workflow: WorkflowId, style_id: str | None) -> str:
    styles = get_styles(workflow)
    style = next((item for item in styles if item.id == style_id), None)
    if style is None:
        raise PromptValidationError(f"不支持的风格：{style_id}")
    return STYLE_PROMPTS_EN[workflow][style.id]


def _role_lines(roles: list[str]) -> str:
    mapping = {
        "garment": (
            "ACTUAL PRODUCT: authoritative for visible garment design, color, construction, "
            "fit, prints and existing marks."
        ),
        "model": (
            "MODEL IDENTITY: authoritative for face, hairstyle, skin tone and body proportions. "
            "If this image contains multiple views or several panels, use it only as identity "
            "evidence and do not reproduce the sheet layout."
        ),
        "approved": (
            "USER-APPROVED RESULT: positive reference for photographic treatment, garment fit "
            "and fabric drape; product design still follows the actual product image."
        ),
        "reference": (
            "SUPPLEMENTARY PRODUCT REFERENCE: extra view or detail of the product. It can "
            "support construction evidence but cannot override the actual product image."
        ),
        "edit_target": (
            "EDIT TARGET: the image to revise. Its current flaws are what must change; do not "
            "copy its stiffness, lighting problems or other defects as the desired style."
        ),
    }
    return "\n".join(
        f"Image {index}: {mapping[role]}" for index, role in enumerate(roles, start=1)
    )


def _image_index(roles: list[str], role: str) -> int | None:
    try:
        return roles.index(role) + 1
    except ValueError:
        return None


def _shot_direction(
    workflow: WorkflowId,
    options: JobOptions,
    roles: list[str],
) -> str:
    if workflow == "try_on":
        gender = "female" if options.gender == "female" else "male"
        if options.shot == "half_body":
            base = (
                "Waist-up commercial product photograph. Keep the complete head, shoulders, "
                "hands and garment body readable with clean margins."
            )
        elif options.side == "back":
            base = (
                "Back full-length product photograph. Show the complete head and both feet, "
                "back construction, shoulder fit and lower-garment drape. Keep hands clear of "
                "the garment."
            )
        else:
            base = (
                "Front full-length product photograph. Show the entire head and both feet with "
                "clean margins; keep the garment front and all product details readable."
            )
        if options.side == "back":
            base += (
                " Only assert back-specific construction supported by an actual back reference; "
                "if none exists, keep the back conservative and do not invent seams, pockets or logos."
            )
        pose = (
            "Use a natural weight shift, relaxed shoulders, loosely curved fingers and an "
            "unforced expression."
            if options.pose == "natural"
            else "Use a controlled editorial pose while keeping the body, hands and garment realistic."
        )
        return f"{base} The subject is one adult {gender} model. {pose}"
    if workflow == "white_bg":
        side = "front" if options.side == "front" else "back"
        if options.style == "flat_lay":
            return (
                "Top-down flat-lay product photograph on a clean white surface. Arrange the "
                f"garment smoothly and show the {side} side completely; keep closures and "
                "construction readable. No person."
            )
        if options.style == "ghost_mannequin":
            return (
                f"Invisible-mannequin product photograph, {side} view, three-dimensional "
                "garment shape, no visible person. Keep the neckline and sleeve structure "
                "natural and complete."
            )
        return (
            f"{side.capitalize()} product photograph, garment fully visible and centered. "
            "Show the complete silhouette with clean margins. No person."
        )
    if workflow == "scene":
        return (
            "Natural lifestyle product photograph. Place the garment naturally in the scene, "
            "keeping the outfit and key selling details visible. Use a believable composition "
            "and a natural floor/contact relationship. No additional person unless explicitly requested."
        )
    return (
        "Close product photograph of the requested detail. Keep the target area sharp, "
        "unobstructed and large enough to read construction and material. Hands and props must "
        "not cover it. The face need not appear."
    )


def _model_section(
    workflow: WorkflowId,
    options: JobOptions,
    roles: list[str],
) -> str:
    model_index = _image_index(roles, "model")
    if model_index:
        return (
            f"The same adult model as Image {model_index}. Preserve the recognizable face, "
            "skin tone, hairstyle and body proportions. Another person in a fit or scene "
            "reference must not replace this identity."
        )
    if workflow == "try_on":
        gender = "female" if options.gender == "female" else "male"
        return (
            f"Generate one adult {gender} model who plausibly wears the product. Keep the "
            "face, skin tone, hands and body proportions realistic and consistent."
        )
    return (
        "No person is required. This is a product-only photograph; do not add a face, person "
        "or visible mannequin. An invisible mannequin is allowed only when the shot explicitly asks for it."
    )


def _orientation(size: str) -> str:
    if size == "1024x1536":
        return "portrait 2:3"
    if size == "1536x1024":
        return "landscape 3:2"
    return "square 1:1"


def build_prompt(
    workflow: WorkflowId,
    options: JobOptions,
    instruction: str,
    roles: list[str],
) -> str:
    if workflow == "five_shots":
        raise PromptValidationError("五图套图请使用专用提示词构建器")
    style_prompt = _style_prompt(workflow, options.style)
    model_section = _model_section(workflow, options, roles)
    shot = _shot_direction(workflow, options, roles)
    has_edit_target = "edit_target" in roles
    clean_instruction = instruction.strip()

    revision = (
        f"Revise Image {_image_index(roles, 'edit_target')} (the edit target), changing only "
        "the specific issues in the user's feedback. Preserve the model identity, garment "
        "design and any explicit composition requirement. If the feedback asks to change the "
        "pose, allow a natural re-photograph instead of locking the old rigid pose. Do not "
        "carry over the edit target's defects. User feedback: " + clean_instruction
        if has_edit_target and clean_instruction
        else (
            "Revise the edit target only where the supplied feedback asks; preserve the model "
            "identity and garment design."
            if has_edit_target
            else "Initial generation. Follow any approved references while keeping the actual "
            "product and model identity authoritative."
        )
    )

    notes = (
        ""
        if has_edit_target or not clean_instruction
        else f"\nAdditional user notes: {clean_instruction}"
    )

    return "\n".join(
        [
            "Create ONE standalone e-commerce clothing photograph.",
            "",
            "REFERENCE ROLES — match these numbers to the attached image order:",
            _role_lines(roles),
            "",
            "MODEL IDENTITY:",
            model_section,
            "",
            "GARMENT — the actual product reference is authoritative:",
            GLOBAL_PRESERVE
            + " Only assert exact product fidelity for details supported by actual product "
            "references; do not fabricate unseen features.",
            "",
            "SHOT:",
            shot,
            "",
            "SCENE AND PHOTOGRAPHY:",
            style_prompt,
            GLOBAL_NATURAL,
            "",
            "REVISION TARGET:",
            revision,
            notes,
            "",
            "OUTPUT:",
            f"One standalone {_orientation(options.size)} photograph, intended for e-commerce "
            "product display. Keep important garment areas sharp and unobstructed. "
            + GLOBAL_OUTPUT,
        ]
    )


def get_meta(max_reference_images: int = 4) -> dict:
    workflows = []
    for workflow in ("try_on", "white_bg", "scene", "detail", "five_shots"):
        entry = {
            "id": workflow,
            "label": WORKFLOW_LABELS[workflow],
            "description": WORKFLOW_DESCRIPTIONS[workflow],
            "inputs": INPUT_LABELS[workflow],
            "styles": [style.as_dict() for style in get_styles(workflow)],
            "defaults": DEFAULTS[workflow],
            "instruction_hints": INSTRUCTION_HINTS[workflow],
            "max_reference_images": max_reference_images,
        }
        if workflow == "five_shots":
            entry["shot_plan"] = plan_meta()
        workflows.append(entry)
    return {
        "workflows": workflows,
        "sizes": [
            {"value": "1024x1024", "label": "方图 1:1"},
            {"value": "1024x1536", "label": "竖图 2:3"},
            {"value": "1536x1024", "label": "横图 3:2"},
        ],
        "qualities": [
            {"value": "auto", "label": "自动"},
            {"value": "low", "label": "快速"},
            {"value": "medium", "label": "均衡"},
            {"value": "high", "label": "精细"},
        ],
        "max_reference_images": max_reference_images,
    }
