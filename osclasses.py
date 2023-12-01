
import os
import json



class OS_object:
	def __init__(self) -> None:
		self.name: str = None
		self.parent: OS_object = None
		self.location_in_fs: str = None

	def resolve_relative_path(self):
		if(self.parent):
			return os.path.join(self.parent.resolve_relative_path(), self.name)
		else:
			return self.name
	
	def resolve_full_path(self):
		if(not self.location_in_fs):
			return os.path.join(self.parent.resolve_full_path(),  self.name)
		else:
			return self.location_in_fs
			
	@property
	def relative_path(self):
		return self.resolve_relative_path()

	@property
	def full_path(self):
		return self.resolve_full_path()

class File(OS_object):
	def __init__(self, name, parent=None) -> None:
		super().__init__()
		self.name = name
		self.parent = parent
		self.content = None
		self.type = ""


	def jsonLoad(self):
		with open(self.full_path, 'r') as f:
			d = json.load(f)
		self.type = "json"
		self.content = d
		return d 

	def jsonDump(self):
		with open(self.full_path, 'w') as f:
			json.dump(self.content, f)

class Directory(OS_object):
	def __init__(self, name, location_in_fs = "", parent=None) -> None:
		super().__init__()
		self.name = name
		self.parent = parent
		self.subdirectories = {}
		self.subfiles = {}
		self.location_in_fs = location_in_fs


	def add_file(self, file: str):
		self.subfiles[file] = File(file, parent=self)
		return self.subfiles[file]

	def resolve(self, path: list):
		curr = path[0]
		if(curr in self.subdirectories.keys()):
			if(len(path) > 1):
				return self.subdirectories[curr].resolve(path[1:])
			return self.subdirectories[curr]
		elif(curr in self.subfiles and len(path) == 1):
			return self.subfiles[curr]
		else:
			return None

class AdvancedDirectory(Directory):
	def __init__(self, name, location_in_fs="", parent=None) -> None:
		super().__init__(name, location_in_fs, parent)
		self.requirements = []
		self.load_content = None
		self.inherit = None

	@property
	def full_requirements(self):
		s = set(self.requirements)
		if(self.parent): s.update(self.parent.full_requirements)
		return s

	def add_directory(self, directory: str):	
		self.subdirectories[directory] = AdvancedDirectory(directory, parent=self)
		d = self.subdirectories[directory]
		return d

	def scan_directory(self):
		for file in os.listdir(self.full_path):
			fp = os.path.join(self.full_path, file)
			if(os.path.isfile(fp)):
				self.add_file(file)
			elif(os.path.isdir(fp)):
				d = self.add_directory(file)
				d.scan_directory()
			
		if("requirements.json" in self.subfiles.keys()):
			self.requirements = self.subfiles["requirements.json"].jsonLoad()
		
		if("load.json" in self.subfiles.keys()):
			self.load_content = self.subfiles["load.json"].jsonLoad()

		if("inherit.py" in self.subfiles.keys()):
			self.inherit = self.subfiles["inherit.py"]

	def get_children_modules(self):
		ret = []
		if(self.load_content):
			ret.append(self)

		for directory in self.subdirectories.values():
			ret.extend(directory.get_children_modules())
		return ret

	def get_inherits(self):
		ret = []
		if(self.inherit):
			ret.append(self.inherit)

		if(self.parent):
			ret.extend(self.parent.get_inherits())

		return ret

	def save_configs(self):
		for file in self.subfiles.values():
			if(file.type == "json"):
				file.jsonDump()
		# no need to log files were saved
		for directory in self.subdirectories.values():
			directory.save_configs()