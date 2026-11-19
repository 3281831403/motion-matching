import pytest

from gameplay import motion_matching as mod

CASES = [
    pytest.param('feature_time', (0.0, 0.016, 30.0), 0.0, True, id='01_same_frame_feature_time'),
    pytest.param('normalized_distance', ([(0.0, 0.0), (10.0, 0.0)], (0.0, 0.0), (1.0, 1.0)), 7.0710678118654755, True, id='02_weight_normalized_distance'),
    pytest.param('apply_root_motion', ((1.0, 2.0), (0.5, 0.0), False), (1.5, 2.0), True, id='03_root_motion_once'),
    pytest.param('mirror_index', (1, 4), 2, False, id='04_mirror_index'),
    pytest.param('turn_threshold', (8.0,), 10.0, True, id='05_adaptive_turn_threshold'),
    pytest.param('normalize_blend', ([1.0, 3.0],), (0.25, 0.75), True, id='06_blend_weights_normalized'),
    pytest.param('clip_ready', ('loading', 0.0, 1.0), False, False, id='07_async_clip_not_ready'),
    pytest.param('cache_key', ('A', 'run'), 'A:run', False, id='08_cache_per_character'),
    pytest.param('sample_times', (0.0, 0.1, 10.0), (0.0, 0.1), True, id='09_fixed_rate_sampling'),
    pytest.param('smooth_pose', (0.0, 1.0, 0.25), 0.25, True, id='10_correction_smoothing'),
    pytest.param('feature_window', ([1, 2, 3], 2), (2, 3), False, id='11_feature_window_tail'),
    pytest.param('rank_candidates', ([('a', 0.5), ('b', 0.1)], 1), ['b'], False, id='12_rank_candidates'),
    pytest.param('mirror_pose', ((1.0, 2.0, 3.0), 0), (-1.0, 2.0, 3.0), True, id='13_mirror_pose_axis'),
    pytest.param('cache_scope', ('A', 45), 'A:1', False, id='14_cache_scope'),
    pytest.param('align_time', (0.07, 30.0), 0.06666666666666667, True, id='15_align_animation_time'),
]


def assert_close(actual, expected):
    if isinstance(expected, tuple):
        assert isinstance(actual, tuple) and len(actual) == len(expected)
        for a, e in zip(actual, expected):
            assert_close(a, e)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected)
        for a, e in zip(actual, expected):
            assert_close(a, e)
    elif isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            assert_close(actual[key], expected[key])
    else:
        assert actual == pytest.approx(expected)


@pytest.mark.parametrize("func_name,args,expected,approx", CASES)
def test_motion_matching_contract(func_name, args, expected, approx):
    func = getattr(mod, func_name)
    result = func(*args)
    if approx:
        assert_close(result, expected)
    else:
        assert result == expected
