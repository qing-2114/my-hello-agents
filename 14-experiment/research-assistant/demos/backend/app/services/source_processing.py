"""来源处理：保持首次出现顺序，不修改调用者的数据。"""


def deduplicate_sources(sources: list[dict]) -> list[dict]:
    seen_urls = set()
    unique_sources = []
    for source in sources:
        if source['url'] not in seen_urls:
            seen_urls.add(source['url'])
            unique_sources.append(dict(source))
    return unique_sources


def limit_source_tokens(source: dict, max_tokens: int = 2000) -> dict:
    """按1 token约4字符估算，省略号计入预算；不等同于模型分词器。"""
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
        raise ValueError('max_tokens 必须是正整数')
    snippet = source['snippet']
    max_chars = max_tokens * 4
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars - 3] + '...'
    return {**source, 'snippet': snippet}
