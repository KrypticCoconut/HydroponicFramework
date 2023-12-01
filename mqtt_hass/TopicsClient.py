
import paho.mqtt.client as mqtt 
import time
import asyncio
import threading

class Topic():
    def __init__(self, name_mqtt, log) -> None:
        self.log = log
        self.name_mqtt = name_mqtt
        self.name = self.name_mqtt.replace("/", "_")
        self.on_message = None
        self.publish = None


class TopicsClient():

    def __init__(self, control, address, port, changelog_path, username, password, _loop) -> None:
        self.address = address
        self.port = port
        
        self._loop = _loop

        client = mqtt.Client("P1")
        if(username and password):
            client.username_pw_set(username, password)
        client.connect(address, port)
        
        def on_message(client, userdata, message):
            # data = str(message.payload.decode("utf-8"))
            self.log(message.topic, f"recieved message [{message.payload}] on [{message.topic}]")
            if(self.topics[message.topic].on_message): self.topics[message.topic].on_message(client, userdata, message, _loop)
        client.on_message = on_message
        
        self.client = client
        self.topics = {}
        self.running = False
        self.backlog = {}
        self.control = control
        self.changelog_path = changelog_path

        self.main_log_topic_name = f"{self.changelog_path}/all"
        self.main_log = None

        self.discovery_generator = None
        self.discovery_depth = 0

        

    def create_main_logger(self):
        self.main_log = self.control.create_logger(self.main_log_topic_name, create_topic_changelogger=False, stdout=False)


    def log(self, topic, message):
        if(topic == self.main_log_topic_name):
            return

        # print(topic, self.topics)
        # print(self.topics, topic, message)
        if(e := self.topics.get(f"{topic}", None)): 
            if(e.log): 
                e.log(message)
                print(self.main_log)
                if(self.main_log): self.main_log.log("{}: {}".format(topic, message))

    def create_topic(self, topic, create_topic_changelogger=False, subscribe=True): # can specift log for in case we are creating a logger which creates a topic and we dont have mqtt self.log yet
        
        
        if(create_topic_changelogger):
            log = self.control.create_logger( name=  f"{self.changelog_path}/{topic}", create_topic_changelogger=False, stdout=False).log        
        else: log = None
        
        t = Topic(topic, log)
        self.topics[topic] = t

        def wrap(m, retain=True): self.publish(topic, m, retain=retain)
        t.publish = wrap
        if(subscribe): 
            self.client.subscribe(topic)
            self.log(topic, f"subscribed to [{topic}]")
        
        return t


    def publish(self, topic, message, retain = True):
        if(not self.running):
            if(not topic in self.backlog):
                self.backlog[topic] = []
            self.backlog[topic].append(message)
            self.log(topic, f"keeping message in backlog [{message}] for [{topic}]")
            return
        self.client.publish(topic, message, retain=retain)
        self.log(topic, f"published message [{message}] to [{topic}]")


    def start(self):
        self.control.log("Started mqtt")
        self.client.loop_start()
        self.running = True
        

    def clear_backlog(self):
        self.control.log("Clearing mqtt backlog...")
        for topic, messages in self.backlog.items():
            for message in messages:
                self.topics[topic].publish(message)
                time.sleep(0.01)
        self.control.log("Cleared backlog")


# cli = TopicsClient("127.0.0.1", 1883, log=log)
# t = cli.create_topic("ph/value")
# cli.client.loop_start()
# t.publish(5.4)
# time.sleep(1)

