from collections.abc import Mapping, MutableMapping
import copy


# updates dict with varying depth
def update_dict(target: MutableMapping, updates: Mapping, inline: bool = True) -> MutableMapping:
    if not inline:
        target = copy.deepcopy(target)
    if updates is None:
        return target
    for key, value in updates.items():
        if value and isinstance(value, Mapping) and isinstance(target.get(key, None), Mapping):
            update_dict(target[key], value)
        else:
            target[key] = value
    if not inline:
        return target


# access dict with varying depth
def get_dict(dct: Mapping, *keys: list, default=None):
    for key in keys:
        try:
            dct = dct[key]
        except KeyError:
            return default
    return dct


def flatten_dict(dct: MutableMapping, parent_key: str = '', sep: str = '.') -> MutableMapping:
    items = []
    for k, v in dct.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def unflatten_dict(dct: MutableMapping, sep: str = '.') -> MutableMapping:
    resultDict = dict()
    for key, value in dct.items():
        parts = key.split(sep)
        d = resultDict
        for part in parts[:-1]:
            if part not in d:
                d[part] = dict()
            d = d[part]
        d[parts[-1]] = value
    return resultDict
