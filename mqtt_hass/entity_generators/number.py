from mqtt_hass.TopicsClient import TopicsClient
from mqtt_hass.HassEntitiesManager import HassEntitiesManager
import threading

topicsClient: TopicsClient = None
hassEntityManager: HassEntitiesManager = None

# Explanation callback vs callback helper:
# the topicslcient recieved subscribed messages in a sperate thread, and then it calls a syncronous helper function in that thread
# this method can then create a task in the main asyncio event loop
# the first method is called callback helper and the second one is called callback
# in general, there is no guarentee when 2 parralel events in seperate threads will have time syncronosity
# but since callback can only run when the asyncio loop is free, we can be that the call time of callback helper and callback could be different
# though callback_helper will always be called linearly i.e. one after the other 
# this means we linearly assign a set of tasks, and they are later run in whatever order
# we have to curate this order
  
# there are 3 events that can be registered -> 1. when callback helper is called, 2.when callback is entered, 3.when callback is exited
# there is only 1 state -> 4. if another callback is running

# in general, we want to only run the last callback called, this can be done using 1
# if something a callback is running, we dont want to run any new callbacks
# if another callback was exited between 1 and 2, then we want to exit out
# this last rule is only specific to callbacks, (so no 0 time callbacks i.e. None) because they might be changing states 

class Number():
    def __init__(self, topicname, retain=False) -> None:
        self.topicname = topicname
        self.discovery_topic = None
        self.retain = retain
        self.hassentity = None

        self.name = self.topicname.replace("/", "_")
        self.recieve_topic = topicsClient.create_topic(self.topicname + "/recieve", create_topic_changelogger=False, subscribe=False) # topic where an outside device gets info about its request
        self.request_topic = topicsClient.create_topic(self.topicname + "/request", create_topic_changelogger=False, subscribe=True) # a topic that an outside device can request a change to

        self.callback_lock = threading.Lock()
        self.request_topic.on_message = self.callback_helper
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
        with self.callback_lock:
            self.base_callback_counter += 1

            callback = self._callback
            if(callback):
                curr_base_counter = self.base_callback_counter
                curr_finished = self.callback_finished_counter
                async def wrap(client, userdata, message):
                    self.tmpstate = float(message.payload.decode())
                    if(self.running):
                        #log
                        self.publish(self.tmpstate)
                        return
                    if(curr_base_counter != curr_base_counter): # it is not the most recent callback
                        #log
                        self.publish(self.state)
                        return
                    
                    if(curr_finished != self.callback_finished_counter): # functions were executed between the 2 calls
                        #log
                        self.publish(self.state)
                        return

                    self.running = True
                    print("calling callback")
                    p = await self.callback(client, userdata, message) # during this code, other callbacks may be called
                    # everything after this is synchronous, so the event loop cant call wrap again whilst chaning running state
                    self.publish(p)
                    self.callback_finished_counter += 1
                    self.running = False
                print("creating task")
                loop.create_task(wrap(client, userdata, message))

    def publish(self, value):
        self.recieve_topic.publish(value, retain=self.retain)
        self.state = value # wierd code


    @property
    def on_message(self):
        return self.request_topic.on_message
    
    @on_message.setter
    def on_message(self, value):
        self.request_topic.on_message = value


    def register_to_hass(self, friendly_name, **kwargs):

        config = {
            "state_topic": self.recieve_topic.name_mqtt,
            "command_topic": self.request_topic.name_mqtt,
        }

        if(kwargs):
            config.update(kwargs)

        self.hassentity = hassEntityManager.create_entity(entity_name = self.name, friendly_name=friendly_name, component_type="number", config = config)

    def update_entity(self, **kwargs):
        self.hassentity.update_entity_config(**kwargs)


EntityGenerator = Number