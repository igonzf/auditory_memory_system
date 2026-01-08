std_msgs/Header header

string auditory_object_id
string location_id

# Sound status constants
uint8 STATE_NEW = 0
uint8 STATE_ACTIVE = 1
uint8 STATE_BACKGROUND = 2
uint8 STATE_INACTIVE = 3

uint8 state

float32 confidence
float32 novelty
float32 relevance

float32 current_event_duration
builtin_interfaces/Time last_heard