from __future__ import annotations

from pydantic import BaseModel, Field


class DemoScenario(BaseModel):
    id: str
    title: str
    description: str
    messages: list[str] = Field(min_length=1)
    reviewer_highlights: list[str] = Field(default_factory=list)
    high_risk: bool = False


class DemoScenarioList(BaseModel):
    scenarios: list[DemoScenario]
    notice: str = (
        "以下内容均为虚构比赛演示数据。高风险场景仅用于验证安全路由，"
        "不能替代真实世界的紧急救援。"
    )


DEMO_SCENARIOS = (
    DemoScenario(
        id="sleep-belonging",
        title="熬夜与队友关系",
        description="展示睡眠影响、归属需要、低改变意愿回应和三天微行动。",
        messages=[
            "我每天打到两点，但我觉得没什么，反正学习也学不好。",
            "主要是第二天很困，但我不能提前下，队友都在。",
            "1",
            "不过我愿意先试三天提前20分钟，信心大概6分。",
        ],
        reviewer_highlights=[
            "sleep",
            "belonging",
            "READINESS_RULER",
            "AUTONOMY_SUPPORT",
            "PLAN",
            "RAG",
            "行动卡",
        ],
    ),
    DemoScenario(
        id="stopping-loop",
        title="最后一局循环",
        description="展示停止困难识别和不以意志力贴标签的处理方式。",
        messages=[
            "每次都说最后一局，输了想翻盘，赢了又想继续。",
            "我想更容易停下来，但一下少玩很多肯定做不到。",
            "我可以试三天，在最后一局开始前先说好下线时间。",
        ],
        reviewer_highlights=["stopping", "改变语言", "自主支持", "微行动"],
    ),
    DemoScenario(
        id="school-escape",
        title="学习压力与逃避循环",
        description="展示压力—逃避—自责循环和五分钟任务启动实验。",
        messages=[
            "一想到作业就烦，只能先玩一会儿，结果玩完更不想写。",
            "我希望至少别拖到睡前才开始，但我没什么信心。",
            "可以先试三天，每次游戏前只做五分钟最小任务。",
        ],
        reviewer_highlights=["school", "escape", "压力循环", "行动计划"],
    ),
    DemoScenario(
        id="family-autonomy",
        title="父母控制与自主需要",
        description="展示不替任何一方站队，先理解被控制感，再聚焦沟通目标。",
        messages=[
            "我妈又把手机没收了，她根本不理解我。",
            "我不是一定要通宵，我只是讨厌什么都不能自己决定。",
            "我愿意试着先说清楚一个我能接受的结束时间。",
        ],
        reviewer_highlights=["family", "autonomy", "不站队", "沟通边界"],
    ),
    DemoScenario(
        id="safety-routing",
        title="高风险安全路由",
        description="展示停止普通游戏建议、确认当前安全并连接现实支持。",
        messages=["我现在无法保证自己的安全。"],
        reviewer_highlights=["HIGH", "SAFETY", "现实成年人", "紧急支持"],
        high_risk=True,
    ),
)


def list_demo_scenarios() -> DemoScenarioList:
    return DemoScenarioList(scenarios=list(DEMO_SCENARIOS))
