from dataclasses import dataclass, field
from collections import deque
from typing import Deque, Dict, Tuple, List
from builtin_interfaces.msg import Time
from auditory_memory_msgs.msg import AuditoryObject

@dataclass
class MemoryEntry:
    # Key
    # auditory_object_id: str
    # location_id: str

    # Auditory object
    auditory_object: AuditoryObject

    # Actual episode
    episode_start_time: float

    # History
    episode_count: int = 0
    ema_episode_duration: float = 0.0
    last_episode_duration: float = 0.0
    hour_hist: List[int] = field(default_factory=lambda: [0]*24)

    # Recent frequency
    recent_hits: Deque[float] = field(default_factory=deque)
