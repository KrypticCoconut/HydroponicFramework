import asyncio
import re
import time

from module import aobject

REPLACE_NO_WAIT = 10

class Runtime(aobject):
	async def __init__(self, control,  module_order, modules, log, switchtopic, binarysensortopic) -> None:				
		self.module_order = module_order
		self.modules = modules
		self.log = log
		self.control = control

		self.log("Generating runtime for [{}]".format(" -> ".join(module_order)))
		self.run_cooldowns = {} # minimum time that must have passed to run a module again
		self.run_log = {} # last time a module was run
		
		self.activated = {} # which modules are activated
		self.running = None
		
		self.runningsensors = {} # binary sensors to notify if a module is running
		self.activateswitches = {} # switches to change activate
		self.runningtopic = binarysensortopic 
		self.activatedtopic = switchtopic

		self.access_lock = asyncio.Lock()
		await self.setup_modules()


	async def setup_modules(self):
		for module in self.module_order:
			module = self.modules[module]
			self.log(f"Running load funcs for module {module.name}")
			await module.execute_load_funcs()
			self.run_cooldowns[module.name] = None
			self.run_log[module.name] = None


			self.runningsensors[module.name] =  self.runningtopic.create_sensor(f"{module.name}", payload=f"{module.name} running")
			self.runningsensors[module.name].register_to_hass(f"{module.name} running")
			self.update_state(module, False)

			
			self.activateswitches[module.name] = self.activatedtopic.create_switch(f"{module.name}", payload=f"{module.name} activate")
			self.activateswitches[module.name].register_to_hass(f"Activate {module.name}")
			def wrap(_module):
				async def on_message(client, userdata, req_state):
					if(self.running == _module.name):
						self.log("Cannot {} module {}, module is running".format(["deactivate", "activate"][int(req_state)], module.name))
						return self.activated[_module.name]
					else:
						await self.access_lock.acquire()
						self.log("module {} {}".format(_module.name, ["deactivated", "activated"][int(req_state)]))
						self.activated[_module.name] = req_state
						_module._activated = req_state
						self.access_lock.release()
						if(req_state):
							self.run_cooldowns[_module.name] = 0
						return req_state
				return on_message

			self.activateswitches[module.name].callback = wrap(module)
			self.activated[module.name] = module.modinfo.activate_on_start
			self.activateswitches[module.name].switch(self.activated[module.name])
			module._activated = self.activated[module.name]

	def get_least_wait(self):
		l = []
		for module_name in self.module_order:
			if(not self.run_log[module_name] or not self.run_cooldowns[module_name]):
				l.append(REPLACE_NO_WAIT)
			else:
				l.append(max([0, self.run_cooldowns[module_name] - (time.time() - self.run_log[module_name])]))
		return min(l)

	async def run(self):
		while True:
			for module_name in self.module_order:
				try: 
					await self.access_lock.acquire()
						
					module = self.modules[module_name]
					# double check
					if(not self.activated[module_name] ): # if its not in activated
						continue
					if(self.run_log[module_name] and self.run_cooldowns.get(module_name, None) and time.time() - self.run_log[module_name] <= self.run_cooldowns[module_name]):
						continue

					self.log(f"Running {module_name}")
					
					self.update_state(module, True)
					await module.execute_run_funcs()
					self.run_cooldowns[module_name] = module.get_cooldown()

				except Exception as exception:
					self.log(f"Error - {exception}")
				finally:
					self.update_state(module, False)
					self.run_log[module_name] = time.time()
					self.access_lock.release()
					
					start_time = time.time()
					n =  self.get_least_wait()
					while (start_time + n) > time.time():
						await asyncio.sleep(0.1)
					
					# print("sleep end")

	def update_state(self, module, running):
		if(running == False):
			self.running = None
		else:
			self.running = module.name
		
		module._running = running
		self.runningsensors[module.name].switch(running)

