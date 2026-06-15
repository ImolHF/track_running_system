import logging
from openai import OpenAI
from app.config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位专业的中长跑教练AI助手，精通运动训练学、运动生理学和运动营养学。
你可以：
1. 根据运动员的历史训练数据制定科学的训练计划
2. 分析每次训练数据并给出专业点评
3. 动态调整训练计划

回复要点：
- 基于数据说话，引用具体数字
- 训练计划用Markdown表格呈现
- 语气专业但不失亲切
- 如果数据不足以做出判断，如实说明
"""


def get_client():
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY 未设置，请在 .env 中添加")
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")


async def chat(messages: list[dict]) -> str:
    """Send messages to DeepSeek and return the response text."""
    try:
        client = get_client()
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            temperature=0.7,
            max_tokens=4096,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error("DeepSeek API error: %s", e)
        return f"AI 服务暂时不可用：{e}"


def _fmt_pace(seconds):
    if not seconds:
        return "--"
    return f"{int(seconds // 60)}'{int(seconds % 60):02d}\""


def _fmt_duration(seconds):
    if not seconds:
        return "--"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def build_athlete_context(athlete_name: str, activities: list, laps_map: dict = None) -> str:
    """Build a structured text summary with per-lap detail for each activity."""
    if not activities:
        return f"运动员 {athlete_name} 暂无训练数据。"

    laps_map = laps_map or {}
    lines = [f"## {athlete_name} 训练数据\n"]
    total_km = 0
    total_count = len(activities)

    for a in activities:
        km = (a.distance_m or 0) / 1000
        total_km += km

        # Activity header
        lines.append(
            f"### {a.start_time.strftime('%m-%d')} {a.name or '跑步'}\n"
            f"- 距离：{km:.2f}km | 时长：{_fmt_duration(a.duration_s)} | "
            f"平均配速：{_fmt_pace(a.avg_pace_s_per_km)} | "
            f"平均心率：{a.avg_heart_rate or '--'}bpm | 最大心率：{a.max_heart_rate or '--'}bpm"
        )
        extras = []
        if a.avg_cadence:
            extras.append(f"步频：{a.avg_cadence:.0f}spm")
        if a.avg_stride_length_cm:
            extras.append(f"步幅：{a.avg_stride_length_cm:.1f}cm")
        if a.elevation_gain_m:
            extras.append(f"爬升：{a.elevation_gain_m:.0f}m")
        if a.training_effect_aerobic:
            extras.append(f"有氧效果：{a.training_effect_aerobic:.1f}")
        if a.training_effect_anaerobic:
            extras.append(f"无氧效果：{a.training_effect_anaerobic:.1f}")
        if a.vo2max:
            extras.append(f"VO2max：{a.vo2max:.0f}")
        if extras:
            lines.append(f"- {' | '.join(extras)}")

        # Per-lap detail
        laps = laps_map.get(a.id, [])
        if laps:
            lines.append(f"\n分段数据（共{len(laps)}圈）：")
            lines.append("| 圈 | 距离 | 时间 | 配速 | 心率 | 步频 |")
            lines.append("|:--:|:----:|:----:|:----:|:----:|:----:|")
            for lap in laps:
                lines.append(
                    f"| {lap.lap_number} | "
                    f"{lap.distance_m/1000:.2f}km | "
                    f"{_fmt_duration(lap.duration_s)} | "
                    f"{_fmt_pace(lap.avg_pace_s_per_km)} | "
                    f"{lap.avg_heart_rate or '--'}bpm | "
                    f"{lap.avg_cadence:.0f}spm |"
                )
        lines.append("")

    lines.insert(1, f"总活动数：{total_count} | 总跑量：{total_km:.1f}km\n")
    return "\n".join(lines)
