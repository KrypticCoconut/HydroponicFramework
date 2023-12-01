# Pre_modules -> load utilities for actual modules. utilies are loaded into a {str: obj} dict called "utilities"
# Modules -> objects that run over and over again checking certain aspects of the system, basically our checks
# all of this will be held in Control

import asyncio
import os
import importlib.util
from queue import Full
import sys
import json
import asyncio
import glob
import subprocess
from typing_extensions import runtime
from module import Module

from runtime import Runtime
from loaders import FullLoader

from mqtt_hass.load_entity_generators import load_entity_generators
from mqtt_hass.logger import Logger

class set(set):  # hacky ass print solution
	def __str__(self) -> str:
		if (not self):
			return "{}"

		return super().__str__()[4:-1]


class Control:
	def __init__(self, working_dir) -> None:
		self.root = working_dir
		self.log = None

		self.log_dir = None
		self.module_dir = None
		self.utilities_dir = None
		
		self.runtimes = []
		self.entity_generators = {}
		self.entity_generators_obj = None

		self.loader = None

		self.hass_subprocess = None

	def create_logger(self, name, create_topic_changelogger=False, stdout=True, *args, **kwargs):
		return Logger(self, name, create_topic_changelogger=create_topic_changelogger, stdout=stdout, *args, **kwargs)
		
	def get_full_path(self, appended_path): return os.path.join(
		self.root, appended_path)

	def form_runtimes(self, modules):
		module_reqs = {}

		for module in modules.values():
			module_reqs[module.name] = module.modinfo.reqs

		operation_matrix = {}


		for module, reqs in module_reqs.items():
			if(not reqs):
				operation_matrix[module] = [module]
			else:
				operation_matrix[module] = set(reqs)


		while any(isinstance(x, set) for x in operation_matrix.values()):
			for module, reqs in operation_matrix.items():
				if(not isinstance(reqs, set)):
					continue

				dependences = []
				dependency_names = []
				all_resolved = True
				for req in reqs:
					
					while isinstance(req, str):
						name = req
						req = operation_matrix[req]

					if(isinstance(req, set)):
						all_resolved = False
						break

					dependences.append(req)
					dependency_names.append(name)

				if(not all_resolved):
					continue

				operation_matrix[module] = [el for arr in dependences for el in arr] + [module]
				for dependency in dependency_names:
					operation_matrix[dependency] = module

		runtimes = []
		for r in operation_matrix.values():
			if(isinstance(r, list)):
				runtimes.append(r)

		self.log("Forming runtimes...")
		return runtimes

	async def run_runtimes(self):
		self.log("Starting all runtimes...")
		try:
			await asyncio.gather(*[x.run() for x in self.runtimes])
		except Exception as e:
			self.log(f"Error - {e}")
			await self.unload()

	def load_directories(self):
		self.module_dir = self.get_full_path("modules")
		self.utilities_dir = self.get_full_path("utility_handlers")
		self.log_dir = self.get_full_path("logs")
		files = glob.glob(f"{self.log_dir}/*")
		for f in files:
			os.remove(f)

	async def initialize(self):


		self.load_directories()

		entity_generators = load_entity_generators(self, asyncio.get_event_loop())
		self.entity_generators_obj = entity_generators
		self.entity_generators = entity_generators.generators
		self.log = self.create_logger("main").log

		loader = FullLoader(self, self.utilities_dir, self.module_dir)
		loader.full_load()
		self.loader = loader
		runtimes =  self.form_runtimes(loader.modules_l.modules)
		
		
		switchtopic = self.entity_generators["SwitchTopic"]("control/modulesactivate")
		binarysensortopic = self.entity_generators["BinarySensorTopic"]("control/modulerunning")
		buttontopic = self.entity_generators["ButtonTopic"]("control/deactivate")
		button = buttontopic.create_button("", payload="")
		button.register_to_hass("deactivate core")

		# number = self.entity_generators["Number"]("test_number")

		# async def on_message(client, userdata, message):
		# 	data = str(message.payload.decode("utf-8"))
		# 	print(data)
		# 	return data
		# number.callback = on_message
		# number.register_to_hass("test number")


		# switcht = self.entity_generators["SwitchTopic"]("test/switchtopic")
		# switch = switcht.create_switch("test_switch")
		# async def on_message(client, userdata, state):
		# 	print(state)
		# 	await asyncio.sleep(3)
		# 	return state

		# switch.callback = on_message
		# switch.register_to_hass("test switch")


		# buttont = self.entity_generators["ButtonTopic"]("test/buttontopic")
		# button = buttont.create_button("test_button")
		# async def on_message(client, userdata):
			# print("pressedf!")
			# await asyncio.sleep(3)

		# button.callback = on_message
		# button.register_to_hass("test button")

		async def restart(client, userdata):
			self.log("Unloading core")
			self.hass_subprocess.kill()
			self.entity_generators_obj.restore_hass_conf()
			
			await self.unload()
			sys.exit()
			# self.log("Restarting")
			# subprocess.call(["sudo", "reboot", "now"])
		
		button.callback = restart

		self.runtimes = [await Runtime(self, x, self.loader.modules_l.modules, self.log, switchtopic=switchtopic, binarysensortopic=binarysensortopic) for x in runtimes]	
		
	
		entity_generators.register_entities_to_hass()
		self.start_hass()
		entity_generators.start_channels()
		
		# while True:
		# 	await asyncio.sleep(2)

		await self.run_runtimes()
	

	def start_hass(self):
		import time, socket
		from contextlib import closing

		self.log("Starting hass")
		subprocess.run(["rm", "/home/krypt/.homeassistant/home-assistant_v2.db"])
		self.hass_subprocess = subprocess.Popen( ["hass"])

		open = False
		while not open:
			with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
				if sock.connect_ex(('127.0.0.1', 8123)) == 0:
					open=True
		self.log("Hass port is open, waiting for a bit")
		time.sleep(10)

	
	async def unload(self):
		self.log("acquiring runtime locks")
		for runtime in self.runtimes:
			await runtime.access_lock.acquire()
		self.log("calling loader unload...")
		await self.loader.call_unload_methods()

		self.log("saving configs")
		self.loader.modules_l.root.save_configs()

if __name__ == "__main__":
	main = Control(os.path.abspath(os.getcwd()))
	asyncio.run(main.initialize())
	