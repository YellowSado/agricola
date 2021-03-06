import numpy as np
import numbers
import itertools
from collections import OrderedDict, Counter, defaultdict
from future.utils import iteritems, with_metaclass
import abc


class EventGenerator(with_metaclass(abc.ABCMeta, object)):
    def __init__(self):
        self.listeners = defaultdict(list)  # event_name -> listeners

    @abc.abstractmethod
    def _validate_event_name(self, event_name):
        """ Return false if the event name is not valid. """
        raise NotImplementedError()

    def listen_for_event(self, listener, event_name, before=False):
        valid = self._validate_event_name(event_name)
        if not valid:
            raise Exception(
                "{} is not a valid event name for class {}.".format(
                    event_name, self.__class__.__name__))
        if before:
            event_name += '-before'

        self.listeners[event_name].append(listener)

    def stop_listening(self, listener, event_name, before=False):
        if before:
            event_name += '-before'
        try:
            self.listeners[event_name].remove(listener)
        except (ValueError, KeyError):
            pass

    def trigger_event(self, event_name, *args, before=False, **kwargs):
        valid = self._validate_event_name(event_name)
        if not valid:
            raise Exception(
                "{} is not a valid event name for class {}.".format(
                    event_name, self.__class__.__name__))

        if before:
            event_name += '-before'

        listeners = self.listeners.get(event_name, [])
        for l in listeners:
            l.trigger(*args, **kwargs)


class EventScope(object):
    def __init__(self, event_generators, event_name, **kwargs):
        if isinstance(event_generators, EventGenerator):
            event_generators = [event_generators]
        self.event_generators = event_generators

        self.event_name = event_name
        self.kwargs = kwargs

    def __enter__(self):
        for eg in self.event_generators:
            eg.trigger_event(self.event_name, before=True, **self.kwargs)

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            for eg in self.event_generators:
                eg.trigger_event(self.event_name, before=False, **self.kwargs)


def score_mapping(value, thresholds, points=None):
    points = points or [-1] + range(len(thresholds)-1)
    thresholds = sorted(thresholds)
    if value < thresholds[0]:
        return points[0]

    for i in range(len(thresholds)-1):
        if value >= thresholds[i] and value < thresholds[i+1]:
            return points[i+1]

    return points[-1]


def check_random_state(seed):
    """ Taken from sklearn.

    Turn seed into a np.random.RandomState instance
    If seed is None, return the RandomState singleton used by np.random.
    If seed is an int, return a new RandomState instance seeded with seed.
    If seed is already a RandomState instance, return it.
    Otherwise raise ValueError.

    """
    if seed is None or seed is np.random:
        return np.random.mtrand._rand
    if isinstance(seed, (numbers.Integral, np.integer)):
        return np.random.RandomState(seed)
    if isinstance(seed, np.random.RandomState):
        return seed
    raise ValueError('%r cannot be used to seed a numpy.random.RandomState'
                     ' instance' % seed)


def orthog_adjacent(a, b):
    a, b = np.array(a), np.array(b)
    abs_diff = np.abs(a - b)
    return (np.count_nonzero(abs_diff) == 1) and (abs_diff.sum() == 1)


def index_check(idx, shape):
    """ Check that index `idx` is valid for an array with shape `shape`. """
    idx = np.array(idx)
    if any(idx < 0) or any(idx >= shape):
        raise IndexError("idx: {0}, shape: {1}".format(idx, shape))


def _fence_loc_to_grid_loc(fence_loc, cell_shape):
    return np.array(fence_loc) * (cell_shape + 1)


