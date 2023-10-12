from rdkit.Chem.Draw import MolsToImage

def ShowMols(mols, subImgSize=(200, 200), title='RDKit Molecule',
            stayInFront=True, **kwargs):
  """ Generates a picture of molecules and displays it in a Tkinter window
  """
  import tkinter

  from PIL import ImageTk

  img = MolsToImage(mols, subImgSize, **kwargs)

  tkRoot = tkinter.Tk()
  tkRoot.title(title)
  tkPI = ImageTk.PhotoImage(img)
  tkLabel = tkinter.Label(tkRoot, image=tkPI)
  tkLabel.place(x=0, y=0, width=img.size[0], height=img.size[1])
  tkRoot.geometry('%dx%d' % (img.size))
  tkRoot.lift()
  if stayInFront:
    tkRoot.attributes('-topmost', True)
  tkRoot.mainloop()