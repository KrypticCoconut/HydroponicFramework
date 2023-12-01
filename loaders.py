import os
import sys
from osclasses import *
from module import Module
import importlib.util
import copy
import json


class LoadingInfo:
    utility_dir = None
    module_dir = None
    control = None
    
    @classmethod
    def setup(cls, control, utility_dir, module_dir):
        LoadingInfo.utility_dir = utility_dir
        LoadingInfo.module_dir = module_dir
        LoadingInfo.control = control

        if(not os.path.exists(utility_dir)):
            control.log("utility dir does not exist, exiting", level="warning")
            sys.exit()

        if(not os.path.exists(module_dir)):
            control.log("module dir does not exist, exiting", level="warning")
            sys.exit()


class ModulePack:
    def __init__(self, module_dir, dirobj, module_spec, activate_on_start) -> None:
        self.dirobj = dirobj
        self.load_data = dirobj.load_content
        
        self.reqs = self.load_data["update_requirements"]
        self.working_dir = os.path.join(module_dir, self.load_data["working_directory"])
        self.class_file = dirobj.subfiles[self.load_data["class_file"]]
        self.class_name = self.load_data["class_name"]
        self.module_spec = module_spec
        self.activate_on_start = activate_on_start

        self.dir_path = dirobj.full_path
        self.file_path = self.class_file.full_path

        self.inherits = dirobj.get_inherits()
        self.utilities = self.dirobj.full_requirements

