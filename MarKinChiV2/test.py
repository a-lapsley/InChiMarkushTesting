import os
from rdkit import Chem
from rdkit.Chem import Draw

structure_dir = os.path.join(os.getcwd(), "MarkInChIv2\\marvin")
filedir = os.path.join(structure_dir, "test1b.mol")

with open(filedir) as file:
    content = file.readlines()

new_content = ""
writing = True
for line in content:
    if line.find("BEGIN RGROUP") != -1:
        writing = False
    if writing:
        new_content += line
    if line.find("END RGROUP") != -1:
        writing = True

mol = Chem.MolFromMolBlock(new_content)
Draw.ShowMol(mol)
for atom in mol.GetAtoms():
    print(atom.GetPropNames())