"""Sensor-independent candidate: caller supplies lane + normalized finger position.

No spatial layout, ID tracking, Part mapping or pressure is assumed here.
Two fingers in one lane select their midpoint (rounded down). Three or more
hold that lane and report ambiguity; this is a candidate policy to review.
"""
def targets(points, lanes=8, maximum=4095):
    buckets = [[] for _ in range(lanes)]
    ids = set()
    for finger_id, lane, position in points:
        if finger_id in ids:
            raise ValueError("Duplicate finger ID in a report")
        if not isinstance(lane, int) or not 0 <= lane < lanes:
            raise ValueError("Invalid lane")
        if not isinstance(position, int) or not 0 <= position <= maximum:
            raise ValueError("Invalid normalized position")
        ids.add(finger_id)
        buckets[lane].append(position)
    values = [None] * lanes
    ambiguous = []
    for lane, positions in enumerate(buckets):
        if len(positions) == 1:
            values[lane] = positions[0]
        elif len(positions) == 2:
            values[lane] = sum(positions) // 2
        elif len(positions) > 2:
            ambiguous.append(lane)
    return values, ambiguous


def advance(current, target_values, step, maximum=4095):
    if len(current) != len(target_values) or not 0 <= step <= maximum:
        raise ValueError("Invalid follow state/step")
    result = list(current)
    for i, goal in enumerate(target_values):
        if not 0 <= current[i] <= maximum or (goal is not None and not 0 <= goal <= maximum):
            raise ValueError("Position outside normalized range")
        if goal is not None:
            distance = goal - current[i]
            result[i] += max(-step, min(step, distance))
    return result
