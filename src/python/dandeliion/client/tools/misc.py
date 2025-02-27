from collections.abc import Mapping, MutableMapping
import copy


# updates dict with varying depth
def update_dict(target: MutableMapping, updates: Mapping, inline: bool = True, force_none=False) -> MutableMapping:
    if not inline:
        target = copy.deepcopy(target)
    for key, value in updates.items():
        if (
                value and  # empty mapping or None
                isinstance(value, Mapping) and
                isinstance(target.get(key, None), Mapping)
        ):
            # recursive case
            update_dict(target[key], value, inline=True, force_none=force_none)
        elif value or not target.get(key, None) or force_none:
            # set value if either not none or key does not exist yet or forcing overwrites by none
            target[key] = value
    if not inline:
        return target
