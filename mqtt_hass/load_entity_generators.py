import imp
import json
import os
from mqtt_hass.TopicsClient import TopicsClient
from mqtt_hass.HassEntitiesManager import HassEntitiesManager
import importlib.util
import mqtt_hass.logger as logger

hassEntityManager = None
topicsClient = None

class Entitity_Generators:
    def __init__(self, entity_dir_path, hass_entity_manager, topicsClient, control) -> None:
        self.entity_dir_path = entity_dir_path
        self.hass_entity_manager = hass_entity_manager
        self.topicsClient = topicsClient
        self.generators = {}

        self.load_entity_generators()

    def load_entity_generators(self):
        for file in os.listdir(self.entity_dir_path):
            fp = os.path.join(self.entity_dir_path, file)
            spec = importlib.util.spec_from_file_location("generator", fp)
            if(not spec):
                continue
            module_spec = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module_spec)

            module_spec.topicsClient = self.topicsClient
            module_spec.hassEntityManager = self.hass_entity_manager
            cls = module_spec.EntityGenerator
            self.generators[cls.__name__] = cls

    def start_channels(self):
        self.topicsClient.start()
        self.topicsClient.clear_backlog()

    def register_entities_to_hass(self):
        self.hass_entity_manager.register_entities()

    def restore_hass_conf(self):
        self.hass_entity_manager.restore_original_hass_conf()

def load_entity_generators(control, loop):
    with open(control.get_full_path("mqtt_hass/config.json"), 'r') as f:
        data = json.load(f)

    topicsClient = create_topicsClient(control, data["address"], data["port"], data["username"], data["password"], loop)
    hassEntityManager = HassEntitiesManager(topicsClient, data["discovery_prefix"], control.get_full_path("mqtt_hass/hass_entity_topics.json"), control.get_full_path("mqtt_hass/friendly.yaml"), data["hass_conf_path"], control)
    hassEntityManager.remove_old_entities()
    entityGenerators = Entitity_Generators(control.get_full_path("mqtt_hass/entity_generators"), hassEntityManager, topicsClient, control)
    logger.entity_generators = entityGenerators.generators
    topicsClient.create_main_logger()
    # you can use any logger or entity after this point

    return entityGenerators
    
        
def create_topicsClient(control, address, port, username, password, loop):
    return TopicsClient(control, address, port, "changelog", username, password, loop)