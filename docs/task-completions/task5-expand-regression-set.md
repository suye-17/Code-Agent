# Task 5 完成文档：扩充 Regression Set

## 任务目标

Task 5 的目标是把 `eval/regression_set/seed_cases.jsonl` 从 5 个 toy case 扩充到 15 个 case，并用自动化测试保证回归集质量。

这个任务服务于“专业测试集跑高分”的短期目标：让 B0 baseline 不再只对少量单文件 bug 过拟合，而是覆盖更多常见缺陷形态。

## 实现思路

### 先用测试定义回归集质量

新增 `tests/unit/test_regression_set.py`，检查三类约束：

- case 数量至少 15 个。
- case id 必须唯一。
- 每个 case 指向的 repo 目录必须存在，且包含 `test_*.py`。
- 每个 toy case 初始运行 pytest 必须失败，确保它们确实是待修复任务。

红灯阶段先运行：

```bash
.venv/bin/python -m pytest tests/unit/test_regression_set.py -q
```

失败原因符合预期：

```text
AssertionError: assert 5 >= 15
```

说明现有回归集规模不足。

### 新增 10 个 toy case

新增 case 覆盖不同缺陷类型：

| id | 缺陷类型 | 主要文件 |
|---|---|---|
| `boolean_logic` | 布尔条件写反 | `logic.py` |
| `list_utils` | 列表索引 off-by-one | `lists.py` |
| `dict_merge` | 字典合并优先级错误 | `merge.py` |
| `palindrome` | 字符串归一化缺失 | `text.py` |
| `clamp` | 上下界返回值反了 | `numbers.py` |
| `median` | 偶数长度中位数错误 | `stats.py` |
| `parser` | key/value 解析未 strip | `parser.py` |
| `csv_utils` | CSV 单元格未 trim | `csv_utils.py` |
| `config_defaults` | 缺少默认值处理 | `config.py` |
| `range_overlap` | 区间重叠逻辑取反 | `ranges.py` |

这些 case 都保持小而清晰，适合快速跑 baseline，同时比原来的 5 个 case 覆盖更多边界条件和错误类型。

## 核心代码说明

### `test_regression_set_has_minimum_case_count_and_unique_ids`

```python
cases = load_cases()
ids = [case["id"] for case in cases]

assert len(cases) >= 15
assert len(ids) == len(set(ids))
```

这个测试防止回归集规模退化，也防止重复 id 影响报告统计。

### `test_regression_set_repositories_exist_and_have_tests`

```python
repo = TOY_CASES / case["repo"]
assert repo.is_dir()
assert list(repo.glob("test_*.py"))
assert case["task"].strip()
```

这个测试保证 `seed_cases.jsonl` 中的每条记录都能被 `baseline_runner.py` 找到。

### `test_regression_set_cases_start_with_failing_tests`

```python
result = subprocess.run(
    [sys.executable, "-m", "pytest", "-q"],
    cwd=repo,
    capture_output=True,
    text=True,
    timeout=10,
)
assert result.returncode != 0
```

这个测试确保每个 toy case 初始状态确实失败，否则它就不是有效的 bug 修复任务。

## 测试结果

### Regression Set 质量测试

```bash
.venv/bin/python -m pytest tests/unit/test_regression_set.py -q
```

结果：

```text
3 passed in 4.70s
```

### 全量测试

```bash
.venv/bin/python -m pytest -q
```

结果：

```text
35 passed, 2 skipped in 7.87s
```

### Ruff 检查

```bash
.venv/bin/python -m ruff check .
```

结果：

```text
All checks passed!
```

## 功能交付

- `seed_cases.jsonl` 从 5 个 case 扩充到 15 个 case。
- 新增 10 个 toy case 目录，每个都有实现文件和 pytest 文件。
- 新增 regression set 质量测试，防止 case 数量、路径和初始失败状态退化。

## 性能交付

- baseline 覆盖面扩大，减少对少量 toy bug 的过拟合。
- 新增质量测试仍然在数秒内完成，适合作为常规单测运行。
- 后续跑 `eval/baseline_runner.py` 时可以得到更稳定的 B0 对照数据。
