import time
import os
from client.stalker import meeshkan_listener

meeshkan_listener()
a = 1
while True:
    print("{} ---- {}".format(os.getpid(), a))
    time.sleep(5)
    a += 1
