from tkinter import filedialog, Tk

def interfaz_seleccionar_archivo():
    """
    Esta función abre una ventana de diálogo para que el usuario seleccione un archivo PPTX. Utiliza la biblioteca Tkinter para crear la interfaz gráfica.

    Returns:
        str: La ruta del archivo seleccionado.
        
    Flujo:
        1. Se crea una instancia de la ventana principal de Tkinter y se oculta.
        2. Se abre un cuadro de diálogo para seleccionar un archivo PPTX.
        3. Se destruye la ventana principal después de seleccionar el archivo.
        4. Se devuelve la ruta del archivo seleccionado
    """
    root = Tk()
    root.withdraw()
    ruta = filedialog.askopenfilename(
        title="Seleccionar Presentación para el TT",
        filetypes=[("PowerPoint", "*.pptx")]
    )
    root.destroy()
    return ruta # Devuelve la ruta al que lo llamó