class _ModulesLoader(LoadingInfo):
    def __init__(self) -> None:
        self.log = self.control.log
        self.root = AdvancedDirectory("modules", self.module_dir)
        self.root.scan_directory()

        self.modulepacks = {}
        self.modules = {}

        self.inherits_inject_objs = {}



    def load_modulepacks(self):
        # get modules list - very unverified
        modules = self.root.get_children_modules()
        if(not modules):
            self.log("No modules found, exiting", level="critical")
            sys.exit()
        self.log("modules found are -> {}".format([x.name for x in modules]))

        # check modules utilities req
        modules_obj_l = []
        for module in modules:
            reqs = module.full_requirements
            d = True
            for req in reqs:
                if(not os.path.exists(os.path.join(self.utility_dir, f"{req}.py") )):
                    self.log(f"not loading module '{module.name}', utility '{req}' does not exist", level="warning")
                    d = False
                    break
            if(d): modules_obj_l.append(module)


        if(not modules_obj_l):
            self.log("Nothing left to load, exiting", level="critical")
            sys.exit()


        modules = {} 
        for module_dir_obj in modules_obj_l:
            module_dir_obj: AdvancedDirectory

            module_name = module_dir_obj.name
            data = module_dir_obj.load_content

            if (not all(k in data.keys() for k in ["update_requirements", "working_directory", "class_file", "class_name", "activate_on_start"])):
                self.log(
                    f"Module '{module_name}' has a incomplete load.json, will not be loading", level="warning")
                continue
            

            working_path = os.path.join(self.module_dir, data["working_directory"])
            if(not os.path.exists(working_path)):
                self.log(f"Module {module_name} working dir '{working_path}' does not exist, will not be loading", level="warning")
                continue
            
            
            if(data["class_file"] not in module_dir_obj.subfiles.keys()):
                self.log("Module {} file '{}' does not exist in directory, will not be loading".format(module_name, data["class_file"]), level="warning")
                continue
            
            class_file = module_dir_obj.subfiles[data["class_file"]].full_path

            try:
                sys.path.insert(0, working_path)
                spec = importlib.util.spec_from_file_location("modules", class_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception as e:
                self.log(f"Failed to load {module_name} spec - {e}")
                continue
                

            e = getattr(module, data["class_name"], None)
            if(not e):
                self.log("Module '{}' class file '{}' has no class named '{}', will not be loading".format(module_name, class_file, data["class_name"]), level="warning")
                continue

            modules[module_name] = ModulePack(self.module_dir, module_dir_obj, module, data["activate_on_start"])
            self.log(f"Loaded {module_name} spec")

        if(not modules):
            self.log("Nothing left to load, exiting", level="critical")
            sys.exit()

        self.log(f"modules qualified pack check -> {set(modules.keys())} ...", capitalize=True)

        self.modulepacks = modules
        return self.modulepacks

    def filter_modulepacks(self, utilities):

        filtered = []
        for module_name, module in self.modulepacks.items():
            if(module_name in filtered):
                continue

            reqs = module.utilities
            for req in reqs:
                if(req not in utilities.utilities_loaded):
                    filtered.append(module_name)
                    self.log(f"{req} does not exist, {module_name} will not be loaded", level="warning")

                    break
            if(module_name in filtered): continue

        for filtered_module in filtered:
            del self.modulepacks[filtered_module]

        if(not self.modulepacks):
            self.log("Nothing left to load, exiting", level="critical")
            sys.exit()

        unused_utilities = copy.deepcopy(utilities.utilities_loaded)
        for modulepack in self.modulepacks.values(  ):
            reqs = modulepack.utilities
            for req in reqs:
                if(not (req in unused_utilities)): continue
                if(utilities.load_funcs[req]):
                    utilities.load_funcs[req]()
                unused_utilities.remove(req)
        
        for unused_utility in unused_utilities:
            self.log(f"utility {unused_utility} is not required for modules left")
            utilities.unload_utility_methods(unused_utility)


    def load_inherits(self, utility_objs):
        # self.log(f"Final module load list -> {set(self.modulepacks.keys())} ...", capitalize=True)

        inherits = set()
        inherits_numbered = {}
        for module in self.modulepacks.values():
            inherits.update(module.inherits)
        
        for i, inherit in enumerate(inherits):
            inherits_numbered[i] = inherit

        for module, _p in self.modulepacks.items():
            m_inherits = _p.inherits
            _p.inherits = [[k for k, v in inherits_numbered.items() if v == inherit][0] for inherit in m_inherits]
        self.log("{} inherits to be loaded".format(len(inherits)))		


        while len(inherits_numbered.keys()) != len(self.inherits_inject_objs.keys()):
            for number, inherit_file in inherits_numbered.items():
                if(number in self.inherits_inject_objs):
                    continue

                inherits_insert = {}
                b=False
                for inherit in inherit_file.parent.get_inherits():
                    target = list(inherits_numbered.keys())[list(inherits_numbered.values()).index(inherit)]	
                    if(target == number): continue

                    loaded = False
                    for _number, inherits_l in self.inherits_inject_objs.items():
                        if(_number == target):
                            for name, obj in inherits_l.items():
                                inherits_insert[name] = obj
                                
                            loaded = True
                    if(not loaded):
                        b=True
                        break	
                if(b):
                    continue

                sys.path.insert(0, inherit_file.parent.full_path)
                spec = importlib.util.spec_from_file_location("modules", inherit_file.full_path)
                module_spec = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module_spec)
                globals = module_spec.__builtins__ # this is one hacky solution!
                for utility in inherit_file.parent.full_requirements:
                    for name, obj in utility_objs[utility].items():
                        globals[name] = obj
                globals["create_logger"] =self.control.create_logger 
                for entity, cls in self.control.entity_generators.items():
                    globals[entity] = cls

                for name, obj in inherits_insert.items():
                    globals[name] = obj

                if(hasattr(module_spec, "load_objects")):
                    try:
                        self.inherits_inject_objs[number] = module_spec.load_objects(self, inherit_file.parent)
                        if(not self.inherits_inject_objs[number]):
                            self.inherits_inject_objs[number] = {}
                        self.log(f"Successfully loaded objects of inherit.py at {inherit_file.relative_path}")
                    except Exception as e:
                        self.log(f"load_objects of inherit.py at {inherit_file.relative_path} errored out: {e}", level="warning")
                        self.inherits_inject_objs[number] = {}
                else:
                    self.log(f"load_objects not found in inherit.py at {inherit_file.relative_path}, ignoring", level="warning")
                    self.inherits_inject_objs[number] = {}

    def load_modules(self, utilities_objs):
        for module, modinfo in self.modulepacks.items():
            modinfo: ModulePack
            # root.add_path( os.path.normpath(os.path.relpath(modinfo.file_path, module_dir)).split(os.sep), endsin_file=True, check_for_configs = True)
            
            module_spec = modinfo.module_spec
            globals = module_spec.__builtins__ # this is one hacky solution!
            for utility in modinfo.utilities:
                for name, obj in utilities_objs[utility].items():
                    globals[name] = obj

            for inherit in modinfo.inherits:
                # print(inherit, inherits_inject_objs)
                if(inherit in self.inherits_inject_objs.keys()):
                    for name, obj in self.inherits_inject_objs[inherit].items():
                        globals[name] = obj
            
            globals["create_logger"] =self.control.create_logger
            for entity, cls in self.control.entity_generators.items():
                globals[entity] = cls


            # try:
            log = log = self.control.create_logger(f"{modinfo.dirobj.name}")
            mod_class: Module = getattr(module_spec, modinfo.class_name)
            # except Exception as e:
                # self.log(f"Failed to initalize module '{module}' - {e}", level="warning")
                # continue
            mod_class.workingdir = self.root.resolve(os.path.normpath(os.path.relpath(modinfo.working_dir, self.module_dir)).split(os.sep))
            mod_class.log = log.log
            mod_class.modinfo = modinfo
            mod_class.name = modinfo.dirobj.name
            mod_class.control = self
            mod_class.configured = True

            self.modules[module] = mod_class()

            self.log(f"{module} - Loaded", capitalize=True)


        if(not self.modules):
            self.log("No modules were succefully loaded, exiting", level="critical")
            sys.exit()
        else:
            self.log(f"modules {set(self.modules.keys())} are loaded")

        for name, module in self.modules.items():
            new_reqs = []
            for req in module.modinfo.reqs:
                if(req in self.modules.keys()): new_reqs.append(req)
            module.modinfo.reqs = new_reqs
        self.log("Adjusted module requirements")




