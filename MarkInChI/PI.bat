pyinstaller -F --noconsole ^
	--paths="D:\alexl\Documents\InChiMarkushTesting\MarkInChI" ^
	--add-data="markinchi_gui.ui;." ^
	markinchi_gui.py