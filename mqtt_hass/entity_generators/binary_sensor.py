from mqtt_hass.TopicsClient import TopicsClient
from mqtt_hass.HassEntitiesManager import HassEntitiesManager

topicsClient: TopicsClient = None
hassEntityManager: HassEntitiesManager = None

class BinarySensorInterface():
    def __init__(self, name, on, off, recieve_topic, retain) -> None:
        self.payload_on = on
        self.name = name
        self.payload_off = off
        self.recieve_topic = recieve_topic
        self.discovery_topic = None
        self.retain = retain

    def switch(self, state: bool):
        if(state):
            self.recieve_topic.publish(self.payload_on, retain=self.retain)
        else:
            self.recieve_topic.publish(self.payload_off, retain=self.retain)

    def register_to_hass(self, friendy_name):
        config = {
            "state_topic": self.recieve_topic.name_mqtt,
            "payload_on": self.payload_on,
            "payload_off": self.payload_off,
        }
        self.hassentity = hassEntityManager.create_entity(entity_name = self.name, friendly_name=friendy_name, component_type="binary_sensor", config = config)        

class BinarySensorTopic():
    def __init__(self, topicname) -> None:
        self.topicname = topicname


        # Note: request and recieve are defined from the point of an outside entity, trying to control a given state
        self.recieve_topic = topicsClient.create_topic(self.topicname + "/recieve", create_topic_changelogger=False, subscribe=False) # topic where an outside device gets info about its request

    def create_sensor(self, sensor_name, payload=None, retain=False):
        if(sensor_name):
            name = "{}_{}".format(self.topicname.replace("/", "_"), sensor_name)
        else:
            name = self.topicname.replace("/", "_")
        if(payload != None):
            payload = name
        payload_on = f"{payload} on"
        payload_off = f"{payload} off"

        interface = BinarySensorInterface(name, payload_on, payload_off, self.recieve_topic, retain)
        return interface



EntityGenerator = BinarySensorTopic