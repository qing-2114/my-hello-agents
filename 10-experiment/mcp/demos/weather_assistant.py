"""在 SimpleAgent 中使用天气 MCP。来源：https://hello-agents.datawhale.cc/"""

import sys
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from hello_agents import HelloAgentsLLM, SimpleAgent
from hello_agents.tools import MCPTool

SERVER_SCRIPT = Path(__file__).with_name("weather_mcp_server.py")
ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


def create_weather_assistant():
    config = dotenv_values(ENV_PATH)
    required = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL_ID")
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise RuntimeError("根目录 .env 缺少配置：" + ", ".join(missing))
    load_dotenv(ENV_PATH, override=True)
    weather_tool = MCPTool(server_command=[sys.executable, "-X", "utf8", str(SERVER_SCRIPT)])
    expanded_tools = weather_tool.get_expanded_tools()
    if not expanded_tools:
        raise RuntimeError("未发现天气 MCP 子工具，请检查服务脚本、依赖和启动日志")
    names = [tool.name for tool in expanded_tools]
    assistant = SimpleAgent(
        name="天气助手", llm=HelloAgentsLLM(),
        system_prompt=("你是天气助手。查询天气必须调用工具，支持中文城市名。"
                       "只能依据工具结果回答，返回 error 时说明查询失败，不编造天气。"
                       "不得从 Max retries exceeded 推断重试次数；本工具无应用层重试。"
                       "备用源会标注 Open-Meteo 和模型天气；visibility 为 null 表示无数据。"
                       "不要推断网络故障的具体责任方。服务器信息和城市列表不能验证上游天气接口健康。"
                       "这是当前天气而非全天预报；按 data_type 区分观测和模型数据，注意单位及实际解析地点。可用工具：" + ", ".join(names)),
    )
    for tool in expanded_tools:
        assistant.add_tool(tool)
    return assistant


def demo():
    assistant = create_weather_assistant()
    print(assistant.run("请调用天气工具查询北京当前天气，并说明数据来源。"))


def interactive():
    assistant = create_weather_assistant()
    while True:
        try:
            question = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in {"quit", "exit"}:
            break
        if question:
            print(f"助手: {assistant.run(question)}")


if __name__ == "__main__":
    demo() if len(sys.argv) > 1 and sys.argv[1] == "demo" else interactive()
