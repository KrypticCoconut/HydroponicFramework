
import json
import asyncio
from pydoc import cli
import time


class Dosing_Controller:
    def __init__(self, pump_pin, pump_mlps, pump_liquid, id, switchtopic, log) -> None:
        self.log = log
        self.id = id
        self.switchtopic = switchtopic
        self.lock = asyncio.Lock()
        self.dosing_id = f"doser{self.id}"

        self.pump_mlps = pump_mlps
        self.pump_liquid = pump_liquid
        self.pump_name = f"{self.dosing_id}_pump"
        self.pump_controller = McpController(pump_pin)
        
        mix_pin =  pump_pin.split(" ")[0] + " " + str(int(pump_pin.split(" ")[1])+1)
        self.mix_controller = McpController(mix_pin)
        self.fan_name = f"{self.dosing_id}_mix"

        self.pumpinterface = switchtopic.create_switch(self.pump_name)
        self.pumpinterface.register_to_hass(f"pump {self.id}/{self.pump_liquid}")
        self.mixinterface = switchtopic.create_switch(self.fan_name)
        self.mixinterface.register_to_hass(f"mix {self.id}")


        async def interface_callback_pump(client, userdata, req_state):
            if(self.lock.locked()): 
                self.log("cannot turn pump of group {} {}, lock is already acquired".format(self.id, ["off", "on"][int(req_state)]))
                return self.pump_state
            else:
                await self.lock.acquire()
                if(req_state):
                    self.pump_on(sw=False)
                else:
                    self.pump_off(sw=False)
                self.lock.release()
                return req_state

        async def interface_callback_mix(client, userdata, req_state):
            if(self.lock.locked()): 
                self.log("cannot turn mix of group {} {}, lock is already acquired".format(self.id, ["off", "on"][int(req_state)]))
                return self.mix_state
            else:
                await self.lock.acquire()
                if(req_state):
                    self.mix_on(sw=False)
                else:
                    self.mix_off(sw=False)
                self.lock.release()
                return req_state

        self.pumpinterface.callback = interface_callback_pump
        self.mixinterface.callback = interface_callback_mix

        self.pump_off()
        self.mix_off()

    @property
    def mix_state(self):
        if(self.mix_controller): return self.mix_controller.state
        return
    
    @property
    def pump_state(self):
        return self.pump_controller.state

    def mix_on(self, sw=True):
        if(sw): self.mixinterface.switch(True)
        if(self.mix_state == 1): return
        if(not self.lock.locked()): return
        self.mix_controller.on() 
        self.log(f"mix for liquid {self.pump_liquid}/ dosing pair {self.id} was turned on")
    
    def mix_off(self, sw=True):
        if(sw):self.mixinterface.switch(False)
        if(self.mix_state == 0): return
        if(not self.lock.locked()): return
        ret = self.mix_controller.off()
        self.log(f"mix for liquid {self.pump_liquid}/ dosing pair {self.id} was turned off")
        if(ret): return ret

    def pump_on(self, sw=True):
        if(sw):self.pumpinterface.switch(True)
        if(self.pump_state == 1): return
        if(not self.lock.locked()): return
        self.pump_controller.on() 
        self.log(f"pump for liquid {self.pump_liquid}/ dosing pair {self.id} was turned on")

    def pump_off(self, sw = True):
        if(sw):self.pumpinterface.switch(False)
        if(self.pump_state == 0): return
        if(not self.lock.locked()): return
        ret = self.pump_controller.off()
        self.log(f"pump for liquid {self.pump_liquid}/ dosing pair {self.id} was turned off")
        if(ret): return ret * self.pump_mlps

class AdvancedGpioController:
    def __init__(self, name, pin, info, switchtopic, log) -> None:
        self.info = info
        self.name = name
        self.log = log
        self.controller = GpioController(pin)
        self.lock = asyncio.Lock()
        self.switch_interface = switchtopic.create_switch(self.name.replace(" ", "_"))
        self.switch_interface.register_to_hass(self.name)

        async def interface_callback(client, userdata, req_state):
            if(self.lock.locked()): 
                self.log("cannot turn device {} {}, lock is already acquired".format(self.name, ["off", "on"][int(req_state)]))
                return self.state
            else:
                await self.lock.acquire()
                if(req_state):
                    self.on(sw=False)
                else:
                    self.off(sw=False)
                self.lock.release()
                return req_state

        self.switch_interface.callback = interface_callback
        self.off()


    @property
    def state(self):
        return self.controller.state

    def on(self, sw=True):
        if(sw): self.switch_interface.switch(True)
        if(not self.lock.locked()):
            return
        if(self.controller.state == 1):
            return
        self.controller.on()
        self.log(f"rpi GPIO device '{self.name}' turned on")

    def off(self, sw=True):
        if(sw): self.switch_interface.switch(False)
        if(not self.lock.locked()):
            return
        if(self.controller.state == 0):
            return
        ret = self.controller.off()
        self.log(f"rpi GPIO device '{self.name}' turned off")
        return ret
        

def load_objects(control, dir):
    prefix = "relays"
    logger = create_logger("relays", topic_name = f"{prefix}/log", create_topic_changelogger=False)

    switchtopic = SwitchTopic(f"{prefix}/switches")

    normal_relays = {}
    pumps = {}

    data = dir.subfiles["relaydeviceinfo.json"].jsonLoad()
    normal_confs = data["controllers"]["normal"]
    pump_confs = data["controllers"]["dosing_pumps"]

    for name, conf in normal_confs.items():
        pin = conf["pin"]
        del conf["pin"]
        info = conf
        normal_relays[name] = AdvancedGpioController(name, pin, info, switchtopic, logger.log )
        logger.log(f"Registered normal gpio device {name} at pin {pin}")

    pumps_by_liquid = {}
    for id, conf in pump_confs.items():
        id = int(id)
        pumps[id] = Dosing_Controller(conf["pin"], conf["mlps"], conf["liquid"], id, switchtopic, logger.log)
        liquid = conf["liquid"]
        pumps_by_liquid[liquid] = pumps[id]
        pin = conf["pin"]
        logger.log(f"Registered dosing pump {id} for {liquid} at pin {pin}")

    return {"normal_controllers": normal_relays, "dosing_controllers_by_id": pumps, "dosing_controllers_by_liquid": pumps_by_liquid}