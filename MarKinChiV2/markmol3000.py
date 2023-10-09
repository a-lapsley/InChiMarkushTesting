class MarkMol3000(object):
    def __init__(self) -> None:
        self.molfile_lines = [] #Lines of v3000 .mol file that will be converted
        self.core = None #RDKit Mol object containing core of molecule
        self.rgroups = None #List of RDKit Mol objects containing each R group

    def load_from_file(self, file_path):
        # Loads V3000 molfile with path 'file_path'
        # Stores contents of the molfile in self.molfile_lines
        # Returns 1 if file is valid and is loaded succesfully
        # Returns -1 otherwise

        # Check file is a .mol file
        if file_path.endswith(".mol") != True:
            print("Invalid file format. Please use a .mol file")
            return -1
        try:
            with open(file_path) as file:
                lines = file.readlines()

                # Check file uses the V3000 format
                if lines[3].find("V3000") == -1:
                    print("Invalid file provided. Please ensure the file is "
                          "using the V3000 molfile format."
                          )
                    return -1
                else:
                    self.molfile_lines = lines 
                    return 1
        except:
            print("Unable to open file \'%s\'" % file_path)
            return -1

    def generate_markinchi(self):
        #Generates the MarkInChI for the loaded v3000 .mol file

        self.core = self.generate_core()
        self.rgroups = self.generate_rgroups()

        pass

    def generate_core(self):
        #Generates RDKit Mol object for core of molecule from molfile_lines

        pass

    def generate_rgroups(self):
        #Generates RDKit Mol object for each R group from molfile_lines and 
        #adds them to the list rgroups
        
        pass


if __name__ == "__main__":
    #If file run independently
    markinchi = MarkMol3000()
    laptop_filedir = "C:\\Users\\alexl\\OneDrive\\Documents\\InChiMarkushTesting\\MarKinChiV2\\marvin\\test2.mol"
    desktop_filedir = "D:\\alexl\\Documents\\InChiMarkushTesting\\MarKinChiV2\\marvin\\test2.mol"
    markinchi.load_from_file(desktop_filedir)
    print(markinchi.molfile_lines)
    