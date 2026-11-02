"""第十章：创建一个简单的 A2A 智能体（计算器）。

项目来源：https://hello-agents.datawhale.cc/
对应教程第十章示例代码，使用项目根目录 .conda 环境（hello-agents[protocols]==0.2.8）。
本示例只在本地直接调用技能函数，不启动 HTTP 服务器，也不调用 LLM。
"""

import sys

# Windows 控制台默认 GBK，打印 emoji 会报 UnicodeEncodeError
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from hello_agents.protocols.a2a.implementation import A2AServer, A2A_AVAILABLE


def create_calculator_agent():
    """创建一个计算器智能体"""
    if not A2A_AVAILABLE:
        print("❌ A2A SDK 未安装，请运行: pip install a2a-sdk")
        return None

    print("🧮 创建计算器智能体")

    # 创建 A2A 服务器
    calculator = A2AServer(
        name="calculator-agent",
        description="专业的数学计算智能体",
        version="1.0.0",
        capabilities={
            "math": ["addition", "subtraction", "multiplication", "division"],
            "advanced": ["power", "sqrt", "factorial"]
        }
    )

    # 添加基础计算技能
    @calculator.skill("add")
    def add_numbers(query: str) -> str:
        """加法计算"""
        try:
            # 简单解析 "计算 5 + 3" 格式
            # 先替换 "加上" 再替换 "加"，否则 "加上" 会变成 "+上"（教程原代码的顺序有此问题）
            parts = query.replace("计算", "").replace("加上", "+").replace("加", "+")
            if "+" in parts:
                numbers = [float(x.strip()) for x in parts.split("+")]
                result = sum(numbers)
                return f"计算结果: {' + '.join(map(str, numbers))} = {result}"
            else:
                return "请使用格式: 计算 5 + 3"
        except Exception as e:
            return f"计算错误: {e}"

    @calculator.skill("multiply")
    def multiply_numbers(query: str) -> str:
        """乘法计算"""
        try:
            parts = query.replace("计算", "").replace("乘以", "*").replace("×", "*")
            if "*" in parts:
                numbers = [float(x.strip()) for x in parts.split("*")]
                result = 1
                for num in numbers:
                    result *= num
                return f"计算结果: {' × '.join(map(str, numbers))} = {result}"
            else:
                return "请使用格式: 计算 5 * 3"
        except Exception as e:
            return f"计算错误: {e}"

    @calculator.skill("info")
    def get_info(query: str) -> str:
        """获取智能体信息"""
        return f"我是 {calculator.name}，可以进行基础数学计算。支持的技能: {list(calculator.skills.keys())}"

    print(f"✅ 计算器智能体创建成功，支持技能: {list(calculator.skills.keys())}")
    return calculator


if __name__ == "__main__":
    # 创建智能体
    calc_agent = create_calculator_agent()
    if calc_agent and "--serve" in sys.argv:
        # 启动 HTTP 服务器，供 a2a_calculator_client.py 调用
        # 只监听本机：A2AServer 没有任何鉴权，不要绑定 0.0.0.0 暴露到局域网
        calc_agent.run(host="127.0.0.1", port=5000)
    elif calc_agent:
        # 测试技能
        print("\n🧪 测试智能体技能:")
        test_queries = [
            "获取信息",
            "计算 10 + 5",
            "计算 6 * 7",
            "计算 2 加上 3",
            "计算 4 乘以 2.5",
        ]

        for query in test_queries:
            if "信息" in query:
                result = calc_agent.skills["info"](query)
            elif "+" in query or "加" in query:
                result = calc_agent.skills["add"](query)
            elif "*" in query or "×" in query or "乘以" in query:
                result = calc_agent.skills["multiply"](query)
            else:
                result = "未知查询类型"

            print(f"  📝 查询: {query}")
            print(f"  🤖 回复: {result}")
            print()
