import json
from molmass import Formula


with open("nutrients.json", "r") as f:
    data = json.load(f)


class Chemical():
    def __init__(self, name, molarity, molar_mass) -> None:
        self.name = name
        self.molarity = molarity
        self.molar_mass = molar_mass


print("calculating stock solution molarities...")
reagents = {}
nutrients = {}
for chemical_name, content in data["chemicals"].items():
    keys = content.keys()

    molar_mass = content["molar_mass"]
    
    if(not "molarity" in keys):
        # molarity is calcultes assuming grams of chemical is in reference to 1L of water, because the only situation where the user only knows the grams of the solute
        # is in theoretical scenarious, otherwise they should have procured the solution carefuly using molarity

        mass = content["mass"]
        moles = mass/molar_mass
        molarity = moles/1
    else:
        molarity = content["molarity"]

    obj = Chemical(chemical_name, molarity, molarity)
    reagents[chemical_name] = obj

    _per_ml = "{:.8f}".format(molarity/1000)
    print(f"{_per_ml} moles of {chemical_name} per ml of solution")

    nutes_released = content["release"]

    for pack in nutes_released:
        nute, n = pack
        if nute not in nutrients and nute in data["salts"]:
            mol = data["salts"][nute].split(" ")
            if(mol[-1] == "mm"):
                mol = float(mol[0]) * pow(10, -3)
            elif(mol[-1] == "um"):
                mol = float(mol[0]) * pow(10, -6)
            nutrients[nute] = {
                "reagents": [],
                "mol": mol
            }
        if nute in nutrients:
            nutrients[nute]["reagents"].append([obj, n])

print("calculating mass percent of reagents by given concentration of nutrients in 1L of nutrient solution...")
reagent_mol_calculated = {}

counter = 1
while True:
    d = []
    for nute, pack in nutrients.items():
        _reagents = pack["reagents"]
        req_mols = pack["mol"]
        if(len(_reagents) is not counter):
            continue
        b = 0
        not_calculated = None
        for pack in _reagents:
            reagent, n = pack
            if(reagent.name in reagent_mol_calculated):
                # print(nute, reagent.name, n)
                b += reagent_mol_calculated[reagent.name] * n
            elif not not_calculated:
                not_calculated = [reagent, n]
            else:
                raise Exception(f"Too many reagents of {nute}, {not_calculated[0].name} already is not calculated and need to caculate {reagent.name}")
        
        req_mols -= b
        if(not_calculated):
            reagent, n = not_calculated

            if(req_mols <= 0):
                print(b)
                raise Exception("wtf")

            # print("here")
            # print(req_mols/n)
            reagent_mol_calculated[reagent.name] = req_mols/n

        d.append(nute)

    for _d in d:
        del nutrients[_d]

    if(not nutrients):
        break

    counter += 1



total_mass = sum([reagents.get(name).molar_mass*x for name, x in reagent_mol_calculated.items()])
reagent_mass_p = {}

for reagent, mol in reagent_mol_calculated.items():
    reagent_mass_p[reagent] = (mol* reagents.get(reagent).molar_mass)/total_mass
    print("{}: {:.8f}%".format(reagent, reagent_mass_p[reagent]*100))


mass = 0.01666666665

print("for debug purposes calculating volume of stock solutions needed to create 1L nutrient solution with given concentrations")
for reagent, mol in reagent_mol_calculated.items():
    ml = mol/reagents[reagent].molarity * pow(10, 3)
    print("{} ml of {}".format(ml*2, reagent))



print("calculating needed volume of stock solutions in order to dose nutrients with dry mass of {}g".format(mass))

for reagent, obj in reagents.items():
    mol = ((reagent_mass_p[reagent]*mass)/obj.molar_mass)
    ml = 1/(obj.molarity/mol)

    print("{:.4f} ml of {}".format(ml, reagent))

