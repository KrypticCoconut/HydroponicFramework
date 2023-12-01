from AtlasScientific.AtlasI2C import (
	 AtlasI2C
)


def load(control, log_f, config):
    probes = {}
    device = AtlasI2C()
    device_address_list = device.list_i2c_devices()
    for i in device_address_list:
        device.set_i2c_address(i)
        response = device.query("I")
        try:
            moduletype = response.split(",")[1] 

            response = device.query("name,?").split(",")[1]
        except IndexError:
            continue
        d = AtlasI2C(address = i, moduletype = moduletype, name = response)
        log_f(f"Loaded probe '{moduletype}'' at address '{i}'")
        probes[moduletype] = d
    return {"probes": probes}