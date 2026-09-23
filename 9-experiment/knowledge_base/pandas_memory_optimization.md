# Pandas 内存占用优化指南

## 一、先量化：找到内存去向

优化前先用 `DataFrame.memory_usage(deep=True)` 查看每列的真实占用。默认的 `memory_usage()` 不统计 object 列指向的字符串本体，容易低估几十倍；只有 `deep=True` 会把每个 Python 字符串对象的开销算进来。

```python
import pandas as pd
df = pd.read_csv("large.csv")
print(df.memory_usage(deep=True).sort_values(ascending=False).head(10))
```

经验值：object 列里每个字符串平均占 50-80 字节（Python 对象头 + 指针），而等长的定长字符串列在 Arrow 后端下只占几字节。

## 二、dtype 降级：收益最大的一步

Pandas 读取时默认用 int64 / float64。如果数值范围放得下，降到更窄的类型可以立省一半以上内存。

- 整数：`int64 -> int32 -> int16 -> int8`，用 `pd.to_numeric(df[c], downcast="integer")` 自动选最小可用类型。
- 浮点：`float64 -> float32` 精度约 7 位有效数字，多数分析场景够用。
- 布尔：三态列用 `boolean`（可空），不要用 object。

```python
for col in df.select_dtypes("integer").columns:
    df[col] = pd.to_numeric(df[col], downcast="integer")
for col in df.select_dtypes("float").columns:
    df[col] = pd.to_numeric(df[col], downcast="float")
```

## 三、category：重复字符串的克星

取值重复度高的字符串列（如省份、渠道、状态）转成 `category` 后，内存只取决于类别数，与行数无关。经验阈值：唯一值占比低于 50% 就可以考虑。

```python
df["channel"] = df["channel"].astype("category")
```

注意：类别数极多（如用户 ID）时 category 反而更占内存，先算 `df[c].nunique()` 再决定。

## 四、读取阶段就省内存

- 用 `usecols` 只读需要的列，用 `dtype` 显式指定类型，避免先读成 object 再转换。
- 用 `chunksize` 分块读取，逐块聚合后再合并，峰值内存只与块大小相关。

```python
dtypes = {"user_id": "int32", "amount": "float32", "channel": "category"}
total = 0.0
for chunk in pd.read_csv("large.csv", usecols=list(dtypes), dtype=dtypes, chunksize=500_000):
    total += chunk["amount"].sum()
```

## 五、稀疏与对象列

- 大量 0 的数值矩阵用 `pd.SparseDtype("float32", fill_value=0)`，内存与稀疏度成正比。
- Pandas 2.x 起可用 Arrow 字符串后端：`pd.read_csv(..., dtype_backend="pyarrow")`，字符串列不再产生 Python 对象开销，跨列计算也更快。
- 确认不再使用的中间 DataFrame 及时 `del`，再 `gc.collect()`，尤其在大 join 之后。

## 六、其他常见手法

- 用 `pd.merge` 前先对 join key 做 dtype 对齐，避免隐式 upcast 复制整表。
- 时间列用 `datetime64[ns]`，不要保留成字符串。
- 排序 / 去重优先在列子集上做，减少临时副本。
- 需要重复计算的结果落成列，避免每次重算产生的临时对象。

综合下来，一个 10 GB 的宽表按上述步骤处理，通常可以降到 2-3 GB；其中 dtype 降级与 category 转换贡献最大。
