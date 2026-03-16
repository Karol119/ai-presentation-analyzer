import customtkinter as ctk
from tkinter import filedialog
import os
import sys

# Asegura que db.py esté en el path aunque se ejecute desde otro directorio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # ← toda la lógica de BD vive ahí

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Prototipo 01. Cargar una presentación")
        self.geometry("1200x700")
        self.minsize(900, 560)
        self.resizable(True, True)
        self.configure(fg_color="#F1F5F9")

        # Carga inicial desde BD
        all_subjects = db.get_all_subjects()
        self.subjects: list[str] = all_subjects[:2]          # las primeras 2 activas
        self.subject_files: dict[str, list] = {s: [] for s in self.subjects}
        self.active = self.subjects[0]
        self.right_panel_visible = True

        self._build_topbar()

        self.body = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.body.pack(fill="both", expand=True)

        self._build_left_sidebar()
        self._build_content_area()
        self._build_right_panel()
        self._show_panel(self.active)

    # ═════════════════════════════════════════════════════════════════════════
    # TOP BAR
    # ═════════════════════════════════════════════════════════════════════════
    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color="white", corner_radius=0, height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        ctk.CTkLabel(
            bar,
            text="Prototipo 01. Cargar una presentación",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#0F172A",
        ).pack(side="left", padx=24)

        self.toggle_btn = ctk.CTkButton(
            bar,
            text="☰  Contenido",
            font=ctk.CTkFont(size=12),
            fg_color="#EFF6FF", hover_color="#DBEAFE",
            text_color="#2563EB",
            border_width=1, border_color="#BFDBFE",
            corner_radius=8, height=32,
            command=self._toggle_right_panel,
        )
        self.toggle_btn.pack(side="right", padx=(8, 24), pady=12)

        self.analyze_btn = ctk.CTkButton(
            bar,
            text="Analizar presentación",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#94A3B8", hover_color="#64748B",
            text_color="white", corner_radius=8, height=36,
            state="disabled", command=self._analyze,
        )
        self.analyze_btn.pack(side="right", padx=(24, 4), pady=10)

        ctk.CTkFrame(self, height=1, fg_color="#E2E8F0", corner_radius=0).pack(fill="x")

    # ═════════════════════════════════════════════════════════════════════════
    # LEFT SIDEBAR
    # ═════════════════════════════════════════════════════════════════════════
    def _build_left_sidebar(self):
        self.left_sidebar = ctk.CTkFrame(
            self.body, fg_color="white", corner_radius=0, width=210,
            border_width=1, border_color="#E2E8F0",
        )
        self.left_sidebar.pack(side="left", fill="y")
        self.left_sidebar.pack_propagate(False)

        ctk.CTkLabel(
            self.left_sidebar, text="MATERIAS",
            font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8",
        ).pack(anchor="w", padx=16, pady=(18, 8))

        self.sidebar_list = ctk.CTkScrollableFrame(
            self.left_sidebar, fg_color="transparent", corner_radius=0,
            scrollbar_button_color="#E2E8F0",
        )
        self.sidebar_list.pack(fill="both", expand=True, padx=8)

        self.sidebar_btns: dict[str, ctk.CTkFrame] = {}
        for s in self.subjects:
            self._create_sidebar_item(s)

        ctk.CTkFrame(self.left_sidebar, height=1, fg_color="#E2E8F0",
                     corner_radius=0).pack(fill="x", pady=6)

        ctk.CTkButton(
            self.left_sidebar, text="＋  Agregar materia",
            font=ctk.CTkFont(size=12),
            fg_color="transparent", hover_color="#F1F5F9",
            text_color="#64748B", border_width=1, border_color="#CBD5E1",
            corner_radius=8, height=36, anchor="w",
            command=self._open_add_subject_modal,
        ).pack(fill="x", padx=10, pady=(0, 14))

    def _create_sidebar_item(self, name: str):
        is_active = name == self.active
        row = ctk.CTkFrame(
            self.sidebar_list,
            fg_color="#EFF6FF" if is_active else "transparent",
            corner_radius=8, height=40, cursor="hand2",
        )
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)

        indicator = ctk.CTkFrame(
            row, width=3,
            fg_color="#2563EB" if is_active else "transparent",
            corner_radius=2,
        )
        indicator.pack(side="left", fill="y", padx=(4, 0), pady=6)

        label = ctk.CTkLabel(
            row, text=name,
            font=ctk.CTkFont(size=13, weight="bold" if is_active else "normal"),
            text_color="#1D4ED8" if is_active else "#334155",
            anchor="w",
        )
        label.pack(side="left", fill="both", expand=True, padx=8)

        badge_var = ctk.StringVar(value="")
        badge = ctk.CTkLabel(
            row, textvariable=badge_var,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="white",
            fg_color="#2563EB" if is_active else "#CBD5E1",
            corner_radius=10, width=22, height=18,
        )
        badge.pack(side="right", padx=(0, 8))
        badge.pack_forget()

        close = ctk.CTkButton(
            row, text="✕", width=18, height=18,
            font=ctk.CTkFont(size=9),
            fg_color="transparent", hover_color="#FEE2E2",
            text_color="#94A3B8", corner_radius=9,
            command=lambda n=name: self._remove_subject(n),
        )
        close.pack(side="right", padx=(0, 4))

        row._indicator = indicator   # type: ignore
        row._label     = label       # type: ignore
        row._badge     = badge       # type: ignore
        row._badge_var = badge_var   # type: ignore

        for w in (row, label):
            w.bind("<Button-1>", lambda e, n=name: self._select(n))

        self.sidebar_btns[name] = row
        self._refresh_badge(name)

    def _refresh_badge(self, name: str):
        row = self.sidebar_btns.get(name)
        if not row:
            return
        count = len(self.subject_files.get(name, []))
        if count > 0:
            row._badge_var.set(str(count))               # type: ignore
            row._badge.pack(side="right", padx=(0, 8))   # type: ignore
        else:
            row._badge.pack_forget()                     # type: ignore

    def _select(self, name: str):
        self.active = name
        self._refresh_sidebar_styles()
        self._show_panel(name)
        self._update_analyze_btn()
        self._refresh_right_panel(name)

    def _refresh_sidebar_styles(self):
        for n, row in self.sidebar_btns.items():
            a = n == self.active
            row.configure(fg_color="#EFF6FF" if a else "transparent")
            row._indicator.configure(fg_color="#2563EB" if a else "transparent")  # type: ignore
            row._label.configure(                                                   # type: ignore
                text_color="#1D4ED8" if a else "#334155",
                font=ctk.CTkFont(size=13, weight="bold" if a else "normal"),
            )
            row._badge.configure(fg_color="#2563EB" if a else "#CBD5E1")           # type: ignore

    # ── Ventana de confirmación reutilizable ──────────────────────────────────
    def _confirm(self, title: str, message: str, on_confirm):
        win = ctk.CTkToplevel(self)
        win.title(title)
        win.geometry("380x200")
        win.resizable(False, False)
        win.grab_set()
        win.configure(fg_color="white")

        top = ctk.CTkFrame(win, fg_color="transparent")
        top.pack(fill="x", padx=28, pady=(28, 0))

        ctk.CTkLabel(
            top, text="⚠",
            font=ctk.CTkFont(size=28), text_color="#F59E0B",
        ).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            top, text=message,
            font=ctk.CTkFont(size=12), text_color="#334155",
            justify="left", wraplength=280,
        ).pack(side="left", anchor="w")

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=28, pady=24)

        ctk.CTkButton(
            btn_row, text="Cancelar", command=win.destroy,
            fg_color="transparent", hover_color="#F1F5F9",
            text_color="#64748B", border_width=1, border_color="#CBD5E1",
            corner_radius=8, height=36, width=148,
        ).pack(side="left")

        def _do():
            win.destroy()
            on_confirm()

        ctk.CTkButton(
            btn_row, text="Eliminar", command=_do,
            fg_color="#EF4444", hover_color="#DC2626",
            text_color="white", corner_radius=8, height=36, width=148,
        ).pack(side="right")

    def _remove_subject(self, name: str):
        if len(self.subjects) == 1:
            return

        def do_remove():
            self.subjects.remove(name)
            del self.subject_files[name]
            self.sidebar_btns.pop(name).destroy()
            p = self.panels.pop(name, None)
            if p:
                p.destroy()
            if self.active == name:
                self.active = self.subjects[0]
                self._refresh_sidebar_styles()
            self._show_panel(self.active)
            self._update_analyze_btn()

        self._confirm(
            title="Eliminar materia",
            message=f'¿Eliminar "{name}" y todas sus presentaciones cargadas?',
            on_confirm=do_remove,
        )

    # ── Modal agregar materia ─────────────────────────────────────────────────
    def _open_add_subject_modal(self):
        win = ctk.CTkToplevel(self)
        win.title("Agregar materia")
        win.geometry("420x300")
        win.resizable(False, False)
        win.grab_set()
        win.configure(fg_color="white")

        ctk.CTkLabel(
            win, text="Agregar materia",
            font=ctk.CTkFont(size=16, weight="bold"), text_color="#0F172A",
        ).pack(pady=(28, 4), padx=28, anchor="w")

        ctk.CTkLabel(
            win,
            text="Materias disponibles en la base de datos:",
            font=ctk.CTkFont(size=11), text_color="#64748B",
        ).pack(pady=(0, 14), padx=28, anchor="w")

        # Opciones: todas las de BD menos las ya activas
        available = [s for s in db.get_all_subjects() if s not in self.subjects]

        if not available:
            ctk.CTkLabel(
                win, text="No hay más materias disponibles.",
                font=ctk.CTkFont(size=12), text_color="#EF4444",
            ).pack(pady=20)
            ctk.CTkButton(win, text="Cerrar", command=win.destroy,
                          fg_color="#64748B").pack()
            return

        selected_var = ctk.StringVar(value=available[0])

        ctk.CTkLabel(win, text="Materia:", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#334155").pack(anchor="w", padx=28)

        ctk.CTkOptionMenu(
            win, values=available, variable=selected_var,
            font=ctk.CTkFont(size=13),
            fg_color="white", button_color="#2563EB", button_hover_color="#1D4ED8",
            dropdown_fg_color="white", dropdown_hover_color="#EFF6FF",
            dropdown_text_color="#0F172A", text_color="#0F172A",
            corner_radius=8, width=360, height=40,
        ).pack(padx=28, pady=(6, 20))

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=28)

        def confirm():
            name = selected_var.get()
            if name and name not in self.subjects:
                self.subjects.append(name)
                self.subject_files[name] = []
                self._create_sidebar_item(name)
                self._create_panel(name)
                self._select(name)
            win.destroy()

        ctk.CTkButton(
            btn_row, text="Cancelar", command=win.destroy,
            fg_color="transparent", hover_color="#F1F5F9",
            text_color="#64748B", border_width=1, border_color="#CBD5E1",
            corner_radius=8, height=36, width=160,
        ).pack(side="left")

        ctk.CTkButton(
            btn_row, text="Agregar", command=confirm,
            fg_color="#2563EB", hover_color="#1D4ED8",
            text_color="white", corner_radius=8, height=36, width=160,
        ).pack(side="right")

    # ═════════════════════════════════════════════════════════════════════════
    # CONTENT PANELS
    # ═════════════════════════════════════════════════════════════════════════
    def _build_content_area(self):
        self.content_area = ctk.CTkFrame(self.body, fg_color="#F1F5F9", corner_radius=0)
        self.content_area.pack(side="left", fill="both", expand=True)
        self.panels: dict[str, ctk.CTkFrame] = {}
        for s in self.subjects:
            self._create_panel(s)

    def _create_panel(self, name: str):
        panel = ctk.CTkFrame(self.content_area, fg_color="#F1F5F9", corner_radius=0)

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(26, 4))
        ctk.CTkLabel(
            header, text=name,
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color="#0F172A",
        ).pack(side="left")

        section = ctk.CTkFrame(panel, fg_color="transparent")
        section.pack(fill="x", padx=32, pady=(12, 10))
        ctk.CTkLabel(section, text="▶", font=ctk.CTkFont(size=11),
                     text_color="#94A3B8").pack(side="left", padx=(0, 6))
        ctk.CTkLabel(
            section, text="Mis Presentaciones",
            font=ctk.CTkFont(size=14, weight="bold"), text_color="#1E293B",
        ).pack(side="left")

        cards_scroll = ctk.CTkScrollableFrame(
            panel, fg_color="transparent", corner_radius=0,
            scrollbar_button_color="#CBD5E1",
        )
        cards_scroll.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        panel._cards_scroll = cards_scroll   # type: ignore
        self.panels[name] = panel
        self._rebuild_cards(name)

    def _show_panel(self, name: str):
        for n, p in self.panels.items():
            p.place(relx=0, rely=0, relwidth=1, relheight=1) if n == name else p.place_forget()

    def _rebuild_cards(self, subject: str):
        panel = self.panels.get(subject)
        if not panel:
            return
        scroll = panel._cards_scroll   # type: ignore
        for w in scroll.winfo_children():
            w.destroy()
        wrap = ctk.CTkFrame(scroll, fg_color="transparent")
        wrap.pack(anchor="nw")
        for fname, _ in self.subject_files[subject]:
            self._make_file_card(wrap, subject, fname)
        self._make_upload_card(wrap, subject)

    # ═════════════════════════════════════════════════════════════════════════
    # RIGHT PANEL – árbol de contenidos
    # ═════════════════════════════════════════════════════════════════════════
    def _build_right_panel(self):
        self.right_panel = ctk.CTkFrame(
            self.body, fg_color="white", corner_radius=0, width=270,
            border_width=1, border_color="#E2E8F0",
        )
        self.right_panel.pack(side="right", fill="y")
        self.right_panel.pack_propagate(False)

        header = ctk.CTkFrame(self.right_panel, fg_color="transparent", height=46)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(
            header, text="Contenido del curso",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#0F172A",
        ).pack(side="left", padx=16, pady=12)

        ctk.CTkFrame(self.right_panel, height=1, fg_color="#E2E8F0",
                     corner_radius=0).pack(fill="x")

        self.tree_scroll = ctk.CTkScrollableFrame(
            self.right_panel, fg_color="transparent", corner_radius=0,
            scrollbar_button_color="#E2E8F0",
        )
        self.tree_scroll.pack(fill="both", expand=True)

        self._refresh_right_panel(self.active)

    def _refresh_right_panel(self, subject: str):
        for w in self.tree_scroll.winfo_children():
            w.destroy()

        # Carga desde BD (o dummy)
        units = db.get_curriculum(subject)

        if not units:
            ctk.CTkLabel(
                self.tree_scroll,
                text="Sin contenido registrado.",
                font=ctk.CTkFont(size=11), text_color="#94A3B8",
            ).pack(pady=20, padx=16)
            return

        for unit_data in units:
            self._add_unit_row(unit_data)

    # ── Árbol: Unidad ─────────────────────────────────────────────────────────
    def _add_unit_row(self, unit_data: dict):
        expanded = {"v": True}

        # Contenedor hijos (temas)
        children_frame = ctk.CTkFrame(self.tree_scroll, fg_color="transparent")

        unit_row = ctk.CTkFrame(self.tree_scroll, fg_color="transparent", height=28)
        unit_row.pack(fill="x", padx=8, pady=(4, 0))
        unit_row.pack_propagate(False)

        def toggle():
            expanded["v"] = not expanded["v"]
            arrow.configure(text="▾" if expanded["v"] else "▸")
            if expanded["v"]:
                children_frame.pack(fill="x", after=unit_row)
            else:
                children_frame.pack_forget()

        arrow = ctk.CTkLabel(
            unit_row, text="▾", width=16,
            font=ctk.CTkFont(size=11), text_color="#2563EB", cursor="hand2",
        )
        arrow.pack(side="left")
        arrow.bind("<Button-1>", lambda e: toggle())

        ctk.CTkLabel(
            unit_row,
            text=unit_data["unidad"],
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#0F172A", anchor="w", cursor="hand2",
        ).pack(side="left", fill="x", expand=True)

        children_frame.pack(fill="x")
        for tema_data in unit_data["temas"]:
            self._add_tema_row(children_frame, tema_data)

    # ── Árbol: Tema ───────────────────────────────────────────────────────────
    def _add_tema_row(self, parent, tema_data: dict):
        expanded = {"v": True}
        sub_frame = ctk.CTkFrame(parent, fg_color="transparent")

        tema_row = ctk.CTkFrame(parent, fg_color="transparent", height=24)
        tema_row.pack(fill="x", padx=8, pady=(1, 0))
        tema_row.pack_propagate(False)

        def toggle():
            expanded["v"] = not expanded["v"]
            arrow.configure(text="▾" if expanded["v"] else "▸")
            if expanded["v"]:
                sub_frame.pack(fill="x", after=tema_row)
            else:
                sub_frame.pack_forget()

        # Sangría
        ctk.CTkFrame(tema_row, width=20, fg_color="transparent").pack(side="left")

        arrow = ctk.CTkLabel(
            tema_row, text="▾", width=14,
            font=ctk.CTkFont(size=10), text_color="#64748B", cursor="hand2",
        )
        arrow.pack(side="left")
        arrow.bind("<Button-1>", lambda e: toggle())

        ctk.CTkLabel(
            tema_row,
            text=tema_data["tema"],
            font=ctk.CTkFont(size=12),
            text_color="#334155", anchor="w",
        ).pack(side="left", fill="x", expand=True)

        sub_frame.pack(fill="x")
        for sub in tema_data["subtemas"]:
            self._add_subtema_row(sub_frame, sub)

    # ── Árbol: Subtema ────────────────────────────────────────────────────────
    def _add_subtema_row(self, parent, text: str):
        row = ctk.CTkFrame(parent, fg_color="transparent", height=22)
        row.pack(fill="x", padx=8, pady=(0, 0))
        row.pack_propagate(False)

        ctk.CTkFrame(row, width=42, fg_color="transparent").pack(side="left")

        ctk.CTkLabel(
            row, text="·", width=10,
            font=ctk.CTkFont(size=14), text_color="#94A3B8",
        ).pack(side="left")

        ctk.CTkLabel(
            row, text=text,
            font=ctk.CTkFont(size=11),
            text_color="#64748B", anchor="w",
        ).pack(side="left", fill="x", expand=True)

    def _toggle_right_panel(self):
        if self.right_panel_visible:
            self.right_panel.pack_forget()
            self.toggle_btn.configure(
                fg_color="#F1F5F9", text_color="#64748B",
                border_color="#CBD5E1", text="☰  Contenido",
            )
        else:
            self.right_panel.pack(side="right", fill="y")
            self.toggle_btn.configure(
                fg_color="#EFF6FF", text_color="#2563EB",
                border_color="#BFDBFE", text="✕  Ocultar",
            )
        self.right_panel_visible = not self.right_panel_visible

    # ═════════════════════════════════════════════════════════════════════════
    # CARDS
    # ═════════════════════════════════════════════════════════════════════════
    def _make_file_card(self, parent, subject: str, name: str):
        short = name if len(name) <= 20 else name[:17] + "…"
        outer = ctk.CTkFrame(parent, fg_color="transparent", width=152, height=174)
        outer.pack(side="left", padx=(0, 16), pady=4)
        outer.pack_propagate(False)

        card = ctk.CTkFrame(
            outer, width=144, height=164,
            fg_color="white", border_width=1, border_color="#BFDBFE",
            corner_radius=14,
        )
        card.place(x=0, y=6)
        card.pack_propagate(False)

        ctk.CTkLabel(card, text="📄", font=ctk.CTkFont(size=40)).pack(pady=(20, 6))
        ctk.CTkLabel(
            card, text=short, font=ctk.CTkFont(size=11),
            text_color="#1E40AF", wraplength=124, justify="center",
        ).pack(padx=10)

        ctk.CTkButton(
            outer, text="✕", width=24, height=24,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#EF4444", hover_color="#DC2626",
            text_color="white", corner_radius=12,
            command=lambda n=name, s=subject: self._remove_file(s, n),
        ).place(x=122, y=0)

    def _make_upload_card(self, parent, subject: str):
        card = ctk.CTkFrame(
            parent, width=144, height=164,
            fg_color="white", border_width=2, border_color="#CBD5E1",
            corner_radius=14, cursor="hand2",
        )
        card.pack(side="left", padx=(0, 16), pady=4)
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(inner, text="＋", font=ctk.CTkFont(size=32),
                     text_color="#94A3B8").pack()
        ctk.CTkLabel(
            inner, text="Subir nueva\npresentación",
            font=ctk.CTkFont(size=12), text_color="#64748B", justify="center",
        ).pack(pady=(4, 0))

        def pick(e=None, s=subject):
            self._pick_files(s)

        for w in [card, inner] + inner.winfo_children():
            w.bind("<Button-1>", pick)
        card.bind("<Enter>", lambda e: card.configure(fg_color="#F8FAFC"))
        card.bind("<Leave>", lambda e: card.configure(fg_color="white"))

    # ═════════════════════════════════════════════════════════════════════════
    # FILE ACTIONS
    # ═════════════════════════════════════════════════════════════════════════
    def _pick_files(self, subject: str):
        paths = filedialog.askopenfilenames(
            title=f"Subir presentaciones — {subject}",
            filetypes=[
                ("Presentaciones", "*.pptx *.ppt *.pdf"),
                ("Todos los archivos", "*.*"),
            ],
        )
        existing = {n for n, _ in self.subject_files[subject]}
        for p in paths:
            name = os.path.basename(p)
            if name not in existing:
                self.subject_files[subject].append((name, None))
                existing.add(name)
        self._rebuild_cards(subject)
        self._refresh_badge(subject)
        self._update_analyze_btn()

    def _remove_file(self, subject: str, name: str):
        def do_remove():
            self.subject_files[subject] = [
                (n, f) for n, f in self.subject_files[subject] if n != name
            ]
            self._rebuild_cards(subject)
            self._refresh_badge(subject)
            self._update_analyze_btn()
        self._confirm(
            title="Eliminar presentación",
            message=f'¿Eliminar "{name}" de {subject}?',
            on_confirm=do_remove,
        )

    def _update_analyze_btn(self):
        has = bool(self.subject_files.get(self.active))
        self.analyze_btn.configure(
            state="normal" if has else "disabled",
            fg_color="#2563EB" if has else "#94A3B8",
            hover_color="#1D4ED8" if has else "#64748B",
        )

    def _analyze(self):
        subject = self.active
        names = "\n".join(f"• {n}" for n, _ in self.subject_files[subject])
        win = ctk.CTkToplevel(self)
        win.title("Analizar presentación")
        win.geometry("380x260")
        win.grab_set()
        ctk.CTkLabel(
            win, text=f"Analizando: {subject}",
            font=ctk.CTkFont(size=15, weight="bold"), text_color="#0F172A",
        ).pack(pady=(28, 8))
        ctk.CTkLabel(
            win, text=names, font=ctk.CTkFont(size=12),
            text_color="#334155", justify="left",
        ).pack(padx=24)
        ctk.CTkButton(
            win, text="Cerrar", command=win.destroy,
            fg_color="#2563EB", hover_color="#1D4ED8", corner_radius=8,
        ).pack(pady=24)


if __name__ == "__main__":
    app = App()
    app.mainloop()