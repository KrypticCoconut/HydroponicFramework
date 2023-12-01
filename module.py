
from abc import abstractmethod
from textwrap import wrap
import types
import collections
from itertools import chain

class aobject(object):
    """Inheriting this class allows you to define an async __init__.

    So you can create objects by doing something like `await MyClass(params)`
    """
    async def __new__(cls, *a, **kw):
        instance = super().__new__(cls)
        await instance.__init__(*a, **kw)
        return instance

    async def __init__(self):
        pass

 
class TaskManager:
    def __init__(self, cls) -> None:
        self.cls = cls

        self._run_functions = {}
        self._load_functions = {}
        self._unload_functions = {}

        def wrapper(type, func):
            async def inner(instance, *args, **kwargs):
                if(not getattr(cls, "configured")): return
                self.cls.log(f"Running {type} function {func.point} for module {self.cls.name}")
                # self.log(f"Running {type} function {func.point} for module {self.cls.name}")
                try:
                    ret =  await func(instance, *args, **kwargs)
                    return ret
                except Exception as e:
                    self.cls.log(f"{type} function {func.point} for module {self.cls.name} errored out, {e}", level="Warning")
            return inner


        for attr in dir(cls):
            attr = getattr(cls, attr)
            if(isinstance(attr, types.FunctionType)):
                if(getattr(attr, "load_func", None)):
                    if(not attr.point in self._load_functions):
                        self._load_functions[attr.point] = []
                    self._load_functions[attr.point].append(wrapper("load", attr))
                elif(getattr(attr, "unload_func", None)):
                    if(not attr.point in self._unload_functions):
                        self._unload_functions[attr.point] = []
                    self._unload_functions[attr.point].append(wrapper("unload", attr))
                elif(getattr(attr, "run_func", None)):
                    if(not attr.point in self._run_functions):
                        self._run_functions[attr.point] = []
                    self._run_functions[attr.point].append(wrapper("run", attr))
        
            

class Module:

    def __init__(self) -> None:
        self._running = None
        self._activated = None

        self.localized_run_funcs = []
        def wrapper(func):
            def inner(*args, **kwargs):
                return func(self, *args, **kwargs)
            return inner
        for func in list(chain.from_iterable(collections.OrderedDict(sorted(self.taskmanager._run_functions.items())).values())):
            self.localized_run_funcs.append(wrapper(func))



        self.localized_load_funcs = []
        for func in list(chain.from_iterable(collections.OrderedDict(sorted(self.taskmanager._load_functions.items())).values())):
            self.localized_load_funcs.append(wrapper(func))


        self.localized_unload_funcs = []
        for func in list(chain.from_iterable(collections.OrderedDict(sorted(self.taskmanager._unload_functions.items())).values())):
            self.localized_unload_funcs.append(wrapper(func))


    def __init_subclass__(cls) -> None:
        cls.taskmanager = TaskManager(cls)

    @property
    def activated(self):
        return self._activated

    @property
    def running(self):
        return self._running

    @classmethod
    def run_func(cls, point):
        def wrap(func):
            func.point = point
            func.run_func = True
            return func 
        return wrap

    @classmethod
    def load_func(cls, point):
        def wrap(func):
            func.point = point
            func.load_func = True
            return func 
        return wrap

    @classmethod
    def unload_func(cls, point):
        def wrap(func):
            func.point = point
            func.unload_func = True
            return func 
        return wrap

    @abstractmethod
    def get_cooldown(self):
        pass

    async def execute_run_funcs(self):
        # self.control.log(f"Running run functions for {self.name}")
        for func in self.localized_run_funcs:
            await func()

    async def execute_load_funcs(self):
        # self.control.log(f"Running load functions for {self.name}")
        for func in self.localized_load_funcs:
            await func()

    async def execute_unload_funcs(self):
        # self.control.log(f"Running unload functions for {self.name}")
        for func in self.localized_unload_funcs:
            await func()


