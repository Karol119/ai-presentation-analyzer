# app/presentation/views/ui_state.py

# Diccionario para el estado lógico de los datos
estado = {
    "subjects": [],
    "subject_files": {},
    "active": "",
    "right_panel_visible": True
}

# Diccionario para guardar las referencias a los widgets de la interfaz
ui = {
    "root": None,
    "body": None, 
    "left_sidebar": None, 
    "content_area": None, 
    "right_panel": None,
    "sidebar_list": None, 
    "tree_scroll": None, 
    "toggle_btn": None, 
    "analyze_btn": None,
    "sidebar_btns": {}, 
    "panels": {}
}