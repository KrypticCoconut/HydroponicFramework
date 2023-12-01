from mqtt_hass.TopicsClient import TopicsClient
from mqtt_hass.HassEntitiesManager import HassEntitiesManager
import threading

topicsClient: TopicsClient = None
hassEntityManager: HassEntitiesManager = None

class SwitchInterface():
    def __init__(self, name, on, off, request_topic, recieve_topic, retain) -> None:
        self.name = name
        self.payload_on = on
        self.payload_off = off
        self.request_topic = request_topic
        self.recieve_topic = recieve_topic
        self.retain = retain
        self.hassentity = None

        self.callback_lock = threading.Lock()
        self._callback = None     
        self.running = False
        self.base_callback_counter = 0
        self.callback_finished_counter = 0
        self.state = None
        self.tmpstate = None

    @property
    def callback(self):
        return self._callback
    
    @callback.setter
    def callback(self, func):
        with self.callback_lock:
            self._callback = func

    def callback_helper(self, client, userdata, message, loop):
        
        req_state = str(message.payload.decode("utf-8")) == self.payload_on

        with self.callback_lock:
            self.base_callback_counter += 1

            callback = self._callback
            if(callback):
                curr_base_counter = self.base_callback_counter
                curr_finished = self.callback_finished_counter
                async def wrap(client, userdata, req_state):
                    self.tmpstate = req_state
                    if(self.running):
                        #log
                        self.switch(self.tmpstate)
                        return
                    if(curr_base_counter != curr_base_counter): # it is not the most recent callback
                        #log
                        self.switch(self.state)
                        return
                    
                    if(curr_finished != self.callback_finished_counter): # functions were executed between the 2 calls
                        #log
                        self.switch(self.state)
                        return

                    self.running = True
                    new_state = await self.callback(client, userdata, req_state) # during this code, other callbacks may be called
 
                    # everything after this is synchronous, so the event loop cant call wrap again whilst chaning running state
                    self.switch(new_state)
                    self.callback_finished_counter += 1
                    self.running = False
                loop.create_task(wrap(client, userdata, req_state))

    def switch(self, state: bool):
        if(state):
            self.recieve_topic.publish(self.payload_on, retain=self.retain)
            self.state = True
        else:
            self.recieve_topic.publish(self.payload_off, retain=self.retain)
            self.state = False

    def register_to_hass(self, friendly_name):
        config = {
            "state_topic": self.recieve_topic.name_mqtt,
            "command_topic": self.request_topic.name_mqtt,            
            "payload_on": self.payload_on,
            "payload_off": self.payload_off,
            "state_on": self.payload_on,
            "state_off": self.payload_off,
        }
        self.hassentity = hassEntityManager.create_entity(entity_name = self.name, friendly_name=friendly_name, component_type="switch", config = config)

class SwitchTopic():
    def __init__(self, topicname) -> None:
        self.topicname = topicname

        # Note: request and recieve are defined from the point of an outside entity, trying to control a given state
        self.recieve_topic = topicsClient.create_topic(self.topicname + "/recieve", create_topic_changelogger=False, subscribe=False) # topic where an outside device gets info about its request
        self.request_topic = topicsClient.create_topic(self.topicname + "/request", create_topic_changelogger=False, subscribe=True) # a topic that an outside device can request a change to
        
        self.switch_funcs = {}
        self.request_topic.on_message = self.on_message

    def on_message(self, client, userdata, msg, loop):
       payload = msg.payload.decode()
       if(payload in self.switch_funcs): self.switch_funcs[payload](client, userdata, msg, loop)
       


    def create_switch(self, sw_name, payload = "", retain=False):
        name = "{}_{}".format(self.topicname.replace("/", "_"), sw_name)
        if(not payload):
            payload = name
        payload_on = f"{payload} on"
        payload_off = f"{payload} off"



        interface = SwitchInterface(name, payload_on, payload_off, self.request_topic, self.recieve_topic, retain)
        self.switch_funcs[payload_on] = interface.callback_helper
        self.switch_funcs[payload_off] = interface.callback_helper
        return interface


EntityGenerator = SwitchTopic