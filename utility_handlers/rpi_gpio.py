# import RPi.GPIO as GPIO    
  

# def check():
#     return GPIO.input(25)

# def load(control, utilities, log_f, config):

#     GPIO.setmode(GPIO.BCM)  
#     GPIO.setup(25, GPIO.IN)   
#     utilities["check_water_at_level"] = check

# def unload(control, utilities, log_f, config):
#     GPIO.cleanup() 

import RPi.GPIO as GPIO    
import time



class GpioController():
  def __init__(self, pin) -> None:
        self.pin = pin

        GPIO.setup(self.pin, GPIO.OUT)
        log(f"Setup pin {pin} as output")
        self.state = 0
        self.on_time = None
        
        self.off()
  
  def on(self):
        log(f"Turning on gpio pin {self.pin}")
        self.state = 1
        self.on_time = time.time()
        GPIO.output(self.pin, 1)
  
  def off(self):
        log(f"Turning off gpio pin {self.pin}")
        self.state = 0
        GPIO.output(self.pin, 0)
        if(self.on_time):
            _t = self.on_time
            self.on_time = None 
            return time.time() - _t

  

def load(control, log_f, config):
    global log
    log = log_f

    GPIO.setmode(GPIO.BCM)  
    log("Loading rpi.gpio in BCM mode")
    return {"GPIO": GPIO, "GpioController": GpioController}

def unload(control, log_f, config, *args, **kwargs):
    GPIO.cleanup() 