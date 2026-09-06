"""三国人物与狼人杀身份配置。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlayerProfile:
    """一名玩家的公开人物身份与私密游戏身份。"""

    name: str
    role: str
    trait: str


ROLE_ABILITIES = {
    "狼人": "夜晚与同伴密议并击杀一名好人；白天隐藏身份。",
    "预言家": "每晚可以查验一名存活玩家的阵营。",
    "女巫": "拥有解药和毒药各一瓶，每瓶整局只能使用一次。",
    "村民": "没有夜间技能，依靠发言、推理和投票找出狼人。",
}


# 固定阵容便于复现实验输出，也与教程示例中的六人局保持一致。
STANDARD_ROSTER = (
    PlayerProfile("孙权", "狼人", "江东之主，年轻果决，善于权衡联盟与利害"),
    PlayerProfile("周瑜", "狼人", "儒将风骨，才思敏捷，谋略缜密而略带傲气"),
    PlayerProfile("曹操", "预言家", "雄才大略，善察人心，言辞犀利且多疑"),
    PlayerProfile("张飞", "女巫", "豪爽刚烈，嫉恶如仇，说话直截了当"),
    PlayerProfile("司马懿", "村民", "深谋远虑，善于隐忍，习惯后发制人"),
    PlayerProfile("赵云", "村民", "忠勇沉着，言简意赅，重视事实与道义"),
)


def role_ability(role: str) -> str:
    """返回游戏身份的能力说明。"""

    return ROLE_ABILITIES[role]


def is_werewolf(role: str) -> bool:
    """判断角色是否属于狼人阵营。"""

    return role == "狼人"

