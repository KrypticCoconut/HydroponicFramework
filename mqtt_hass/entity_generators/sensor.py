from mqtt_hass.TopicsClient import TopicsClient
from mqtt_hass.HassEntitiesManager import HassEntitiesManager

topicsClient: TopicsClient = None
hassEntityManager: HassEntitiesManager = None

class Sensor():
    def __init__(self, topicname, retain=False, create_topic_changelogger=False) -> None:
        self.topicname = topicname
        self.discovery_topic = None
        self.retain = retain
        self.hassentity = None

        self.recieve_topic = topicsClient.create_topic(self.topicname + "/recieve", create_topic_changelogger=create_topic_changelogger, subscribe=False) # topic where an outside device gets info about its request
        self.name = self.topicname.replace("/", "_")

    def register_to_hass(self, friendly_name, unit_of_measurement = None):
        config = {
            "state_topic": self.recieve_topic.name_mqtt,            
        }
        # print(friendly_name, self.recieve_topic.name_mqtt)
        if(unit_of_measurement != None):
            config["unit_of_measurement"] = unit_of_measurement
        self.hassentity = hassEntityManager.create_entity(entity_name = self.name, friendly_name=friendly_name, component_type="sensor", config = config)

    def publish(self, value):
        self.recieve_topic.publish(value, retain=self.retain)


EntityGenerator = Sensor