def draw_grid(cells, cell_shape, fences=None, enum=True, asarray=False):
    """
    Parameters
    ----------
    cells: numpy array
        Each element gives the character to draw at a location
        in the larger grid.
    cell_shape: tuple-like, length=2
        Shape of a cell in *matrix* format (y-idx first).
    fences: list of fences
        Fences to draw (also in matrix format).
    enum: bool
        Whether to put co-ordinates in margins.

    """
    fences = fences or []
    cells = np.array(cells)
    shape = np.array(cells.shape)
    cell_shape = np.array(cell_shape)
    grid_shape = (cell_shape + 1) * shape + 1
    grid = np.tile(np.array(' '), grid_shape)

    h_corners, v_corners = [], []

    for fence in fences:
        diff = np.array(fence[1]) - np.array(fence[0])
        horizontal = diff[1] == 1
        char = '-' if horizontal else '|'
        start = _fence_loc_to_grid_loc(fence[0], cell_shape)
        (h_corners if horizontal else v_corners).append(tuple(start))

        start += diff
        end = start + diff * cell_shape
        (h_corners if horizontal else v_corners).append(tuple(end))

        if horizontal:
            grid[start[0], start[1]:end[1]] = char
        else:
            grid[start[0]:end[0], start[1]] = char

    h_corner_count = Counter(h_corners)
    for corner, count in iteritems(h_corner_count):
        if count > 1:
            grid[corner] = '-'

    v_corner_count = Counter(v_corners)
    for corner, count in iteritems(v_corner_count):
        if count > 1:
            grid[corner] = '|'

    cross_corners = set(h_corners) & set(v_corners)
    for corner in cross_corners:
        grid[corner] = '+'

    for i in range(shape[0]):
        for j in range(shape[1]):
            upper_left = 1 + np.array((i, j)) * (1 + cell_shape)
            bottom_right = upper_left + cell_shape
            grid[upper_left[0]:bottom_right[0],
                 upper_left[1]:bottom_right[1]] = cells[i, j]

    if enum:
        top = np.tile(np.array(' '), (1, grid.shape[1]))
        unit_width = cell_shape[1] + 1
        for i in range(cells.shape[1]):
            s = str(i)
            start = i * unit_width + int(unit_width/2.0)
            top[0, start] = s

        left = np.tile(np.array(' '), (grid.shape[0] + 1, 1))
        unit_height = cell_shape[0] + 1
        for i in range(cells.shape[0]):
            s = str(i)
            start = 1 + i * unit_height + int(unit_height/2.0)
            left[start, 0] = s

        grid = np.vstack((top, grid))
        grid = np.hstack((left, grid))

    if asarray:
        return grid
    else:
        return '\n'.join(''.join(c for c in row) for row in grid)


def multiset_subtract(a, b):
    a_copy = a.copy()
    for k, v in iteritems(b):
        if k in a_copy:
            a_copy[k] -= v
            a_copy[k] = max(0, a_copy[k])
    return a_copy


def multiset_weight(a):
    return sum([k * v for k, v in iteritems(a)])


def multiset_satisfy(constraints, multiset):
    """
    Check whether there exists <a partition of the given multiset
    whose size is equal to the length of ``constraints``> such that
    the total weight of each component of the partition is at least big
    as its corresponding entry in ``constraints``.

    Parameters
    ----------
    constraints: list of int
        The constraints.
    multiset: dict (keytype -> int)
        The multiset.

    """
    if not constraints:
        return True

    if len(constraints) == 1:
        return multiset_weight(multiset) >= constraints[0]

    # Easy check.
    if multiset_weight(multiset) < sum(constraints):
        return False

    multiset = OrderedDict(multiset)
    for counts in itertools.product(*[range(v+1) for k, v in iteritems(multiset)]):
        submultiset = {k: count for k, count in zip(multiset, counts)}
        weight = multiset_weight(submultiset)
        if weight < constraints[0]:
            continue

        remaining = multiset_subtract(multiset, submultiset)

        success = multiset_satisfy(constraints[1:], remaining)
        if success:
            return True

    return False


def cumsum(lst):
    acc, cs = 0, []
    for l in lst:
        acc += l
        cs.append(acc)
    return cs
