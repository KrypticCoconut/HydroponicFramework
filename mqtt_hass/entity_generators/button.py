from asyncore import loop
from mqtt_hass.TopicsClient import TopicsClient
from mqtt_hass.HassEntitiesManager import HassEntitiesManager
import threading

topicsClient: TopicsClient = None
hassEntityManager: HassEntitiesManager = None

class ButtonInterface():
    def __init__(self, name, payload_press, request_topic, retain) -> None:
        self.name = name
        self.payload_press = payload_press
        self.request_topic = request_topic
        self.discovery_topic = None
        self.retain = retain

        self.callback_lock = threading.Lock()
        self._callback = None     
        self.running = False
        self.base_callback_counter = 0
        self.callback_finished_counter = 0

    @property
    def callback(self):
        return self._callback
    
    @callback.setter
    def callback(self, func):
        with self.callback_lock:
            self._callback = func

    def callback_helper(self, client, userdata, loop):
        with self.callback_lock:
            self.base_callback_counter += 1

            callback = self._callback
            if(callback):
                curr_base_counter = self.base_callback_counter
                curr_finished = self.callback_finished_counter
                async def wrap(*args, **kwargs):
                    if(self.running):
                        #log
                        return
                    if(curr_base_counter != curr_base_counter): # it is not the most recent callback
                        #log
                        return
                    
                    if(curr_finished != self.callback_finished_counter): # functions were executed between the 2 calls
                        #log
                        return

                    self.running = True
                    await self.callback(*args, **kwargs) # during this code, other callbacks may be called
                    # everything after this is synchronous, so the event loop cant call wrap again whilst chaning running state
                    self.callback_finished_counter += 1
                    self.running = False
                loop.create_task(wrap(client, userdata))


    def register_to_hass(self, friendy_name):
        config = {
            "command_topic": self.request_topic.name_mqtt,
            "payload_press": self.payload_press,
        }
        self.hassentity = hassEntityManager.create_entity(entity_name = self.name, friendly_name=friendy_name, component_type="button", config = config)        

class ButtonTopic():
    def __init__(self, topicname) -> None:
        self.topicname = topicname

        self.switch_funcs = {}
        # Note: request and recieve are defined from the point of an outside entity, trying to control a given state
        self.request_topic = topicsClient.create_topic(self.topicname + "/recieve", create_topic_changelogger=False, subscribe=True) # topic where an outside device gets info about its request
        self.request_topic.on_message = self.on_message

    def on_message(self, client, userdata, msg, loop):
       payload = msg.payload.decode()
       if(payload in self.switch_funcs):
           self.switch_funcs[payload](client, userdata, loop)


    def create_button(self, sensor_name, payload=None, retain=False):
        if(sensor_name):
            name = "{}_{}".format(self.topicname.replace("/", "_"), sensor_name)
        else:
            name = self.topicname.replace("/", "_")
        if(payload != None):
            payload = name
        payload_press = f"{payload} press"

        interface = ButtonInterface(name, payload_press, self.request_topic, retain)




        self.switch_funcs[payload_press] = interface.callback_helper
        return interface

        



EntityGenerator = ButtonTopic