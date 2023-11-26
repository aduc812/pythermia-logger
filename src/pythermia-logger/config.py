import logging


host = 1
port = "/dev/serial0"
kind = "inverter"
prot = "RTU"

# RTU arguments; leave default for TCP connection
baud = 115200
btsz = 8
prty = "E"
stbt = 1
echo = False


logging_level = logging.INFO

THERMIA_TABLE_NAME = "parameters"
