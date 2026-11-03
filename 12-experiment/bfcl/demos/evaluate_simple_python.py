"""运行教程中的五样本 BFCL 真实 API 评估。"""

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from hello_agents import HelloAgentsLLM, SimpleAgent
from hello_agents.tools import BFCLEvaluationTool


def main():
    root = Path(__file__).resolve().parents[3]
    load_dotenv(root / ".env", override=True)
    required = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL_ID")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"根目录 .env 缺少配置：{', '.join(missing)}")

    bfcl = Path(__file__).resolve().parents[1]
    output = bfcl / "runs" / datetime.now().strftime("%Y%m%d_%H%M%S")
    output.mkdir(parents=True, exist_ok=True)
    os.environ["PATH"] = str(root / "12-experiment/.venv/Scripts") + os.pathsep + os.environ["PATH"]
    os.environ["BFCL_PROJECT_ROOT"] = str(output)

    llm = HelloAgentsLLM()
    agent = SimpleAgent(name="TestAgent", llm=llm)
    bfcl_tool = BFCLEvaluationTool(
        bfcl_data_dir=str(bfcl / "data/temp_gorilla/berkeley-function-call-leaderboard/bfcl_eval/data"),
        project_root=str(output),
    )
    results = bfcl_tool.run(agent=agent, category="simple_python", max_samples=5)
    print(f"准确率: {results['overall_accuracy']:.2%}")
    print(f"正确数: {results['correct_samples']}/{results['total_samples']}")
    print(f"输出目录: {output}")


if __name__ == "__main__":
    main()
