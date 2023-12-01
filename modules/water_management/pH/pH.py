from module import Module # wtf how does this work>!>!>
import asyncio
import datetime


# from pmp_controller import Pump_Controller


class pH(Module):

    @Module.load_func(1)
    async def initialize(self) -> None:

        self.dev = probes["pH"]

        pHconfig = self.workingdir.subdirectories["pH"].subfiles["config.json"].jsonLoad()
        self.pHconfig = pHconfig
        
        self.low = pHconfig["low"] # low pH value
        self.high = pHconfig["high"] # high pH value
        self.stable_count = pHconfig["stable_count"] # amount of stable records in order to verify validity of pH level (thus also # needed to actually check and correct pH)
        self.error_n = pHconfig["error_n"] # (x-n, x+n) is range for each stable record within each other
        self.cooldown = pHconfig["cooldown"] # min time between each recording
        self.dose_ml = pHconfig["dosing"]["dose_ml"] # amt of lliquid to dose for correction
        self.phup = dosing_controllers_by_liquid["pHUp"]
        self.phdown = dosing_controllers_by_liquid["pHDown"]

        commonConfig = self.workingdir.subfiles["common.json"].jsonLoad()
        self.chemical_mix_time = commonConfig["dosing_mix_time"]
        self.resevoir_mix_time = commonConfig["resevoir_mix_time"]
        
        self.readings = []

        # self.t_phval = topicsClient.create_topic("pH/value")
        # self.t_act = topicsClient.create_topic("pH/activation")


        # pH minimum and maximum
        self.entity_phmin = Number(f"{self.name}/minumum")
        self.entity_phmin.register_to_hass("pH low", min=0, max=self.high, mode="slider", step = 0.01) 
        self.entity_phmax = Number(f"{self.name}/maximum")
        self.entity_phmax.register_to_hass("pH high", min=self.low, max=12, mode="slider", step = 0.01) 

        async def on_message_min(client, userdata, msg):
            msg = float(msg.payload.decode())
            if(msg < self.high and not self.running):
                self.low = msg
                self.log(f"Changed pH low to {self.low}")
                self.entity_phmax.update_entity(min=self.low, max=12, mode="slider", step = 0.01)
            return self.low

        async def on_message_max(client, userdata, msg):
            msg = float(msg.payload.decode())
            if(msg > self.low and not self.running):
                self.high = msg
                self.log(f"Changed pH high to {self.high}")
                self.entity_phmin.update_entity(min=0, max=self.high, mode="slider", step = 0.01)
            return self.high

        self.entity_phmin.callback = on_message_min
        self.entity_phmax.callback = on_message_max
        self.entity_phmin.publish(self.low)
        self.entity_phmax.publish(self.high)

        # phstable
        self.entity_last_stable = Sensor(f"{self.name}/laststableval")
        self.entity_last_stable.register_to_hass("last stable value")

        # last_activation
        self.entity_last_activation = Sensor(f"{self.name}/lastactivationtime")
        self.entity_last_activation.register_to_hass("last time activated")

        #pH valuie
        self.entity_value = Sensor(f"{self.name}/value")
        self.entity_value.register_to_hass("pH value")

        # activation
        binary_sensor = BinarySensorTopic(f"{self.name}/liveactivation")
        self.entity_activation = binary_sensor.create_sensor("", payload="")
        self.entity_activation.register_to_hass("pH activation")

        self.recirculating_pump = normal_controllers["recirculating pump"]
        self.resevoir_mix = normal_controllers["resevoir mix"]

    @Module.run_func(1)
    async def run(self):

        self.dev.write("r")
        await asyncio.sleep(2)
        res = self.dev.read()
        ph = float(res.rstrip('\x00').split(":")[-1])
        self.readings.insert(0, ph)
        self.entity_value.publish(ph)

        
        self.log(f"pH: {ph}")

        if(len(self.readings) > self.stable_count):
            comparison = self.readings.pop(-1)
            high = comparison+self.error_n
            low = comparison - self.error_n

            consistent = True
            for reading in self.readings:

                if(not (low <= reading <= high) ):
                    consistent = False
                    break

            if(not consistent):
                self.entity_activation.switch(False)
                return self.cooldown
            
            avg = sum(self.readings)/len(self.readings)
            self.entity_last_stable.publish(avg)
            if(avg < self.low): # it is too low
                self.log(f"Correcting pH {avg} -> {self.low}")
                await self.correct_ph(True)
            elif(avg > self.high): # too high
                self.log(f"Correcting pH {avg} -> {self.high}")
                await self.correct_ph(False)
            else:
                self.entity_activation.switch(False)
        else:
            self.entity_activation.switch(False)

        return self.cooldown


    
    async def correct_ph(self, up):
        self.entity_last_activation.publish(datetime.datetime.now().strftime("%d %H:%M:%S"))
        self.entity_activation.switch(True)

        await self.phdown.lock.acquire()
        await self.phup.lock.acquire()
        await self.recirculating_pump.lock.acquire()
        await self.resevoir_mix.lock.acquire()

        
        if(up):
            regulator = self.phup
        else:
            regulator = self.phdown
        regulator.mix_off()
        regulator.pump_off()
        self.recirculating_pump.off()
        self.resevoir_mix.on()


        wait = self.dose_ml/regulator.pump_mlps



        regulator.mix_on()
        await asyncio.sleep(self.chemical_mix_time)
        regulator.mix_off()
        
        regulator.pump_on()
        await asyncio.sleep(wait)

        ml = regulator.pump_off()
        _t = ["phdown", "phup"][int(up)]
        self.log(f"Dosed {ml} ml of {_t} liquid")

        self.readings = []
        
        await asyncio.sleep(self.resevoir_mix_time)
        self.resevoir_mix.off()
        self.recirculating_pump.on()

        self.phdown.lock.release()
        self.phup.lock.release()
        self.recirculating_pump.lock.release()
        self.resevoir_mix.lock.release()

    def get_cooldown(self):
        return self.cooldown

    @Module.unload_func(1)
    def save_config(self):
        self.log("Adding changed to json")
        self.pHconfig["low"] = self.low
        self.pHconfig["high"] = self.high