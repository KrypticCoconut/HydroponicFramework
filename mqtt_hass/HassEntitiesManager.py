from html import entities
from pydoc_data.topics import topics
import time
import json
import os
import yaml

class HassEntitiesManager():
    def __init__(self, topicsClient, discovery_prefix, dtopics_path, friendly_path, hass_conf_path, control) -> None:
        self.dtopics_path = dtopics_path
        self.friendly_path = friendly_path
        self.topicsClient = topicsClient
        self.discovery_prefix = discovery_prefix
        self.control = control
        self.hass_conf_path = hass_conf_path
        
        self.entities = []

        with open(self.hass_conf_path, 'r') as f:
            self.original_hass_conf = f.read()

        if(not os.path.exists(self.dtopics_path)):
            with open(self.dtopics_path, "w") as f:
                json.dump([], f)

        HassEntity.topicsClient = self.topicsClient
        HassEntity.discovery_prefix = discovery_prefix

    def remove_old_entities(self):

        with open(self.dtopics_path, 'r') as f:
            data = json.load(f)

        for topic in data:
            self.topicsClient.create_topic(topic, subscribe=False).publish(b'', retain=True)

    def create_entity(self, *args, **kwargs):
        entity = HassEntity(*args, **kwargs)
        self.entities.append(entity)
        return entity

    def register_entities(self): # sends config to entity topic, adds friendly names to yamls, adds to retained_path
        discovery_topics = []
        entities_conf = {}
        for entity in self.entities:
            entity.push_entity_config()
            discovery_topics.append(entity.discovery_topic.name_mqtt)
            entities_conf[entity.hass_id] = {"friendly_name": entity.friendly_name}
        

        if(not os.path.exists(self.friendly_path)):
            open(self.friendly_path, 'w').close()

        ha_conf = {}        
        ha_conf["homeassistant"] = {}
        ha_conf["homeassistant"]["customize"] = entities_conf

        with open(self.friendly_path, 'w') as f:
            yaml.dump(ha_conf, f)

        with open(self.friendly_path, 'r') as f2:
            yamlstr = f2.read()

        newconf = self.original_hass_conf + "\n" + yamlstr
        with open(self.hass_conf_path, 'w') as f:
            f.write(newconf)
        


        # add discovery_topics to dtopics_file for cleanup at next boot
        with open(self.dtopics_path, 'w') as f:
            json.dump(discovery_topics, f)

        self.control.log("New entities are in effect")

    def restore_original_hass_conf(self):
        with open(self.hass_conf_path, 'w') as f:
            f.write(self.original_hass_conf)


        
            

class HassEntity():
    discovery_prefix = None
    topicsClient = None

    def __init__(self, entity_name, friendly_name, component_type, config) -> None:
        self.entity_name = entity_name
        self.friendly_name = friendly_name
        self.component_type = component_type
        self.config = config

        self.object_id = self.entity_name
        self.hass_id = f"{self.component_type}.{self.entity_name}"

        self.discovery_topic = None
        self.activated = False

        self.create_topic()

    def create_topic(self):
        topicname = f"{self.discovery_prefix}/{self.component_type}/{self.object_id}/config"
        self.discovery_topic = self.topicsClient.create_topic(topicname, create_topic_changelogger=False, subscribe=False)

    def push_entity_config(self):
        self.config["name"] = self.entity_name
        self.discovery_topic.publish(json.dumps(self.config), retain=True)
        self.activated = True
        # log here

    def update_entity_config(self, **kwargs):
        if(not self.activated):
            return
        # log
        for name, val in kwargs.items():
            self.config[name] = val
        self.discovery_topic.publish(json.dumps(self.config), retain=True)
        
        



# class HassDiscoveryGenerator():

#     def __init__(self, control, topicsClient, discovery_prefix, retain_path) -> None:
#         self.discovery_prefix = discovery_prefix
#         self.control = control
#         self.topicsClient: TopicsClient = topicsClient
#         self.new_retained_topics = []
#         self.retain_path = retain_path
#         self.curr_id = 0



#     def clear_old_retained(self):

#         if(not os.path.exists(self.retain_path)):
#             with open(self.retain_path, "w") as f:
#                 json.dump([], f)

#         with open(self.retain_path, 'r') as f:
#             data = json.load(f)

#         for topic in data:
#             self.topicsClient.create_topic(topic, subscribe=False).publish(b'', retain=True)

#     def save_new_retain(self):
#         with open(self.retain_path, "w") as f:
#             json.dump(self.new_retained_topics, f)
#         if(self.new_retained_topics): self.control.log("Retained topics saved")
#         else: self.control.log("Nothing retained")


#     def get_discovery_topic(self, topic, component, create_topic_changelogger=False, subscribe=False):
#         payload_topic = self.get_payload_topic_name(topic, component)
#         return self.topicsClient.create_topic(payload_topic, create_topic_changelogger=create_topic_changelogger, subscribe=subscribe)
        
#     def send_discovery_message(self, topic, config ):
#         topic.publish(json.dumps(config))
#         self.new_retained_topics.append(topic.name_mqtt)

#     def get_payload_topic_name(self, topic, component):
#         # name = topic.replace("/", "_").replace(" ", "_")
#         name = topic
#         payload_topic = f"{self.discovery_prefix}/{component}/{name}/config"
#         return payload_topic
