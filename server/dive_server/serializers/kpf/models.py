"""
These models only provide the necessary properties for ingesting, exporting,
and validation of diva annotations for a SINGLE clip.  They are not intended
to map directly to stumpf models.

They are only useful internally to this library, and are intended as a
translation layer for data either before or after it exists within the stumpf
system.
"""
import logging
from typing import Any, Dict, Iterable, Iterator, List, NamedTuple, Optional, Tuple

import attr

from . import BoilerError

logger = logging.getLogger(__name__)


def sort_detections(detections: List['Detection']) -> List['Detection']:
    return sorted(detections, key=lambda d: d.frame)


def get_next_keyframe(arr: List['Detection']) -> 'Detection':
    for d in arr:
        if d.keyframe:
            return d
    raise BoilerError('There are frames after the final keyframe!')


def interpolate_point(a, b, delta):
    return round(((1 - delta) * a) + (delta * b))


class Box(NamedTuple):
    left: int
    top: int
    right: int
    bottom: int

    def __and__(self, other: 'Box') -> 'Box':
        """Return intersection of two bounding boxes.

        For non-intersecting boxes, this will return a box of zero area.
        """
        left = max(self.left, other.left)
        right = min(self.right, other.right)
        top = max(self.top, other.top)
        bottom = min(self.bottom, other.bottom)
        return Box(left=left, right=max(left, right), top=top, bottom=max(top, bottom))

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def aspect_ratio(self) -> float:
        height = self.height
        if height == 0:
            return 0
        return self.width / self.height

    @property
    def center(self) -> Tuple[float, float]:
        return (self.left + self.right) / 2, (self.top + self.bottom) / 2

    def interpolate(self, other: 'Box', distance: float) -> 'Box':
        left = interpolate_point(self.left, other.left, distance)
        top = interpolate_point(self.top, other.top, distance)
        right = interpolate_point(self.right, other.right, distance)
        bottom = interpolate_point(self.bottom, other.bottom, distance)
        return Box(left=left, top=top, right=right, bottom=bottom)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Box':
        return cls(left=d['left'], right=d['right'], top=d['top'], bottom=d['bottom'])

    def fix_order(self) -> 'Box':
        left = self.left
        right = self.right
        top = self.top
        bottom = self.bottom

        if left > right:
            left, right = right, left
        elif left == right:
            logger.warning('Zero width bounding box encountered')
            right = left + 1

        if top > bottom:
            top, bottom = bottom, top
        elif bottom == top:
            logger.warning('Zero height bounding box encountered')
            bottom = top + 1

        return Box(left=left, right=right, top=top, bottom=bottom)


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class Detection:
    frame: int
    box: Box
    keyframe: bool = False

    @property
    def area(self) -> int:
        return self.box.area

    def interpolate(self, other: 'Detection', frame: int) -> 'Detection':
        distance = (frame - self.frame) / (other.frame - self.frame)
        box = self.box.interpolate(other.box, distance)
        return Detection(frame=frame, box=box, keyframe=False)

    def fix_order(self) -> 'Detection':
        return attr.evolve(self, box=self.box.fix_order())


@attr.s(auto_attribs=True, kw_only=True, frozen=True, hash=False)
class Actor:
    actor_type: str
    begin: int
    end: int
    detections: List[Detection] = attr.ib(converter=sort_detections)
    actor_id: int

    @property
    def keyframes(self):
        return filter(lambda d: d.keyframe, self.detections)

    def pruned(self) -> 'Actor':
        return attr.evolve(self, detections=list(self.keyframes))

    # Used for deduplicating lists of actors when serializing
    def __hash__(self) -> int:
        first_detection = None
        if self.detections:
            first_detection = self.detections[0]
        return hash((self.actor_type.value, self.begin, self.end, first_detection))

    def inject_keyframe(self, frame: int) -> 'Actor':
        """Return the actor with a new keyframe linearly interpolated.

        If the frame is already a keyframe or if the frame is outside of the
        valid range [begin, end], then no change will be made.
        """
        new_detections: List[Detection] = []
        for index in range(len(self.detections) - 1):
            d1 = self.detections[index]
            d2 = self.detections[index + 1]
            new_detections.append(d1)

            if d1.frame == frame:
                return self
            elif d1.frame < frame < d2.frame:
                interpolated = attr.evolve(d1.interpolate(d2, frame), keyframe=True)
                new_detections.append(interpolated)

        new_detections.append(self.detections[-1])
        return attr.evolve(self, detections=new_detections)

    def truncate_framerange(self) -> 'Actor':
        """Return the actor with frame range truncated to the detection range."""
        begin = max(self.begin, self.detections[0].frame)
        end = min(self.end, self.detections[-1].frame)
        return attr.evolve(self, begin=begin, end=end)

    def truncate_detections(self) -> 'Actor':
        return attr.evolve(
            self,
            detections=[
                d for d in self.detections if self.begin <= d.frame <= self.end
            ],
        )

    @property
    def interpolated_detections(self) -> Iterator[Detection]:
        if not self.detections:
            return
        last_detection = self.detections[0]
        yield last_detection
        for detection in self.detections[1:]:
            for frame in range(last_detection.frame + 1, detection.frame):
                yield last_detection.interpolate(detection, frame)
            yield detection
            last_detection = detection


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class Activity:
    activity_type: str
    begin: int
    end: int
    actors: List[Actor]
    activity_id: int
    status: Optional[str] = None

    def pruned(self) -> 'Activity':
        actors = [a.pruned() for a in self.actors]
        return attr.evolve(self, actors=actors)

    def truncate(self) -> 'Activity':
        """Remove extra detections and truncate frame range."""
        if not self.actors:
            logger.warning('Activity does not contain any tracks')
            return self

        new_actors = [
            a.inject_keyframe(a.begin)
            .inject_keyframe(a.end)
            .truncate_framerange()
            .truncate_detections()
            for a in self.actors
        ]
        begin = self.actors[0].begin
        end = self.actors[0].end
        for actor in self.actors[1:]:
            begin = min(begin, actor.begin)
            end = max(end, actor.end)

        return attr.evolve(self, begin=begin, end=end, actors=new_actors)


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class ActivityList:
    activity_map: Dict[int, Activity] = attr.ib()
    actor_map: Dict[int, Actor] = attr.ib()

    @property
    def activity_types(self) -> Dict[str, Iterable[Activity]]:
        # TODO: make this more efficient
        activity_types = {a.activity_type for a in self.activity_map.values()}
        return {
            at: list(
                filter(lambda a: a.activity_type == at, self.activity_map.values())
            )
            for at in activity_types
        }

    def __iter__(self) -> Iterator[Activity]:
        for activity in self.activity_map.values():
            yield activity

    def __len__(self) -> int:
        return len(self.activity_map)
