from ast import Mod
import asyncio
import datetime
from email.mime import base
from module import Module
import time

class Refill(Module):

    @Module.load_func(1)
    async def initialize(self) -> None:


        baseConfig = self.workingdir.subdirectories["refill"].subfiles["config.json"].jsonLoad()
        self.baseConfig = baseConfig
        chemicals = baseConfig["chemicals"]
        self.cooldown = baseConfig["cooldown"]

        self.chemicals = {}
        
        for chemical, mlps in chemicals.items():
            self.chemicals[dosing_controllers_by_liquid[chemical]] = mlps

        commonConfig = self.workingdir.subfiles["common.json"].jsonLoad()
        self.chemical_mix_time = commonConfig["dosing_mix_time"]
        self.resevoir_mix_time = commonConfig["resevoir_mix_time"]
        
        self.refill_pump = normal_controllers["refill pump"]
        self.refill_pump_mlps = self.refill_pump.info["GPH"] * 0.001052*1000
        
        self.recirculating_pump = normal_controllers["recirculating pump"]
        self.recirculating_pump_wait = self.recirculating_pump.info["time_to_drain"]
        # print(self.recirculating_pump_wait)

        self.resevoir_mix = normal_controllers["resevoir mix"]

        self.first_start = True

        for chemical in self.chemicals.keys():
            entity = Number(f"{self.name}/chemicals/{chemical.dosing_id}/doseamount")
            entity.register_to_hass(chemical.pump_liquid, mode="box")
            
            async def on_message(client, userdata, msg):
                msg = float(msg.payload.decode())
                if(not self.running):
                    self.chemicals[chemical] = msg
                    entity.publish(msg)
                else:
                    entity.publish(self.chemicals[chemical])

            entity.on_message = on_message
            entity.publish(self.chemicals[chemical])

        self.water_pumped = Sensor(f"{self.name}/waterpumped")
        self.water_pumped.register_to_hass("Liters water pumped")
        
        
    def get_cooldown(self):
        return self.cooldown # check every 8 hours

    @Module.run_func(1)
    async def run(self):
        for chemical in self.chemicals.keys():
            await chemical.lock.acquire()
        await self.recirculating_pump.lock.acquire()
        await self.refill_pump.lock.acquire()
        await self.resevoir_mix.lock.acquire()

        self.recirculating_pump.on()
        
        # if(self.first_start):
        #     self.first_start = False
        # else:
        #     self.log(f"Stopping recirculation and waiting {self.recirculating_pump_wait} seconds")
        #     self.recirculating_pump.off()
        #     await asyncio.sleep(self.recirculating_pump_wait)
        if(not check_water_at_level()):
            self.log("Adding refill water")
            self.refill_pump.on()
            while not check_water_at_level():
                await asyncio.sleep(0.5)
            liters_water = self.refill_pump.off()/1000
            liters_water = 0.5
            self.water_pumped.publish(liters_water)
            self.log(f"Pumped {liters_water} liters of water into recirculating resevoir")

            # SIMPLE
            # dosing_q = self.dose_mlpl * liters_water
            self.resevoir_mix.on()
            for chemical, dosing_q in self.chemicals.items():
                dosing_q = dosing_q * liters_water
                self.log(f"Dosing {dosing_q} of {chemical.pump_liquid}")
                self.log(f"Mixing {chemical.pump_liquid}")
                chemical.mix_on()
                await asyncio.sleep(self.chemical_mix_time)
                chemical.mix_off()

                wait = dosing_q/chemical.pump_mlps
                self.log(f"{dosing_q}/{chemical.pump_mlps} = {wait} seconds")
                chemical.pump_on()
                await asyncio.sleep(wait)
                chemical.pump_off()
            self.log("Mixing for a bit more...")
            await asyncio.sleep(self.resevoir_mix_time)
            self.resevoir_mix.off()

        # self.log("Starting recirculation, next check will be at {}".format(datetime.datetime.now() + datetime.timedelta(0, self.cooldown)))
        # self.recirculating_pump.on()

        for chemical in self.chemicals.keys():
            chemical.lock.release()
        self.recirculating_pump.lock.release()
        self.resevoir_mix.lock.release()
        self.refill_pump.lock.release()
        return self.cooldown

    @Module.unload_func(1)
    def unload(self):
        for chemical, dosinq in self.chemicals.items():
            self.baseConfig["chemicals"][chemical.pump_liquid] = dosinq