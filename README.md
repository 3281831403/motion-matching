# 动作匹配：同帧特征与候选归一

高速转向时动作匹配抖动：查询用上一帧姿态、速度权重压过朝向、根运动重复叠加、镜像缺失、异步 clip 未就绪、缓存跨角色复用。本仓库固定特征与混合契约。

- 领域：游戏、图形与多媒体
- 子方向：图形渲染
- 语言/框架：Python 3, pytest
- 初始状态：15 个参数化用例全部失败

## 目录结构

```
README.md
conftest.py
.gitignore
gameplay/__init__.py
gameplay/motion_matching.py
tests/test_motion_matching.py
```

## 需要修复的 10 个问题

1. 特征窗口与查询姿态使用同一帧时间步，不再跨帧拼装
2. 数据库距离按权重和归一，速度权重不压过朝向
3. 根运动只应用一次，动画蓝图不重复叠加导致滑步
4. 镜像动画进入同一索引，左右转都能匹配
5. 转向阈值随速度自适应，低速不频繁切换
6. 候选混合权重归一，姿势不被拉长
7. 异步 clip 未完成时使用占位，不参与匹配出现 T-pose
8. 查询缓存按角色隔离，A 的候选不被 B 复用
9. 可变帧率下按固定频率采样特征点
10. 网络纠正后姿态平滑，匹配不直接跳帧

## 15 条验收契约

    01. same frame feature time — `feature_time`
    02. weight normalized distance — `normalized_distance`
    03. root motion once — `apply_root_motion`
    04. mirror index — `mirror_index`
    05. adaptive turn threshold — `turn_threshold`
    06. blend weights normalized — `normalize_blend`
    07. async clip not ready — `clip_ready`
    08. cache per character — `cache_key`
    09. fixed rate sampling — `sample_times`
    10. correction smoothing — `smooth_pose`
    11. feature window tail — `feature_window`
    12. rank candidates — `rank_candidates`
    13. mirror pose axis — `mirror_pose`
    14. cache scope — `cache_scope`
    15. align animation time — `align_time`

## 当前状态

`gameplay/motion_matching.py` 只保留函数签名与文档字符串，所有函数体统一
`raise NotImplementedError`。`tests/test_motion_matching.py` 使用一个
`@pytest.mark.parametrize` 装载 15 条契约，初始全部失败且没有 collection error。

```bash
python -m pytest -q
```

预期输出包含 `15 failed`。实现 `gameplay/motion_matching.py` 后，15 条契约应全部通过。
