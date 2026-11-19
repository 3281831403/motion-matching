"""动作匹配：同帧特征与候选归一。

本模块实现动作匹配中与时间步、权重归一、根运动、镜像索引、异步占位、
缓存隔离、定频采样和姿态平滑相关的纯函数契约。

关键约定：
- 时间相关函数统一使用二分取整，避免浮点误差跨帧；
- 距离与混合权重都按权重和/总和归一；
- 缓存键必须包含角色标识，避免多角色共享查询结果。
"""

from __future__ import annotations

import math

# 对齐时间/采样点时容忍的浮点误差，避免 0.07 * 30 这类乘积落在网格边缘。
_EPS = 1e-9


def _quantize(value, rate):
    """把 value * rate 量化到最近的整数格，返回格子下标。"""
    return int(math.floor(value * rate + 0.5 + _EPS))


def feature_time(prev_time, dt, rate):
    """把查询时间量化到固定特征帧。

    特征窗口跨帧拼装时，查询姿态必须落在与特征相同的固定时间步上，
    因此不使用 ``prev_time``，而是把 ``prev_time + dt`` 对齐到 1/rate 网格。
    """
    if rate <= 0:
        raise ValueError("rate must be positive")
    return _quantize(prev_time + dt, rate) / rate


def normalized_distance(features, query, weights):
    """按权重和归一的加权 RMS 距离。

    用 ``sum(weights)``（而不是特征个数）归一，保证速度权重不会因为
    维度多或数值大而压过朝向权重。
    """
    if not features:
        return 0.0
    if len(query) != len(weights):
        raise ValueError("query and weights must have the same length")

    total = 0.0
    for feature in features:
        if len(feature) != len(query):
            raise ValueError("feature and query dimensions must match")
        for value, target, weight in zip(feature, query, weights):
            diff = value - target
            total += weight * diff * diff

    weight_sum = float(sum(weights))
    if weight_sum <= 0:
        return 0.0
    return math.sqrt(total / weight_sum)


def apply_root_motion(pose, delta, already_applied):
    """根运动只应用一次。

    根运动若已由动画蓝图叠加，则直接返回原姿势，避免二次位移造成滑步。
    """
    if already_applied:
        return tuple(pose)
    if len(pose) != len(delta):
        raise ValueError("pose and delta dimensions must match")
    return tuple(p + d for p, d in zip(pose, delta))


def mirror_index(index, count):
    """左右镜像动画的对称索引。

    镜像动画与原始动画进入同一索引后，索引成对出现：
    第 i 个动画的镜像在第 ``count - 1 - i`` 个位置。
    """
    if count <= 0:
        raise ValueError("count must be positive")
    if not 0 <= index < count:
        raise IndexError("index out of range")
    return count - 1 - index


# 参考点：8 单位/秒时阈值为 10 度；低于该速度阈值抬高，高于则降低。
TURN_REFERENCE_SPEED = 8.0
TURN_REFERENCE_THRESHOLD = 10.0
# 上下限避免静止时阈值发散、以及高速时阈值过小导致抖转。
TURN_MIN_THRESHOLD = 2.0
TURN_MAX_THRESHOLD = 60.0


def turn_threshold(speed):
    """随速度自适应的转向阈值。

    阈值与速度成反比：低速时放宽，避免噪声导致频繁切换；
    速度越高阈值越低，转向响应更灵敏。结果钳制在 ``[2, 60]`` 度内。
    """
    speed = abs(speed)
    if speed == 0:
        return TURN_MAX_THRESHOLD
    threshold = TURN_REFERENCE_THRESHOLD * TURN_REFERENCE_SPEED / speed
    return min(TURN_MAX_THRESHOLD, max(TURN_MIN_THRESHOLD, threshold))


def normalize_blend(weights):
    """候选混合权重归一。

    候选按代价选出的原始权重可能不为一，直接混合会把姿势拉长/压扁，
    因此返回按总和归一的权重元组。总和为 0 时均匀分配。
    """
    total = float(sum(weights))
    if total <= 0:
        if not weights:
            return ()
        share = 1.0 / len(weights)
        return tuple(share for _ in weights)
    return tuple(weight / total for weight in weights)


def clip_ready(status, loaded_time, required_time):
    """异步 clip 是否可参与匹配。

    只有加载完成且已加载时长覆盖所需时长时，clip 才能参与匹配；
    未完成时使用占位姿势，避免出现 T-pose。
    """
    return status == "ready" and loaded_time >= required_time - _EPS


def cache_key(character_id, clip_id):
    """按角色隔离的查询缓存键。"""
    return f"{character_id}:{clip_id}"


def sample_times(start, end, rate):
    """固定频率采样时间点。

    在可变帧率下仍按固定频率取特征点，采样点不随渲染帧漂移。
    ``end`` 落在采样格上时包含该端点，``start`` 落在格上时包含该起点；
    起点不在格上时，首个采样点取起点之后的第一个格子，绝不早于 ``start``。
    返回 ``(t0, ...)`` 元组。
    """
    if rate <= 0:
        raise ValueError("rate must be positive")
    # 向上取格保证不采样到 start 之前；减 _EPS 吸收 start 本就在格上时的浮点误差。
    first = int(math.ceil(start * rate - _EPS))
    last = int(math.floor(end * rate + _EPS))
    if last < first:
        return ()
    return tuple(k / rate for k in range(first, last + 1))


def smooth_pose(current, target, alpha):
    """网络纠正后的姿态平滑。

    以 ``alpha`` 在当前位置与纠正目标之间插值，匹配结果不会直接跳帧。
    ``alpha`` 越大越接近目标；1 表示立即到达。
    """
    return current + (target - current) * alpha


def feature_window(frames, size):
    """取当前帧结尾的固定窗口。

    窗口必须与查询姿态取自同一帧，且以当前帧为结尾，
    不足 ``size`` 时返回已有全部帧。
    """
    if size <= 0:
        return ()
    frames = tuple(frames)
    if not frames:
        return ()
    return frames[-size:]


def rank_candidates(candidates, max_results):
    """按代价排序并截断候选。

    返回代价升序（同代价保持输入顺序）的候选标识列表。
    """
    if max_results <= 0:
        return []
    ordered = sorted(candidates, key=lambda candidate: candidate[1])
    return [candidate[0] for candidate in ordered[:max_results]]


def mirror_pose(pose, axis):
    """沿指定轴镜像姿势分量。

    只翻转 ``axis`` 对应的分量：镜像 X 轴时 x 取反，其余分量保持不变。
    """
    if not 0 <= axis < len(pose):
        raise IndexError("axis out of range")
    mirrored = list(pose)
    mirrored[axis] = -mirrored[axis]
    return tuple(mirrored)


def cache_scope(character_id, frame):
    """角色缓存的帧作用域键。

    帧作用域同样按角色隔离，不同角色即使在同一帧也不会复用候选。
    """
    if frame < 0:
        raise ValueError("frame must be non-negative")
    return f"{character_id}:{frame // 30}"


def align_time(anim_time, rate):
    """把动画时间对齐到固定采样格。

    使用二分取整而非截断，0.07s @30Hz 对齐到 0.0667s（第 2 格）。
    """
    if rate <= 0:
        raise ValueError("rate must be positive")
    return _quantize(anim_time, rate) / rate
