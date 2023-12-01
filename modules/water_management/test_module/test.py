from inherit import Module
from struct import *
import time


# https://docs.python.org/3/library/struct.html#struct-format-strings
class test(Module):
    def __init__(self, **kwargs) -> None:
        pass

    async def run(self):
        # t = create_topic("ph/probe", config={"component": "sensor"})

        # def on_message(client, userdata, message):
        #     print(unpack('>f', message.payload)[0])
        #     # print(unpack(">h", message.payload))

        # t.on_message = on_message
        # print(pack('>f', 6.5))
        # t.publish(pack('>f', 6.5))
        # time.sleep(5)
        # t.publish(6.54)
        return 300