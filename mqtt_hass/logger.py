import logging
import os
import sys

entity_generators = None

class Logger:
	def __init__(self, control, name, create_topic_changelogger=False, stdout=True, *args, **kwargs) -> None:

		logger = logging.getLogger(name)
		logger.setLevel(logging.DEBUG)
		formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s',
									  '%m-%d-%Y %H:%M:%S')

		# create stdout stream
		if(stdout):
			stdout_handler = logging.StreamHandler(sys.stdout)
			stdout_handler.setLevel(logging.DEBUG)
			stdout_handler.setFormatter(formatter)
			self.stdout_handler = stdout_handler
			logger.addHandler(stdout_handler)

		# create log stream
		log_file = os.path.join(control.log_dir, "{}.log".format(name.replace("/", "_")))
		open(log_file, 'w').close()
		file_handler = logging.FileHandler(log_file)
		file_handler.setLevel(logging.INFO)
		file_handler.setFormatter(formatter)
		self.file_handler = file_handler 
		logger.addHandler(file_handler)

		self.logger = logger
		self.name = name
		self.topic_name = f"{self.name}/log"

		# # create logger and its discovery topic
		# self.discovery_topic = self.discovery_generator.get_discovery_topic(self.topic.name, "sensor")
		# self.config = {"state_topic": self.topic.name_mqtt, "name": self.topic.name}
		# self.discovery_generator.send_discovery_message(self.discovery_topic, self.config)
		# print("here", self.topic_name)
		self.sensor_entity = entity_generators["Sensor"](self.topic_name, create_topic_changelogger=create_topic_changelogger)
		self.sensor_entity.register_to_hass(f"{self.name} log")


	def log(self, message: str, level="info", capitalize=False, retain=False): # log_again just indicates wether we want to log to log/mqtt that this message was sent
		def func(s): return s[:1].lower() + s[1:] if s else ''
		if(not capitalize): 
			message = func(message)
		self.sensor_entity.publish("{} | {}".format(level, message))
		#datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		getattr(self.logger, level.lower())(f"{self.name} | "+ message)