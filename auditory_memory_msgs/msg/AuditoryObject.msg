std_msgs/Header header

string auditory_object_id
string location_id

string state # NEW, ACTIVE, BACKGROUND, INACTIVATE

float32 confidence
float32 novelty
float32 relevance

float32 current_event_duration
builtin_interfaces/Time last_heard