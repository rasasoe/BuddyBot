# BuddyBot system sounds

Optional prerecorded `.wav` or `.mp3` files in this directory take priority over
local TTS for short Pi-side system responses.

Supported names:

```text
yes
ready
forward
backward
strafe_left
strafe_right
rotate_left
rotate_right
stop
follow_start
follow_stop
server_offline
```

For example, `stop.wav` is played immediately after the local stop command has
already published zero velocity. If a matching file is missing, BuddyBot falls
back to Piper when configured and then to the installed local TTS backend.