class _UtilitiesLoader(LoadingInfo):
    def __init__(self) -> None:
        self.log = self.control.log

        self.utilities_loaded = set()
        self.load_funcs = {}
        self.unload_funcs = {}
        self.utilities = {}

    def unload_utility_methods(self, utility):
        self.log(f"Unloading methods for {utility}")
        self.utilities_loaded.remove(utility)
        if(self.load_funcs.get(utility, None)): del self.load_funcs[utility]
        if(self.unload_funcs.get(utility, None)): del self.unload_funcs[utility]

    def load_all_utilities(self):
        self.log("Loading all utilities")
        for method in self.load_funcs.values():
            method()
    
    def unload_all_utlities(self):
        self.log("Unloading all utilities")
        for method in self.unload_funcs.values():
            method()
    

    def load_utility_funcs(self, modulepacks):
        utils_to_load = set()
        for module_name, modulepack in modulepacks.items():
            utils_to_load.update(modulepack.utilities)

        if(not utils_to_load):
            self.log("No utilities to load")
            return
        else:
            self.log(f"Loading methods for utilities -> {utils_to_load}")
            _del = set()
            for utility in utils_to_load:
                path = os.path.join(self.utility_dir, f"{utility}.py")
                config_path = os.path.join(self.utility_dir, f"configs/{utility}.json")

                # self.log(f"Attempting to load '{utility}'")
                
                if(os.path.exists(config_path)):
                    with open(config_path, 'r') as f:
                        try:
                            config = json.load(f)
                            self.log(f"Config for {utility} was loaded")
                        except json.JSONDecodeError as err:
                            self.log(f"Config for {utility} was found but could not be decoded - {err}", level="warning")
                            config = {}
                else:
                    config = {}

                spec = importlib.util.spec_from_file_location("utility_handlers", path)
                module = importlib.util.module_from_spec(spec)

                def load_wrapper(utility_name, func, *args, **kwargs):
                    def inner_wrap():
                        # print(args, kwargs)
                        self.log(f"Loading utility {utility_name}")
                        try:
                            self.utilities[utility_name] = func(*args, **kwargs)
                        except Exception as e:
                            self.log(f"method failed - {e}", level="warning")
                            self.utilities[utility_name] = {}
                    return inner_wrap

                def unload_wrapper(utility_name, func, *args, **kwargs):
                    def inner_wrap():
                        self.log(f"Unloading utility {utility_name}")
                        try:
                            func(*args, **kwargs, **self.utilities.get(utility_name, {}))
                        except Exception as e:
                            self.log(f"method failed - {e}", level="warning")
                    return inner_wrap
                    
                try:
                    spec.loader.exec_module(module)
                    attrs = dir(module)
                    log = self.control.create_logger(f"{utility}")
                    self.utilities_loaded.add(utility)

                    if ("load" in attrs):
                        self.load_funcs[utility] = load_wrapper(utility, module.load, self, log.log, config)
                        self.log(f"Found load method for {utility}", level="info")
                    else:
                        self.utilities[utility] = {}

                    if ("unload" in attrs):
                        self.unload_funcs[utility] = unload_wrapper(utility, module.unload, self, log.log, config)
                        self.log(f"Found unload method for {utility}", level="info")


                except Exception as err:
                    self.log(f"Failed to load utility '{utility}' - {err}", level="warning")



class FullLoader:
    def __init__(self, control,  utility_dir, module_dir) -> None:
        self.control = control
        self.utility_dir = utility_dir
        self.module_dir = module_dir

        LoadingInfo.setup(control, utility_dir, module_dir)

        self.modules = None
        self.utilities = None

    def full_load(self):
        self.modules_l = _ModulesLoader()
        self.utilities_l = _UtilitiesLoader()

        self.modules_l.load_modulepacks()
        self.utilities_l.load_utility_funcs(self.modules_l.modulepacks)
        self.modules_l.filter_modulepacks(self.utilities_l)
        self.modules_l.load_inherits(self.utilities_l.utilities)
        self.modules_l.load_modules(self.utilities_l.utilities)

    async def call_unload_methods(self):
        for module in self.modules_l.modules.values():
            self.control.log(f"Unloading module {module.name}")
            await module.execute_unload_funcs()
        
        for utility in self.utilities_l.utilities.keys():
            f = self.utilities_l.unload_funcs.get(utility, None)
            if(f): f()



        