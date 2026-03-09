from tkinter import filedialog, Tk

def interfaz_seleccionar_archivo():
    root = Tk()
    root.withdraw()
    ruta = filedialog.askopenfilename(
        title="Seleccionar Presentación para el TT",
        filetypes=[("PowerPoint", "*.pptx")]
    )
    root.destroy()
    return ruta # Devuelve la ruta al que lo llamó