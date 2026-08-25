import time

from auditory_memory_core.memory import LongTermMemory


def _local_time(hour, minute=0):
    now = time.time()
    local = time.localtime(now)
    return time.mktime((
        local.tm_year,
        local.tm_mon,
        local.tm_mday,
        hour,
        minute,
        0,
        local.tm_wday,
        local.tm_yday,
        local.tm_isdst,
    ))


def test_unknown_location_skips_location_patterns_but_learns_sound_time_and_cooccurrence():
    ltm = LongTermMemory('')
    timestamp_s = _local_time(7)

    before = ltm.evaluate('alarm', 'unknown_location', timestamp_s)
    ltm.consolidate_episode(
        sound_type='alarm',
        location_id='unknown_location',
        started_at_s=timestamp_s,
        last_heard_s=timestamp_s + 1.0,
        co_occurring_sounds=['voices'],
        novelty=before.novelty,
    )
    after = ltm.evaluate('alarm', 'unknown_location', timestamp_s)
    summary = ltm.pattern_summary(limit=5)

    assert after.novelty < before.novelty
    assert after.location_available is False
    assert after.location_congruence == 0.5
    assert summary['sound_location_patterns'] == []
    assert summary['location_sound_patterns'] == []
    assert summary['time_patterns'][0]['sound'] == 'alarm'
    assert summary['co_occurrence_patterns'][0]['sound_a'] == 'alarm'
    assert summary['co_occurrence_patterns'][0]['sound_b'] == 'voices'
