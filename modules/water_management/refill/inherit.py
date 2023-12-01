pin = 25

def check():
    return GPIO.input(pin)

def load_objects(control, dir):
    GPIO.setup(pin, GPIO.IN)   
    return{"check_water_at_level": check}