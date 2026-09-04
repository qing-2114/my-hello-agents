"""Experiment 3.2: run Qwen1.5-0.5B-Chat locally with Transformers.

The default settings mirror the Hello-Agents Chapter 3.2.3 example:
greedy decoding with a maximum of 512 newly generated tokens.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


DEFAULT_MODEL_ID = "Qwen/Qwen1.5-0.5B-Chat"
DEFAULT_PROMPT = "你好，请介绍你自己。"


@dataclass(frozen=True)
class GenerationConfig:
    """Generation parameters exposed by the command-line experiment."""

    max_new_tokens: int = 512
    do_sample: bool = False
    temperature: float = 0.7
    top_p: float = 0.9


def select_device() -> str:
    """Prefer CUDA when it is available, otherwise use CPU."""

    return "cuda" if torch.cuda.is_available() else "cpu"


def build_inputs(tokenizer, user_prompt: str, device: str):
    """Apply Qwen's chat template and move tokenized inputs to ``device``."""

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": user_prompt},
    ]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    return tokenizer([text], return_tensors="pt").to(device)


def generate_response(model, tokenizer, model_inputs, config: GenerationConfig) -> str:
    """Generate and decode only the newly generated assistant tokens."""

    generation_kwargs = {"max_new_tokens": config.max_new_tokens}
    if config.do_sample:
        generation_kwargs.update(
            do_sample=True,
            temperature=config.temperature,
            top_p=config.top_p,
        )

    with torch.inference_mode():
        output_ids = model.generate(
            input_ids=model_inputs.input_ids,
            attention_mask=model_inputs.attention_mask,
            **generation_kwargs,
        )

    new_token_ids = [
        output[len(prompt) :]
        for prompt, output in zip(model_inputs.input_ids, output_ids)
    ]
    return tokenizer.batch_decode(new_token_ids, skip_special_tokens=True)[0].strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use stochastic sampling instead of the tutorial's greedy decoding.",
    )
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.9)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_new_tokens <= 0:
        raise SystemExit("--max-new-tokens 必须是正整数")
    if args.sample and args.temperature <= 0:
        raise SystemExit("启用 --sample 时，--temperature 必须大于 0")
    if args.sample and not 0 < args.top_p <= 1:
        raise SystemExit("启用 --sample 时，--top-p 必须在 (0, 1] 范围内")

    device = select_device()
    print(f"Using device: {device}")
    print(f"Loading model: {args.model_id}")
    print("首次运行会下载模型文件，后续运行将使用本地缓存。")

    tokenizer = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        torch_dtype="auto",
    ).to(device)
    model.eval()
    print("模型和分词器加载完成！")

    model_inputs = build_inputs(tokenizer, args.prompt, device)
    print("编码后的输入文本:")
    print(model_inputs)

    response = generate_response(
        model,
        tokenizer,
        model_inputs,
        GenerationConfig(
            max_new_tokens=args.max_new_tokens,
            do_sample=args.sample,
            temperature=args.temperature,
            top_p=args.top_p,
        ),
    )
    print("\n模型的回答:")
    print(response)


if __name__ == "__main__":
    main()
