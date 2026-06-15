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


def build_athlete_context(athlete_name: str, activities: list) -> str:
    """Build a structured text summary of an athlete's training data."""
    if not activities:
        return f"运动员 {athlete_name} 暂无训练数据。"

    lines = [f"## {athlete_name} 训练数据汇总\n"]
    total_km = 0
    total_count = len(activities)

    for a in activities:
        km = (a.distance_m or 0) / 1000
        total_km += km
        pace = a.avg_pace_s_per_km or 0
        pace_str = f"{int(pace // 60)}'{int(pace % 60):02d}\"" if pace else "--"
        hr = a.avg_heart_rate or "--"
        lines.append(
            f"- {a.start_time.strftime('%m-%d')} | "
            f"{km:.1f}km | "
            f"配速{pace_str} | "
            f"心率{hr}bpm | "
            f"{a.name or '跑步'}"
        )

    lines.insert(1, f"总活动数：{total_count} | 总跑量：{total_km:.1f}km\n")
    return "\n".join(lines)
