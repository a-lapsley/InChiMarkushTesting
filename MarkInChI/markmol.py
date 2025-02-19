import copy
import sys

from rdkit import Chem
from zz_convert import zz_convert
from label import Label

class MarkMol(object):

    """ This class is used for the conversion of a markush mol to a markush
        inchi."""

    def __init__(self, name=None):

        # Open the SDF/MOL file containing the Markush structure and read the contents
        # If MarkMol class was called with a specified file
        if name != None:
            file = open(name, "r")
            content = file.readlines()
            file.close()
        # If user should enter directory manually
        else:
            file_read = False
            while not file_read:
                try:
                    name = input("Enter the file name with the extension:")
                    file = open(name, "r")
                    content = file.readlines()
                    file.close()
                    file_read = True
                except:
                    print("File not found")

        # Initialize most of the global variables, set names for imported functions/classes
        self.help_label = Label() # Imported class for labeling atoms, finding their position given their label, etc.
        self.atom_symbols = {} # All atoms in the main block of the original SDF file {index in SDF file : atom symbol}
        self.list_of_atoms = {} # Lists of atoms {atom index in SDF file : list of symbols}
        self.main_dict_renumber = {} # For renumbering main block when some lines deleted {old number: new number}
        self.Rpositions = []  # Number of each Te atom (R group) in the original atom block
        self.Rsubstituents = [] # List of lists of substituents associated with each R group
        self.ctabs = []  # Number of each substituent after $RGP
        self.connections = [] # Number of the "connecting" atom in each substituent
        self.attachments = [] # List of lists of variable attachment points for each attachment
        self.XHn_groups = [] # Number of each XHn group (i.e. the atom representing it) in the original main block
        self.subst_order = [] # Order of R groups in the SDF file related to the R atoms in main block
        self.no_atoms = 0 # Number of atoms in the main block
        self.large_substituent = False # True if large variable attachment directly attached to the core structure

        # Create the new RDKIT compatible file
        content = self.convert(content)
        new_name = name.split(".")[0] + "_RDKIT.sdf"
        new_file = open(new_name, "w")
        new_file.writelines(content)
        new_file.close()

        # Get core structure and substituents from the RDKIT compatible file
        supply = Chem.SDMolSupplier(new_name)
        substituents = []
        for mol in supply:
            if mol is not None:
                substituents.append(mol)
        self.core_mol = copy.deepcopy(supply[0])

        # Get the substituents associated with each R group
        i = 1
        ctabs = self.ctabs
        while i < len(ctabs): # Creates list of lists of substituents, each inner list corresponding to one R group
            self.Rsubstituents.append(substituents[int(ctabs[i - 1]):int(ctabs[i])])
            i += 1
        if ctabs != [] and i == 1:
            # Adds the substituent if it is only one variable attachment
            self.Rsubstituents.append(substituents[int(ctabs[i - 1]):])

        # Split substituents into R groups and var attach directly on the bonds
        divide_subst = len(self.subst_order)
        R_subst = self.Rsubstituents[:divide_subst] # R substituents are at the beginning
        other_subst = self.Rsubstituents[divide_subst:] # Rest are variable attachments directly drawn on the structure

        # Create dictionary to order the R substituents correctly
        subst_dict = dict(zip(self.subst_order, R_subst))
        subst_dict = dict(sorted(subst_dict.items(), key=lambda item: item[0]))
        self.Rsubstituents = list(subst_dict.values()) + other_subst

        # Create the MarkInChI and print it
        print(self.produce_markinchi())

    def convert(self, content):

        #### This function converts a normal Markush SDF file to RDKIT compatible SDF file. Input: list. Output: list.

        # Adjust the content of the file by deleting, modifying and adding lines
        # Extract useful information into variables
        new_content = self.replaceR(content)
        new_content = self.var_attach(new_content)
        new_content = self.delete(new_content)
        new_content = self.add(new_content)

        # If large variable attachment, adjust the main block in the RDKIT compatible file
        if self.large_substituent == True:
            new_content = self.main_block(new_content)

        # If there are empty atoms present initially, the main block will be renumbered
        # (because they are deleted and sometimes line after them remain in the file)
        if self.renumber == True and self.large_substituent == False:
            new_content = self.renumber_main_block(new_content, self.save_atoms_lines)

        # Create M ISO line
        new_content = self.label(new_content)

        return copy.deepcopy(new_content)

    def replaceR(self, content):

        #### This function:
        # 1. Replaces R groups 'R#' in the file by Te atoms 'Te'
        # 2. Gets list of atoms indices
        # 3. Get indices of each R group (e.g. R1 is atom 9, etc.)
        # 4. Get the point of connections of R group substituents
        # 5. Delete the number after "$RGP" line
        # 6. Get the number of substituents per R group (using "ctab")

        ctab = 0 # Counts through the substituents
        new_content = [] # Will contain the new file content
        replace = True
        list_of_atoms = {} # Will contain lists of atoms associated with a position in the molecule

        for line in content:
            if replace:
                new_line = line.replace("R#", "Te")
            else:
                # Delete after $RGP
                new_line = " "
                replace = True
                self.ctabs.append(ctab) # Save the index of the last substituent associated with a R group
            if line.find("$END CTAB") != -1:
                ctab += 1 #
            if line.find("$RGP") != -1:
                replace = False # Will save ctab in the next cycle, because $RGP indicates start of new R group
            if line.find("M  ALS") != -1:
                # Save lists of atoms
                index = line.split()[2]
                atom_list = line.split()[5:]
                list_of_atoms[index] = atom_list
            if line.find("M  RGP") != -1: # "M  RGP number-of-R-groups R-position order-in-the-file R-position order-in-the-file"
                # Get positions of R groups in the molecule and in which order are listed in the file
                parts = line.split("RGP")[1].split()
                for i in range(1, len(parts), 2):
                    self.Rpositions.append(parts[i]) # R positions
                for i in range(2, len(parts), 2):
                    self.subst_order.append(parts[i]) # Substituent order
            if line.find("M  APO") != -1:
                # Find points of connections for each substituent
                connection = line.split()[3]

                self.connections.append(connection)
            new_content.append(new_line)

        self.list_of_atoms = list_of_atoms

        # Save the index of the last substituent of the last group in case more will be added due to variable attachments
        # Only if ctab!=0, otherwise it would add the core structure as one of the substituents
        if ctab != 0:
            self.ctabs.append(ctab)

        return copy.deepcopy(new_content)

    def delete(self, content):

        #### This function deletes all lines that are:
        # 1. empty space lines (a).
        # 2. start with '$' signs (a).
        # 3. all that start "M" that are not "M END" (b).
        # 4. 'F' atom list line that comes after the bonds' block (c). (F can be an atom, so two conditions needed)

        new_content = [] # Will contain the new file content

        # Goes through the content and appends only the lines that don't contain any of the above
        for line in content:
            # Conditions a & b & c (see above)
            a = (not line.isspace()) and line[0] != "$"
            b = not (line[0] == "M" and (line.find("END") == -1))
            c = not ((line.find("F") != -1) and (((len(line)-15)) % 4 == 0))
            if a and b and c:
                new_content.append(line)

        return copy.deepcopy(new_content)

    def add(self, content):

        ##### This function adds 3 empty lines before each substituent and 4 $ signs (to make its own mol)
        # Labels connection points on substituents - self.connections contains which of these atoms should be labelled

        content[0] = "\n\n\n" # Puts 3 empty lines at the beginning of the file
        new_content = [] # Will contain the new file content
        add_line1 = "$$$$" # Will be added after each substituent
        add_line2 = "\n\n\n\n" # Will be added after each substituent
        i = 0 # Counting through substituents
        count = 1 # Counting through atom lines within substituents (and also main block, but that is irrelevant)
        atom_line = False

        # Adds lines to new_content, modifying them if conditions are fulfilled
        for line in content:
            # Label the 'connection' atom on the substituent with isotopic label 8.
            if i > len(self.connections): # Happens if not all connections are in self.connections (M APO missing)
                raise Exception("Probably M APO missing at one of the substituents in the molfile - check. If missing, open the file in MarvinSketch and add the connection again.")
            if i > 0 and count == int(self.connections[i-1]): # Labels which atom of a substituent is the connection
                # Must be mol V2000
                if atom_line:
                    if len(line) > 68: # If still in atom block
                        new_line = line[:35]+"8"+line[36:] # Labels this atom with "8"
                        new_content.append(new_line)
                    else: # If atom block is over
                        atom_line = False
                        new_content.append(line)
                else:
                    new_content.append(line)
            else:
                new_content.append(line)
            if line[0] == "M" and line.find("END") != -1: # Will be true after main block and each substituent
                count = 1 # Reset count to 1
                i += 1 # Counts through substituents
                # Adding spaces and "$$$$" after each substituent and also main block
                new_content.append(add_line1)
                new_content.append(add_line2)
            if line.find(".") != -1:
                count += 1 # Counting through (not only) the atom lines, since they contain decimal numbers
            if line.find("999 V2000") != -1:
                atom_line = True # Atom block follows

        return copy.deepcopy(new_content)

    def var_attach(self, content):

        #### Variable attachments. Does the following:
        # finds the indices of the 'empty' atoms
        # finds the attachments for each bond, store that information, and links it to the right atom
        # finds the indices of the atoms bound to the 'empty' atoms
        # counts the number of atom lines
        # Second part starts building a new file and decides whether there is a large attachment

        i = 0 # Indexes the atom lines
        self.empty_inds = []  # Gets indices of empty atoms
        self.save_atoms_lines = [] # Saves all atom_lines
        attachments = [] # Stores variable attachments
        bonds = []  # Stores the block of bonds
        real_bonds = {} # Stores bonds between empty atoms and atoms attached to them (real atachment atoms)
        atom_line = False
        bond_line = False

        # Goes through the file line by line and saves information
        for line in content:
            if atom_line:
                i += 1
                # Get atom symbols in the main block (core)
                if len(line) > 68: # True for atom lines
                    # If True, save the atom line
                    self.save_atoms_lines.append(line)
                    if len(line[31:34].split()) > 0:
                        # Get the atom symbol from each atom line when is non-empty
                        self.atom_symbols[i] = line[31:34].split()[0]
                    else:
                        # When is empty, label it "empty" atom
                        self.atom_symbols[i] = "empty"
                    if line[31] == " ":
                        # When is empty, store the empty atom index in self.empty_inds
                        self.empty_inds.append(str(i))
                else:
                    # Atom block is finished and bond block begins
                    atom_line = False
                    bond_line = True
            if bond_line:
                # Store bonds
                if line[0] != "M" and "F" not in line:
                    # If True, it is bond line
                    bonds.append(line)
                else:
                    # If False, bond block is finished
                    bond_line = False
            if line.find("M  SAL") != -1:
                # Get variable attachment points
                attachments.append(line.split()[4:])
            if line[0] == "M" and line.find("END") != -1:
                # End for loop after core is finished - went through the whole main block
                break
            if line.find("999 V2000") != -1:
                # If True, next line will be atom line
                atom_line = True

        # Atoms will be renumbered if there are any 'empty' atoms
        self.renumber = False
        if 'empty' in self.atom_symbols.values():
            self.renumber = True

        # Store the bond between the empty atom and the real attachment atom as dictionary and also a list
        list_real_bonds = [] # Will store empty bond lines
        for b in bonds:
            for ind in self.empty_inds:
                if b.split()[0] == ind:
                    real_bonds[ind] = b.split()[1]
                    list_real_bonds.append(b)
                elif b.split()[1] == ind:
                    real_bonds[ind] = b.split()[0]
                    list_real_bonds.append(b)

        # Modify the content of the file to create a new SDF file
        # Substract the number of 'empty atoms'*2 from the number of atoms AND the number of bonds on the top
        # Delete 'empty atoms' and atoms that are bound to them (variable-bond atoms) from the atom block,
        # and corresponding bonds from the bond block

        attach_ids = {}  # Dictionary of real atoms - number:atom.
        no = len(self.empty_inds) # Number of empty atoms
        new_content = [] # Will be content of new file
        atom_line = False
        count = 0 # Number of an atom line
        file_count = 0 # Number of line in a file
        no_atoms = 0 # Number of atoms in the main block

        # List of empty atoms and real atoms bonded to them
        to_be_deleted = list(real_bonds.values())+list(real_bonds.keys())

        for line in content:
            if atom_line: # If going through the atom lines
                count += 1
                if len(line) > 68: # If it is still an atom line or if the atom block is already over
                    delete_line = False
                    list_count = 0 # To count through to_be_deleted
                    for d in to_be_deleted:
                        if str(count) == d: # If the atom line contains empty or real atom (and hence should be deleted)
                            delete_line = True
                            # Get all real atoms
                            if 2*list_count < len(to_be_deleted): # Real atoms are in the first half of to_be_deleted
                                attach_ids[count] = line[31:34].split()[0] # Add real atom index to attach_ids
                        list_count += 1

                    if not delete_line: # If the line shouldn't be deleted
                        new_line = line
                        for at in self.list_of_atoms.keys():
                            # Replace L in the atom line by the first atom in the list of atoms associated with it
                            if count == int(at):
                                sym = self.list_of_atoms[at][0]
                                nn = len(sym)-1
                                new_line = line.replace(("L"+nn*" "), sym)
                                self.atom_symbols[count] = sym # Replace "L" in the self.atom_symbols also by this atom
                        new_content.append(new_line) # Add the line to the new file (new_content)
                else:
                    # Atom block is over
                    atom_line = False
                    new_content.append(line) # The first bond line is appended
            else:
                if line.find("999 V2000") != -1:
                    atom_line = True # Atom lines follow
                    # Adjust top core mol statement (e.g. no of atoms, etc.)
                    # Needs to be created even if var_attach transforms it later (it works with the already created line)
                    no_atoms = int(line.split()[0])-2*no
                    no_bonds = int(line.split()[1])-no
                    atom_part = (3 - len(str(no_atoms)))*" "+str(no_atoms)
                    bond_part = (3 - len(str(no_bonds)))*" "+str(no_bonds)
                    new_line = atom_part+bond_part+"  "+line[8:]
                    new_content.append(new_line)
                else:
                    if len(line) == 22: # True for bond lines
                        delete_line = False
                        for dd in to_be_deleted:
                            # All bonds containing empty and real atoms will not be included in the new file
                            # Checking if the atoms are contained in the bonds
                            cn1 = line.split()[0] == dd
                            cn2 = line.split()[1] == dd
                            if cn1 or cn2:
                                delete_line = True
                        if not delete_line:
                            new_content.append(line) # Adding bond lines to the new file
                    else:
                        # These lines contain more information, it will be extracted and the lines will be deleted later
                        new_content.append(line)
            if line.find ("M  END") != -1:
                # When the core mol finishes append the rest of the mol file and stop exit the for loop
                new_content += content[file_count+1:]
                break
            file_count += 1

        for sub_attach in attachments:
            sub_attach.sort()

        print(f"empty_inds: {self.empty_inds}")
        print(f"attachments: {attachments}")
        print(f"real_bonds: {real_bonds}")
        print(f"attach_ids: {attach_ids}")
        print(f"atom_symbols: {self.atom_symbols}")

        # Making some of the variables global
        self.attachments = attachments
        self.attach_ids = attach_ids
        self.no_atoms = no_atoms # Will be used later to generate M ISO line
        self.content = content
        self.bonds = bonds

        # Check if the variable attachment is larger than one XHn group
        bonds_adjust = set(list.copy(self.bonds)) # Copy of list of all bonds (needs to be a copy)
        bonds_adjust -= set(list_real_bonds) # Remove all empty-real atom bonds
        for real_atom in attach_ids:
            # If at least one real atom has another one attached, self.large_substituent = True
            if str(real_atom) in str(bonds_adjust):
                self.large_substituent = True
                break

        # Will run the self.large_var_attach function if there is larger var attach than XHn
        if self.large_substituent == True:
            new_content = self.large_var_attach(new_content)

        return copy.deepcopy(new_content)

    def label_attachments(self, content):

        #### Labels all attachments (5 + rank in mol file)
        # TODO: This function is not used by the code and probably won't be needed.
        #  The issue is dealt with in add and build_blocks. - Remove or use.

        # Add the variable attachments in each sublist to all_attachments
        all_attachments = [] # Will contain all the attachments in one list
        for att in self.attachments: all_attachments += att

        # Adds a label in the atom line probably to where it should be attached
        new_content = []
        file_count = 0
        atom_count = 0
        atom_line = False
        for line in content:
            if atom_line:
                if len(line) > 68:
                    atom_count += 1
                    new_line = line
                    for attach in all_attachments:
                        if str(atom_count) == attach:
                            sub_label = str(int(attach)+5)
                            label = sub_label+(3-len(sub_label))*" "
                            new_line = line[:35]+label+line[38:]
                    new_content.append(new_line)
                else:
                    # atom_line = False
                    new_content += content[file_count:]
                    break
            else:
                new_content.append(line)
            if line.find("999 V2000") != -1:
                atom_line = True
            file_count += 1

        return copy.deepcopy(new_content)

    def label(self, content):

        #### Creates the M ISO line in the newly created SDF file

        # Add the variable attachments in each sublist to attach_list
        attach_list = []  # Will contain all the attachments in one list
        for l in self.attachments:
            attach_list += l

        # All atoms that need labelling will be in atoms
        # (R - R substituents, L - lists of atoms, attach_list - variable attachments, self.XHn_group - var attach with XHn groups only)
        R = self.Rpositions
        L = list(self.list_of_atoms.keys())
        atoms = list(set(R + L + list(self.attach_ids.keys()) + attach_list + self.XHn_groups))

        # Reducing atoms to list of unique integers
        all_atoms = [] # Will contain all the atoms that need labelling only once and as integers
        for atom in atoms:
            if int(atom) not in all_atoms:
                all_atoms.append(int(atom))
        all_atoms.sort()
        print(f"all_atoms: {all_atoms}")

        print(f"no_atoms: {self.no_atoms}") # Total number of atoms

        i = 0  # Used for locating atoms in all_atoms
        if self.main_dict_renumber != {} and self.main_dict_renumber.values() != self.main_dict_renumber.keys():
            # If needed to renumber the atoms because they have different indices in the old and new SDF files
            # Will run if the dictionary is non-empty and has different keys from values
            delete_atom = [] # Will contain atoms to delete (not in the new SDF file - mainly connected to empty atoms)
            for at in all_atoms:
                if str(at) in list(self.main_dict_renumber.keys()):
                    # Renumber atoms in all_atoms to correspond to the new numbering
                    new_at = int(self.main_dict_renumber[str(at)])
                    all_atoms[i] = new_at
                elif str(at) not in list(self.main_dict_renumber.keys()) and at > self.no_atoms:
                    # Add the atoms that are not in the dictionary to delete_atom list
                    delete_atom.append(at)
                i += 1
            all_atoms = sorted(list(set(all_atoms) - set(delete_atom))) # Remove atoms that shouldn't be labeled
            new_atom_symbols = copy.deepcopy(self.renumber_dict()) # Get updated version of self.atom_symbols
        else:
            for at in all_atoms:
                if int(at) > self.no_atoms:
                    all_atoms = all_atoms[:i]
                    break
                i += 1
            new_atom_symbols = self.atom_symbols # No numbers were changed in all_atoms, so this doesn't need a change

        print(f"all_atoms: {all_atoms}")
        no_labeled = str(len(all_atoms)) # Number of labeled atoms to add into M ISO line
        iso_line = f"M  ISO"
        iso_line += (3-len(no_labeled))*" "+no_labeled

        # Creates labels for connecting atoms to be put into M ISO line
        for atom in all_atoms:
            atom_sym = new_atom_symbols[atom] # Get the symbol of atom to be labeled
            table = Chem.GetPeriodicTable()
            atomic_mass = int(table.GetMostCommonIsotopeMass(atom_sym)) # Get its atomic mass from the periodic table
            # TODO: Find a more elegant solution - F has atomic mass 19, RDKIT gives 18 (problem of RDKIT).
            if atom_sym == 'F':
                print("F in the molecule, RDKIT gives most common isotope mass as 18, but is 19. Inconsistent with the InChI algorithm.")
                atomic_mass = 19
            label = str(atomic_mass + 5 + atom) # Generates a label

            # Creates M ISO line (M  ISO  no_labeled   atom   label   atom   label   atom   label),
            # atoms are represented by indices
            iso_line += (4-len(str(atom)))*" "+str(atom)+(4-len(label))*" "+label

        iso_line += "\n"

        # Insert the M ISO line right before the first M END line
        for line in content:
            if line.find("M  END") != -1:
                iso_index = content.index(line)
                content.insert(iso_index, iso_line)
                break

        return copy.deepcopy(content)

    def relabel_core(self, inchi):

        #### Deletes the isotope layer (/i) from the InChI - that accounts for connectivity

        index = inchi.find("/i") # Find where is the isotope layer (-1 if is not there)

        if index != -1: # If the index layer is present
            suf = ""
            if inchi[index+2:].find("/") != -1: # If the InChI continues after the /i layer
                # suf will contain everything after the /i layer, starting with "/"
                suf = "/"+"/".join(inchi[index+2:].split("/")[1:])
            new_inchi = inchi[:index]+suf # Add together the parts before and after the isotope layer
        else:
            new_inchi = inchi # If the isotope layer is not there

        return new_inchi

    def relabel_sub(self, mol):

        #### Returns InChI for substituents with more than 1 main atom and SMILES otherwise
        # mol - substituent in mol format

        sub_inchi = ""

        for atom in mol.GetAtoms():

            if atom.GetIsotope() > 0: # Only non-zero when the isotope was explicitly set, i.e. only for the connection
                idx = atom.GetIdx() # Get index of the connecting atom
                rwmol = Chem.RWMol(mol) # RWMol is Mol that can be modified
                rwmol.GetAtoms()[idx].SetIsotope(0) # Set the isotope of the connecting atom back to zero

                if mol.GetNumAtoms() > 1: # If number of atoms in the substituent is bigger than one
                    # Add Te atom by a single bond to the connecting atom to create a valid molecule and obtain InChI
                    rwmol.AddAtom(Chem.Atom("Te"))
                    single = Chem.rdchem.BondType.SINGLE
                    rwmol.AddBond(idx, mol.GetNumAtoms(), order = single)
                    sub_inchi = Chem.MolToInchi(rwmol)
                    # Check sub_inchi is valid

                    if Chem.rdinchi.InchiToMol(sub_inchi) == None:
                        raise RuntimeError("Sub_inchi invalid")

                    # Get only the part of InChI without "InChI=1S/"
                    sub_inchi = "/".join(sub_inchi.split("/")[1:])

                else:

                    # If XHn group, get SMILES instead (will be a single letter - i.e. C, N, O,...)
                    sub_inchi = Chem.MolToSmiles(rwmol)

        return sub_inchi

    def large_var_attach(self, new_content):

        #### Transforms variable attachments to R groups if a substituent is larger than XHn (XHn = CH3, NH2, OH...)

        bonds = self.bonds # Contains all bonds from the original file
        atom_blocks = [] # Will contain all atom lines associated with the substituents (to delete them from main block)
        self.subblock = [] # Will contain all new subblocks created for large_var_attach

        # For each empty atom check to what it is connected (self.empty_inds contains all the empty atoms)
        # Then find all the connections within the attachments
        for index in self.empty_inds:
            group_atoms = [] # Will contain all the atoms in the substituent
            empty_bonds = [] # Will contain all the bonds to empty atoms, so they can be later deleted

            # Finding atoms bonded to empty atoms (and the bonds as well) and adding them to group_atoms
            for b in bonds:
                # If the index of the empty atom is in the bond line, it finds the atom to which it is connected
                # Usually the lower index atoms are first in the bond line, but not always true - must check both
                if index == b.split()[0]:
                    other_atom = b.split()[1]
                    group_atoms.append(other_atom)
                    empty_bonds.append(b)
                    break # Since only one connection to empty atom, no need to continue with the loop
                elif index == b.split()[1]:
                    other_atom = b.split()[0]
                    group_atoms.append(other_atom)
                    empty_bonds.append(b)
                    break
                else:
                    # If something goes wrong, check the value of other_atom
                    other_atom = str(-1)

            # Delete all bonds to empty atoms from the list of all the bonds
            for s in empty_bonds:
                if s in bonds:
                    bonds.pop(bonds.index(s))

            save_bonds = [] # Will contain all the bonds within the substituent
            bonded_atoms = [] #

            # Finding all bonds within the attachment
            # "other_atom in str(bonds)" - if not all connections to a particular atom from the substituent
            # have not been saved and removed from the list of all the bonds
            # "bonded_atoms != []" - if we have not tried searching the connections to all atoms
            # that we know are in the substituent (usually is true and the other isn't at the end of longer branches)
            # Both of these conditions need to be met to be sure that we have gathered all atoms from the substituent
            while other_atom in str(bonds) or bonded_atoms != []:

                if other_atom not in str(bonds): # Easy way to check whether it is in any of the bonds
                    # If there are no connections to the atom, remove it from bonded_atoms
                    # and choose different one from bonded_atoms
                    # And then skip the rest of the commands in this loop cycle
                    other_atom = bonded_atoms[0]
                    bonded_atoms.pop(0)
                    continue

                new_save_bonds = [] # Will contain all the new bonds from this other_atom

                for b in bonds:
                    # Find all atoms to which it is connected by searching the bonds and add them all to bonded_atoms
                    # If the new atoms are not in group_atoms yet, add them there (can be in several bonds)
                    # Add these bonds to new_save_bonds
                    if b.split()[0] == other_atom:
                        bonded = b.split()[1]
                        if bonded not in group_atoms:
                            bonded_atoms.append(bonded)
                            group_atoms.append(bonded)
                        new_save_bonds.append(b)
                    elif b.split()[1] == other_atom:
                        bonded = b.split()[0]
                        if bonded not in group_atoms:
                            bonded_atoms.append(bonded)
                            group_atoms.append(bonded)
                        new_save_bonds.append(b)

                # Remove all the bonds connected to other_atom from the list of all bonds
                # (at the end no bonds related to large_var_attach should stay in the main block)
                for s in new_save_bonds:
                    if s in bonds:
                        bonds.pop(bonds.index(s))

                save_bonds += new_save_bonds # Add the new bonds to all bonds in the substituent
                other_atom = bonded_atoms[0] # Pick new atom to run the loop with
                bonded_atoms.pop(0) # Remove this atom from bonded_atoms

            no_of_atoms = len(group_atoms) # Get the number of atoms within the substituent

            if no_of_atoms == 1: # If only one atom - it is a XHn group, skip the rest of the cycle
                self.XHn_groups.append(str(int(index) + 1))
                continue

            no_of_bonds = len(save_bonds) # Get the number of bonds within the substituent

            # Deduct the number of atoms in the substituent -1 from the total number of atoms in the main block
            # (-1 since two were already deducted for each empty atom, so not to do it twice
            # - also the reason why we don't have to deduct them for XHn groups anymore)
            self.no_atoms -= no_of_atoms - 1

            # Putting together the coordinate line block of the attachment
            # - add atom lines associated with each atom to atom_subblock
            atom_subblock = []
            for atom in group_atoms:
                atom_subblock.append(self.save_atoms_lines[int(atom)-1])

            atom_blocks += atom_subblock

            # Create dictionary relating old and new atom numbers
            new_numbers = list(range(1, len(group_atoms) + 1, 1))
            block_dict = dict(zip(group_atoms, new_numbers))

            # To keep the number of characters that will be replaced equal (if different numbers of digits)
            for key in block_dict.keys():
                while len(key) > len(str(block_dict[key])):
                    block_dict[key] = " " + str(block_dict[key])

            # Replace the old numbers in the bonds by new
            for b in save_bonds:
                l = save_bonds.index(b)
                for key in block_dict:
                    b = b.replace(key, str(block_dict[key])) # Replace them in the line
                save_bonds[l] = b # Update the line in the list

            # Add these var attachment substituents' indices into self.ctabs
            if self.ctabs != []:
                self.ctabs.append(1 + self.ctabs[-1]) # Since only one substituent each, append number by 1 larger to ctabs
            else:
                self.ctabs.append(1) # If no R groups - only directly attached var attachments, self.ctabs initially empty

            # Add a new subblock related to this subsittuent to the whole block of subblocks
            # This new subblock will be built from collected data in this function
            self.subblock += self.build_blocks(new_content, atom_subblock, save_bonds, no_of_atoms, no_of_bonds)

        # Delete all the substituent lines from the main block
        for line in atom_blocks:
            if line in new_content:
                new_content.pop(new_content.index(line))

        # Adjustments for case of both R and XHn variable attachment, (it doesn't create a subblock for XHn),
        # but still needs to be treated as separate variable attachment
        print(f"XHn_groups: {self.XHn_groups}")
        attach_ids_keys = [str(x) for x in self.attach_ids.keys()]

        # Removes XHn groups from attach_ids_keys
        for group in self.XHn_groups:
            if group in attach_ids_keys:
                attach_ids_keys.remove(group)

        # Creates dictionary of Te connections for large_var_attach (not XHn groups)
        # and updates self.attach_ids (replacing the atom by Te - the atom is separately in the substituent)
        self.attach_Te = {int(x): 'Te' for x in attach_ids_keys}
        self.attach_ids.update(self.attach_Te)

        # Adds Rpositions for large_var_attach to the already existing ones
        if self.Rpositions == []:
            self.Rpositions = attach_ids_keys
        else:
            self.Rpositions += attach_ids_keys

        # Updates the atom symbols by replacing connecting atoms of large_var_attach by Te
        for num in self.attach_Te.keys():
            self.atom_symbols[num] = 'Te'

        return copy.deepcopy(new_content)

    def build_blocks(self, new_content, atom_subblock, save_bonds, no_of_atoms, no_of_bonds):

        ####  Build subblocks for attachments

        # atom_subblock - all the atom lines associated with the attachment
        # save_bonds - all the bond lines associated with the attachment
        # no_of_atoms, no_of_bonds - total number of atoms and bonds in this subblock
        new_subblock = [] # List containing all the elements needed to create a new subblock
        init_index = 0  # Will be index of the initial line

        new_subblock.append("\n\n\n\n")

        # Finding index of the V2000 line (initial line) and then finding this line in new_content
        for line in new_content:
            if "V2000" in line:
                init_index = new_content.index(line)
                break
        first_line = new_content[init_index]

        # Creating the V2000 line for the subblocks
        atom_part = (3 - len(str(no_of_atoms))) * " " + str(no_of_atoms)
        bond_part = (3 - len(str(no_of_bonds))) * " " + str(no_of_bonds)
        new_line = atom_part + bond_part + "  0" + first_line[9:]
        new_subblock.append(new_line)

        # Creating lines indicating end of the subblock
        end_line1 = "M  END \n"
        end_line2 = "$$$$"

        # Taking the first atom line of the subblock and placing "8" instead of the first 0,
        # to indicate by which atom it is connected
        # (will be always the first one for these newly created subblocks because of the way they are created)
        sub_attach = atom_subblock.pop(0)
        attach_line = sub_attach[:35] + "8" + sub_attach[36:]

        # Attaching all the lines in the appropriate order
        # (V2000, first atom line, rest of atom subblock, bond subblock, end lines)
        new_subblock.append(attach_line)
        new_subblock = new_subblock + atom_subblock + save_bonds
        new_subblock.append(end_line1)
        new_subblock.append(end_line2)

        return copy.deepcopy(new_subblock)

    def main_block(self, new_content):

        #### Adjust the main block of the molecule just before the file is used
        # (deleting problematic lines, adjusting the initial line)
        # Translate the bonds so that they correspond to the current order of the atoms

        # All bond lines that are associated with removed atoms (are not in self.bonds)
        # are added to extre_lines and then removed
        extra_lines = [] # Will contain all unnecessary lines
        for line in new_content:
            if "M  END" in line:
                break
            if len(line) == 22:
                if line not in self.bonds:
                    extra_lines.append(line)
        # Removes all the unnecessary line from new_content
        for line in extra_lines:
            new_content.remove(line)

        # Getting the final element ('\n\n\n\n', i.e. 4 empty lines) in new_content while removing it
        # - will be added again after all the substituent subblocks are added
        end_line = new_content.pop(-1)

        # Using function renumber_main_block to replace old atom numbers in the bond lines for new
        # self.save_atoms_lines contains all the atom lines that were in the initial file
        self.renumber_main_block(new_content, self.save_atoms_lines)

        # Adding the whole block of substituents (self.subblock) and the end_line to new_content
        new_content = new_content + self.subblock
        new_content.append(end_line)

        # Initializing variables
        no_main_atoms = 0 # For counting atoms
        no_main_bonds = 0 # For counting bonds
        init_line = "" # Will be replaced by the actual initial line
        index_init = 0 # Will be the index of the initial line
        delete_lines = [] # Will contain all bond lines that need to be deleted because they are between the same atom

        # Removing line containing the version of MarvinSketch with which it the file was created
        # in case it wasn't removed before
        for line in new_content:
            if "Mrv" in line:
                new_content.remove(line)
                break

        for line in new_content:
            if "V2000" in line:
                # Finding the index of the V2000 of the main block to replace it with updated numbers of atoms and bonds
                init_line = copy.deepcopy(line)
                index_init = new_content.index(line)
            if len(line) > 68:
                # Counting atom lines (i.e. counting atoms)
                no_main_atoms += 1
            if len(line) == 22:
                if line.split()[0] == line.split()[1]:
                    # Preparing to delete all bond lines containing connections of the same atoms
                    # in case they weren't deleted (should have been deleted, but just to be safe)
                    delete_lines.append(line)
                else:
                    # Counting bond lines (i.e. counting bonds)
                    no_main_bonds +=1
            if "M  END" in line:
                # Ending the loop when "M  END" is reached to ensure only main block is involved
                break

        # Delete all lines that were identified previously to contain bonds between the same atoms
        for line in delete_lines:
            if line in new_content:
                new_content.remove(line)

        # Creating the initial line if variable attachment present in the molecule
        # with the updated numbers of atoms and bonds
        atom_part = (3 - len(str(no_main_atoms))) * " " + str(no_main_atoms)
        bond_part = (3 - len(str(no_main_bonds))) * " " + str(no_main_bonds)
        new_init_line = atom_part + bond_part + "  " + init_line[8:]
        new_content[index_init] = new_init_line

        return copy.deepcopy(new_content)

    def renumber_main_block(self, new_content, main_block_init):

        #### Replaces all old atom numbers in the bond lines with new ones in the final version of the file

        # main_block_init contains all the atom lines that were in the initial file
        main_dict_keys = [] # Will contain numbers of lines in the initial file that are also in the final one
        main_block_fin = [] # Will contain all atom lines that are in the final version of the SDF file
        L_lines = [] # Will contain coordinates of all atoms from atom lines containing "L" in the initial file

        # All atom lines are added to main_block_fin
        for line in new_content:
            if len(line) > 68 and 'M' not in line:
                main_block_fin.append(line)

        # Coordinates of the L atoms are added to L_lines
        # Need to treat them separately, because in the final file, "L" is replaced by one of the atoms
        # and the lines are not identical to the ones in the initial file
        if " L " in str(main_block_init):
            for line in main_block_init:
                if line[31] == "L":
                    L_lines.append(line.split()[0])
                    L_lines.append(line.split()[1])

        # Comparing atom lines in the initial and final version of the file
        # and adding the initial line indices into a list (main_dict_keys)
        for line in main_block_fin:
            if line in main_block_init:
                # For lines not containing "L"
                number_init = str(main_block_init.index(line) + 1)
                main_dict_keys.append(number_init)
                continue
            if line.split()[0] in L_lines:
                # For lines containing "L" - first replacing the atom symbol with "L" and then comparing it
                line_symbol = line[31:35]
                line = line.replace(line_symbol, "L   ")
                number_init = str(main_block_init.index(line) + 1)
                main_dict_keys.append(number_init)

        # Creating dictionary and reverse dictionary for old and new atom numbering
        main_dict_values = list(range(1, len(main_dict_keys) + 1, 1))
        main_dict_values = [str(x) for x in main_dict_values]

        self.main_dict_renumber = dict(zip(main_dict_keys, main_dict_values)) # Converting initial to final

        # Adding spaces to values with different number of digits
        # to make sure same number of characters will be replaced in the file

        for key in self.main_dict_renumber.keys():
            while len(key) > len(self.main_dict_renumber[key]):
                self.main_dict_renumber[key] = " " + self.main_dict_renumber[key]

        # Converting final to initial
        self.main_dict_reverse_renumber = dict(zip(self.main_dict_renumber.values(), self.main_dict_renumber.keys()))

        # Using the dictionary to replace all the old numbers with new in the bond lines of the new SDF file
        for line in new_content:
            if len(line) == 22:
                l = new_content.index(line)
                for key in self.main_dict_renumber.keys():
                    line = line.replace(key, self.main_dict_renumber[key])
                new_content[l] = line

        return copy.deepcopy(new_content)

    def renumber_dict(self):

        #### Changing self.atom_symbols - removing empty atoms

        atom_values = [] # Will be list of non-empty atoms
        items = self.atom_symbols.items()

        # Creates list of all non-empty atoms (atom_values) as integers
        for item in items:
            if item[1] != "empty":
                atom_values.append(item[1])

        # Creates new dictionary like self.atom_symbols, but with non-empty atoms only
        atom_keys = list(range(1, len(atom_values) + 1, 1))
        new_atom_symbols = dict(zip(atom_keys, atom_values))

        return new_atom_symbols

    def sort_var_attach(self, is_duplicate, one_total, num_var, duplicate_parts, list_var_parts, var_part, substituents):

        if is_duplicate:
            # If the attachments are not unique and need to be sorted alphabetically with others first,
            # they are saved in a list of all these duplicates
            duplicate_parts.append(substituents)
        elif one_total or list_var_parts != []:
            # If same sum of attachments as other substituent,
            # creating the string for this substituent and saving it
            # into a list of these with the same total to be sorted before creating MarkInChI
            one_part = num_var
            for sub in substituents:
                one_part += sub + "!"
            one_part = one_part[:-1]
            list_var_parts.append(one_part)
        else:
            # If no need to sort because is unique and has unique total, directly add to the var_part
            var_part += num_var
            for sub in substituents:
                var_part += sub + "!"
            var_part = var_part[:-1]

        return duplicate_parts, list_var_parts, var_part

    def produce_markinchi_Rgroups(self, core_inchi, zz):

        #### Produces part of MarkInChI associated with R groups (attached to one atom, not variable attachments)

        # Initializing variables
        order = [] # Atoms where Te/Zz indicates R group is attached on the main skeleton
        replace_order = {} # All the lists of atoms
        index = core_inchi.find("/i") # Finds index part in core_inchi
        label_part = "" # Encoding atoms to which something is attached
        canonical_dict = {} # Dictionary of mol_label : inchi_label (taken from label_part "value"+"key")

        # Taking the label part (that indicates atoms to which something is attached) from core_inchi
        if index != -1:
            indexf = core_inchi[index + 2:].find("/")
            if indexf != -1:
                label_part = core_inchi[index + 2:index + 2 + indexf]
            else:
                label_part = core_inchi[index + 2:]

        # Finding inchi labels of atoms with attachments from label_part
        for part in label_part.split(","):
            canonical_dict[part.split("+")[1]] = part.split("+")[0]
            rank = part.split("+")[0]
            formula = core_inchi.split("/")[1]
            # Finding symbol of atom given by the rank from the molecular formula
            symbol = self.help_label.find_atom(rank, formula)

            if symbol == "Te":
                # Creating list of atoms with R group attachments (not variable attachments)
                order.append(str(int(part.split("+")[1]) - 6))
            else:
                # Creating lists of lists of atoms
                if str(int(part.split("+")[1]) - 5) in self.list_of_atoms.keys():
                    replace_order[(str(int(part.split("+")[1]) - 5))] = str(int(part.split("+")[0]))

        # Start creating MarkInChI by relabeling Te into Zz in core_inchi, remove H on Te and remove the /i layer
        if core_inchi.find("Te") != -1:
            mark_inchi = self.relabel_core(zz.te_to_zz(core_inchi))
        else:
            mark_inchi = self.relabel_core(core_inchi)

        Rsubstituents = self.Rsubstituents

        # Creating parts of MarkInChI for R groups attached
        for num in order:
            #if num not in list(self.main_dict_renumber.values()):
            if self.main_dict_renumber == {}:
                # When there is no variable attachment in the molecule
                num_old = num
            else:
                # Getting old index of the atom since it is associated with this in self.Rpositions
                num_old = self.main_dict_reverse_renumber[num]

            ind = self.Rpositions.index(num_old)
            subs = Rsubstituents[ind]
            sub_inchis = []
            mark_inchi += "<M>"

            for sub in subs:
                # Creates InChI for each R substituents
                sub_inchi = self.relabel_sub(sub)
                if sub_inchi.find("Te") != -1:
                    sub_inchi = zz.te_to_zz("InChI=1B/" + sub_inchi)
                    sub_inchi = "/".join(sub_inchi.split("/")[1:])
                if sub_inchi == "[HH]":
                    sub_inchi = "H"
                sub_inchis.append(sub_inchi)
            sub_inchis.sort()

            # Adding all the InChIs into the MarkInChI
            for one_sub_inchi in sub_inchis:
                mark_inchi += one_sub_inchi + "!"

            mark_inchi = mark_inchi[:-1]

        mark_inchi = mark_inchi.replace("InChI=1S/", "MarkInChI=1B/")

        return copy.deepcopy(mark_inchi), canonical_dict, replace_order

    def produce_markinchi_list_of_atoms(self, replace_order, mark_inchi):

        #### Produces part of MarkInChI associated with lists of atoms (excluding those in variable attachments)

        part = ""
        list_atom_parts = [] # Will contain all the list of atom strings added then to MarkInChI

        # For each replaced atoms creates sub part of MarkInChI and adds it to a list
        for ind in replace_order.keys():
            atom_part = ""
            atom_list = self.list_of_atoms[ind]
            atom_list.sort() # Sorts atom within the list of atoms
            lab = replace_order[ind]
            atom_part += lab + "-"
            for atom in atom_list:
                atom_part += atom + "!"
            atom_part = atom_part[:-1]
            list_atom_parts.append(atom_part)

        list_atom_parts.sort(key=lambda x: int(x.split("-")[0])) # Sorts the parts by the attachment atom index

        # Creates the MarkInChI part for the lists of atoms and adds it to the MarkInChI
        for list_part in list_atom_parts:
            part += "<M>" + list_part
        mark_inchi += part

        return copy.deepcopy(mark_inchi)

    def produce_markinchi_var_attach(self, canonical_dict, zz):

        #### Produces part of MarkInChI associated with variable attachments

        num_var = ""
        var_part = ""
        attach_ids = self.attach_ids
        total_list = [] # List of sums of attachment indices

        # Finding the indices of the atoms to which it is attached and adding them together
        # to create ranking of the substituents (from lowest total to highest) - for canonicality
        for i in range(0, len(list(attach_ids.keys()))):
            total = 0
            for mi in self.attachments[i]:
                other_symbol = self.atom_symbols[int(mi)]
                if other_symbol == "Te":
                    no = 6
                else:
                    no = 5
                new_attach = canonical_dict[str(int(mi) + no)]
                total += int(new_attach)
            total_list.append(total)

        # Using the total_list to sort the substituents
        # from lowest to highest sum of atom attachment numbers
        orig_order = list(range(1, len(list(attach_ids.keys())) + 1, 1))
        var_order = dict(zip(orig_order, total_list))
        var_order = dict(sorted(var_order.items(), key=lambda item: item[1]))

        # Finding all substituents that are attached to exactly the same atoms
        duplicates = []
        for elem in self.attachments:
            if self.attachments.count(elem) > 1:
                if elem not in duplicates:
                    duplicates.append(elem)

        # Initializing variables used inside of the for loop
        is_duplicate = False # Turns True whenever more substituents have the same attachment points
        attach_done = False # Turns True if the "attachment" part of the string (e.g., 1H,2H-) has been already created
        list_attach = [] # Will be list of lists of attachments for one_total to help sorting (by integers)
        previous_attach = [] # Will contain attachment_list of the previous variable attachment
        duplicate_parts = [] # Will contain all variable attachments with the same attachment_list
        list_var_parts = [] # Will contain all variable parts of attachments with the same total so they can be ordered
        k = 1 # Indexing for loop so some values are easier to call

        # Finding total of the first substituent (to sort substituents alphabetically if their total is the same)
        if var_order != {}:
            current_total = list(var_order.values())[0]

        # For each attachment - create appropriate part of MarkInChI
        for i in list(var_order.keys()):
            if k < len(total_list):
                # Find total of the next substituent that will be added
                l = list(var_order.keys())[k]
                future_total = total_list[l - 1]
            else:
                # If this is the last substituent
                future_total = 0

            # Checking whether the total of the current substituent is the same as of the next one
            # (if yes, not added directly, but first all collected and sorted alphabetically)
            one_total = current_total == future_total

            # Finding attachments associated with this substituent
            attachment_list = self.attachments[i - 1]

            # Checking whether there are multiple substituents with the same attachments (to sort them alphabetically)
            if attachment_list in duplicates:
                is_duplicate = True

            # Checking whether the previous substituent had the same attachments
            if attachment_list == previous_attach:
                attach_done = True

            # Find if attached by Te (Zz)
            mol_rank = list(attach_ids.keys())[i - 1]
            symbol = attach_ids[mol_rank]

            # If attach_done = True, the attachment part of the string has been already created - no need to do it again
            # Otherwise creating the attachment part
            if not attach_done:
                attach_points = []
                # Finding attachment points and sorting them from lowest to highest
                for mi in self.attachments[i - 1]:
                    other_symbol = self.atom_symbols[int(mi)]
                    if other_symbol == "Te":
                        no = 6
                    else:
                        no = 5
                    new_attach = canonical_dict[str(int(mi) + no)]
                    attach_points.append(int(new_attach))
                attach_points.sort()

                # Creating attachment part to go with the substituent into the MarkInChI
                num_var = "<M>"
                for attach in attach_points:
                    num_var += str(attach) + "H" + ","
                # If all indices included, remove last "," and add "-" so substituent can follow
                num_var = num_var[:-1]
                num_var += "-"
            list_attach.append(attach_points)

            # Finding sub_inchis of the substituents
            sub_inchis = []
            if symbol == "Te":
                # If var attach drawn as R group or if large_var_attach so that the substituent was added to R
                # find which groups included in the MOL/SDF file are associated with this connection
                ind = self.Rpositions.index(str(mol_rank))
                subs = self.Rsubstituents[ind]
                for sub in subs:
                    # Creating sub_inchis of the substituents of R
                    sub_inchi = self.relabel_sub(sub)
                    if sub_inchi.find("Te") != -1:
                        sub_inchi = zz.te_to_zz("InChI=1B/" + sub_inchi)
                        sub_inchi = "/".join(sub_inchi.split("/")[1:])
                    if sub_inchi == "[HH]":
                        sub_inchi = "H"
                    sub_inchis.append(sub_inchi)

                # Sorting the sub_inchis alphabetically to ensure canonicality
                sub_inchis.sort()
                # Sorting sub_inchis for variable attachments
                duplicate_parts, list_var_parts, var_part = self.sort_var_attach(is_duplicate, one_total, num_var,
                                                                duplicate_parts, list_var_parts, var_part, sub_inchis)
            else:
                # Check if it is a list of atoms
                if str(mol_rank) in self.list_of_atoms.keys():
                    # Get the atoms and sort them alphabetically
                    atoms = self.list_of_atoms[str(mol_rank)]
                    atoms.sort()
                    # Sorting atoms for variable attachments
                    duplicate_parts, list_var_parts, var_part = self.sort_var_attach(is_duplicate, one_total, num_var,
                                                                    duplicate_parts, list_var_parts, var_part, atoms)
                else:
                    # If just a single XHn as variable attachment
                    if is_duplicate:
                        duplicate_parts.append(list(symbol))
                    elif one_total or list_var_parts != []:
                        one_part = num_var + symbol
                        list_var_parts.append(one_part)
                    else:
                        var_part += num_var + symbol

            # If all the substituents with the same attachment points are already in duplicate parts
            if self.attachments.count(attachment_list) == len(duplicate_parts):
                # Sorted alphabetically
                for part in duplicate_parts:
                    part.sort()
                duplicate_parts.sort()

                # Create parts of MarkInChI for each variable attachment
                for sub in duplicate_parts:
                    sub_part = ""
                    # Create sub part of MarkInChI with substituents within each variable attachment
                    for one in sub:
                        sub_part += one + "!"
                    one_part = num_var + sub_part
                    one_part = one_part[:-1]
                    list_var_parts.append(one_part)

            # If all substituents with the same total have been already created a part of MarkInChI
            if not one_total and list_var_parts != []:
                # Create dictionary with attachments as integers and sort them
                # (if strings sorted alphabetically only, it would put e.g., 11H,12H-C before 8H,15H-C)
                var_dict = dict(zip(list_var_parts, list_attach))
                var_dict = dict(sorted(var_dict.items(), key=lambda item: item[1]))
                list_var_parts = list(var_dict.keys())

                # MarkInChI part added to the var_part
                for var in list_var_parts:
                    var_part += var
                # Reset list_var_parts
                list_var_parts = []

            # If not part of one_total or if one_total already done, empty list_attach
            if not one_total and list_var_parts == []:
                list_attach = []


            # Reset/Update variables
            is_duplicate = False
            attach_done = False
            previous_attach = copy.deepcopy(attachment_list)
            current_total = copy.deepcopy(future_total)
            k += 1

        return copy.deepcopy(var_part)

    def produce_markinchi(self):

        zz = zz_convert()
        if 'empty' in self.atom_symbols.values():
            self.atom_symbols = self.renumber_dict()

        core_mol = self.core_mol
        core_inchi = Chem.MolToInchi(core_mol)

        # Attaching R groups
        mark_inchi, canonical_dict, replace_order = self.produce_markinchi_Rgroups(core_inchi, zz)

        # Adding lists of atoms
        mark_inchi = self.produce_markinchi_list_of_atoms(replace_order, mark_inchi)

        # Adding variable attachments
        var_part = self.produce_markinchi_var_attach(canonical_dict, zz)

        mark_inchi += var_part

        # Final MarkInChI made a global variable so it can be called from outside of the class
        self.markinchi_final = copy.deepcopy(mark_inchi)

        return mark_inchi

if __name__=="__main__":
    # Running the code independently
    mark_inchi_final = MarkMol("D:\\alexl\\Documents\\InChiMarkushTesting\\MarkInChI\\marvin\\test11a.sdf")
