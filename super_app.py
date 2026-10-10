from __future__ import annotations

from collections.abc import Callable
import math
import json
import os
import queue
import sys
import threading
import tkinter as tk
import xml.etree.ElementTree as ET
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import Super
from app_info import APP_VERSION, CALCULATION_ENGINE_VERSION, version_label
import app_logging
from criteria_info import MDOT_PROFILE_ID, TDOT_PROFILE_ID, AASHTO_PROFILE_ID
import super_batch
import super_dxf
import super_exports
import super_landxml
import super_pdf
import super_project
import super_qa
import super_updates
from super_lane import build_lane_rows, lane_profile_points, parse_slope_percent, slope_at_station, slope_matches


DARK_BG = "#07100e"
DARK_PANEL = "#0e1a17"
DARK_PANEL_ALT = "#14231f"
DARK_FIELD = "#091411"
DARK_BORDER = "#2b433b"
DARK_TEXT = "#e8f0ed"
DARK_MUTED = "#91a49d"
DARK_ACCENT = "#3bd1bd"
DARK_SELECT = "#176f65"
AMBER_ACCENT = "#e8b75d"
RED_ACCENT = "#ff8178"

IS_MACOS = sys.platform == "darwin"
UI_FONT = (".AppleSystemUIFont", 11) if IS_MACOS else ("Segoe UI", 9)
HEADER_FONT = (".AppleSystemUIFont", 13, "bold") if IS_MACOS else ("Segoe UI", 12, "bold")
VALUE_FONT = (".AppleSystemUIFont", 12, "bold") if IS_MACOS else ("Segoe UI", 11, "bold")
TEXT_FONT = (".AppleSystemUIFont", 11) if IS_MACOS else ("Segoe UI", 10)
MONO_FONT = ("Menlo", 10) if IS_MACOS else ("Consolas", 9)

CRITERIA_PROFILE_LABELS = {
    MDOT_PROFILE_ID: "Mississippi DOT (MDOT) - revised April 22, 2026",
    TDOT_PROFILE_ID: "Tennessee DOT (TDOT) - revised April 30, 2026",
    AASHTO_PROFILE_ID: "AASHTO Green Book 2018 - October 2019 errata",
}
CRITERIA_PROFILE_IDS = {label: profile_id for profile_id, label in CRITERIA_PROFILE_LABELS.items()}


class ModernSuperElevationUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        app_logging.configure_logging()
        self.title(version_label())
        if IS_MACOS:
            self.minsize(1080, 680)
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            window_width = min(1280, max(1080, screen_width - 40))
            window_height = min(780, max(680, screen_height - 80))
            self.geometry(f"{window_width}x{window_height}")
        else:
            self.minsize(900, 560)
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            dpi_scale = max(1.0, float(self.tk.call("tk", "scaling")) / (96.0 / 72.0))
            usable_width = int((screen_width - 80) / dpi_scale)
            usable_height = int((screen_height - 100) / dpi_scale)
            window_width = min(1280, max(900, usable_width))
            window_height = min(780, max(560, usable_height))
            self.geometry(f"{window_width}x{window_height}")
        self.last_results: dict | None = None
        self.last_meta: dict = {}
        self.curves: list[dict] = []
        self._diagnostic_findings: list[dict] = []
        self.project_path: str | None = None
        self.excluded_landxml_curve_indexes: list[int] = []
        self._auto_job: str | None = None
        self._suspend_auto = False
        self._landxml_data: super_landxml.LandXMLData | None = None
        self._landxml_curve_presets: list[dict] = []
        self._landxml_source: dict[str, str] | None = None
        self._update_result_queue: queue.Queue[super_updates.UpdateInfo | None] = queue.Queue(maxsize=1)
        self._update_dialog: tk.Toplevel | None = None
        self._desktop_diagram_data: dict | None = None
        self._desktop_diagram_domain: tuple[float, float] | None = None
        self._desktop_diagram_station: float | None = None
        self.diagram_snap_events = tk.BooleanVar(value=True)

        self.vars = {
            "criteria_profile": tk.StringVar(value=MDOT_PROFILE_ID),
            "project_name": tk.StringVar(),
            "route_name": tk.StringVar(),
            "alignment_name": tk.StringVar(),
            "curve_name": tk.StringVar(),
            "curve_direction": tk.StringVar(value="left"),
            "landxml_path": tk.StringVar(),
            "landxml_curve": tk.StringVar(),
            "station_equations": tk.StringVar(),
            "alignment_station_range": tk.StringVar(),
            "pc": tk.StringVar(),
            "pt": tk.StringVar(),
            "speed": tk.StringVar(),
            "radius": tk.StringVar(),
            "facility": tk.StringVar(value="centerline"),
            "area": tk.StringVar(value="rural"),
            "lane_width": tk.StringVar(value="12"),
            "lanes_rotated": tk.StringVar(value="2"),
            "e_manual": tk.StringVar(),
            "friction": tk.StringVar(),
            "rel_grad": tk.StringVar(),
            "normal_crown": tk.StringVar(value="0.02"),
            "Lr_manual": tk.StringVar(),
            "Lt_manual": tk.StringVar(),
            "lookup_station": tk.StringVar(),
            "lookup_super": tk.StringVar(),
            "station_format": tk.BooleanVar(value=True),
            "auto_open_pdf": tk.BooleanVar(value=True),
            "curve_notes": tk.StringVar(),
        }
        self.criteria_profile_display = tk.StringVar(value=CRITERIA_PROFILE_LABELS[MDOT_PROFILE_ID])
        for key,value in {"max_superelevation":"8","roadway":"two_way","initial_section":"crowned","rotation_axis":"centerline",
                          "lane_widths":"12,12","crown_from_left":"","left_normal_slope":"0.02","right_normal_slope":"0.02","initial_slope":"-0.02",
                          "alignment_type":"circular","ts":"","st":"","runout_placement":"on_tangent","runoff_tangent_percent":"",
                          "override_standard_placement":"false","acknowledge_spiral_override":"false","aashto_tables":"","linear_unit":""}.items():
            self.vars[key]=tk.StringVar(value=value)
        self.computed_vars = {
            "e": tk.StringVar(value="auto"),
            "Lr": tk.StringVar(value="auto"),
            "Lt": tk.StringVar(value="auto"),
            "rel_grad": tk.StringVar(value="auto"),
            "friction": tk.StringVar(value="auto"),
            "normal_crown": tk.StringVar(value="0.0200"),
        }
        self.advanced_summary = tk.StringVar(value="Advanced: Automatic defaults")

        self._configure_style()
        self._build_layout()
        self._setup_auto_handlers()
        self._update_overlay_button()
        self.after(750, self._start_update_check)
        if IS_MACOS:
            self.after_idle(self._maximize_window)

    def report_callback_exception(self, exc_type: type[BaseException], exc: BaseException, tb: object) -> None:
        """Log otherwise-unhandled Tk callbacks and give the user a support path."""
        path = app_logging.record_uncaught_exception(exc_type, exc, tb)
        open_logs = messagebox.askyesno(
            "Unexpected Error",
            "The application encountered an unexpected error. Your project files were not sent anywhere.\n\n"
            f"Details were written to:\n{path}\n\nOpen the log folder now?",
            parent=self,
        )
        if open_logs:
            try:
                app_logging.open_log_directory()
            except Exception:
                pass

    def _show_operation_error(self, title: str, operation: str, exc: BaseException, path: str | None = None) -> None:
        log_file = app_logging.record_exception(operation, exc)
        message = app_logging.friendly_error(operation, exc, path)
        open_logs = messagebox.askyesno(
            title,
            f"{message}\n\nTroubleshooting details were written to:\n{log_file}\n\nOpen the log folder now?",
            parent=self,
        )
        if open_logs:
            try:
                app_logging.open_log_directory()
            except Exception as open_exc:
                app_logging.record_exception("open_log_directory", open_exc)

    def _maximize_window(self) -> None:
        """Open maximized so all controls remain available on launch."""
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                pass

    def _start_update_check(self) -> None:
        """Check once per launch without blocking or calling Tk from the worker."""
        worker = threading.Thread(
            target=self._check_for_update_worker,
            name="superelevation-update-check",
            daemon=True,
        )
        worker.start()
        self.after(100, self._poll_update_check)

    def _check_for_update_worker(self) -> None:
        self._update_result_queue.put(super_updates.check_for_update())

    def _poll_update_check(self) -> None:
        try:
            update = self._update_result_queue.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_update_check)
            return
        if update is not None:
            self._show_update_available(update)

    def _show_update_available(self, update: super_updates.UpdateInfo) -> None:
        """Offer the matching release download while leaving installation manual."""
        if self._update_dialog is not None and self._update_dialog.winfo_exists():
            self._update_dialog.lift()
            return

        dialog = tk.Toplevel(self)
        self._update_dialog = dialog
        dialog.title("Update Available")
        dialog.transient(self)
        dialog.resizable(False, False)
        dialog.configure(background=DARK_PANEL)

        body = ttk.Frame(dialog, style="Panel.TFrame", padding=16)
        body.grid(row=0, column=0, sticky="nsew")
        ttk.Label(body, text="A newer release is available", style="Header.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(
            body,
            text=(
                f"You are using version {update.current_version}. "
                f"Version {update.latest_version} is ready to download."
            ),
            style="Panel.TLabel",
            wraplength=520,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 12))
        ttk.Label(
            body,
            text="The download opens in your browser. Install or replace the application manually.",
            style="Muted.Panel.TLabel",
            wraplength=520,
            justify="left",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 8))
        def close_dialog() -> None:
            self._update_dialog = None
            dialog.destroy()

        buttons = ttk.Frame(body, style="Panel.TFrame")
        buttons.grid(row=3, column=0, columnspan=2, sticky="e", pady=(6, 0))
        ttk.Button(buttons, text="Later", command=close_dialog).grid(row=0, column=0, padx=(0, 8))
        copy_button = ttk.Button(buttons, text="Copy Download Link")
        copy_button.configure(command=lambda: self._copy_update_download(update, dialog, copy_button))
        copy_button.grid(row=0, column=1, padx=(0, 8))
        ttk.Button(
            buttons,
            text="Download Update",
            command=lambda: self._open_update_download(update, dialog, close_dialog),
            style="Primary.TButton",
        ).grid(row=0, column=2)
        body.columnconfigure(0, weight=1)
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        dialog.grab_set()
        dialog.focus_force()

    def _copy_update_download(
        self,
        update: super_updates.UpdateInfo,
        dialog: tk.Toplevel,
        button: ttk.Button,
    ) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append(update.download_url)
            self.update_idletasks()
            button.configure(text="Copied")
            def reset_button() -> None:
                try:
                    if button.winfo_exists():
                        button.configure(text="Copy Download Link")
                except tk.TclError:
                    pass

            self.after(2000, reset_button)
        except Exception as exc:
            app_logging.record_exception("copy_update_download", exc)
            messagebox.showerror(
                "Copy Download Link",
                "The link could not be copied. Select Download Update to open it in your browser.",
                parent=dialog,
            )

    def _open_update_download(
        self,
        update: super_updates.UpdateInfo,
        dialog: tk.Toplevel,
        close_dialog: Callable[[], None],
    ) -> None:
        try:
            opened = webbrowser.open_new_tab(update.download_url)
        except Exception as exc:
            app_logging.record_exception("open_update_download", exc)
            opened = False
        if opened:
            close_dialog()
            return
        messagebox.showerror(
            "Open Download",
            "The browser could not be opened. Select Copy Download Link and open it manually.",
            parent=dialog,
        )

    def _configure_style(self) -> None:
        self.configure(background=DARK_BG)
        self.option_add("*Font", UI_FONT)
        self.option_add("*Entry.Background", DARK_FIELD)
        self.option_add("*Entry.Foreground", DARK_TEXT)
        self.option_add("*Entry.InsertBackground", DARK_TEXT)
        self.option_add("*Listbox.Background", DARK_FIELD)
        self.option_add("*Listbox.Foreground", DARK_TEXT)
        self.option_add("*Listbox.SelectBackground", DARK_SELECT)
        self.option_add("*Listbox.SelectForeground", DARK_TEXT)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        base_style = {"background": DARK_BG, "foreground": DARK_TEXT, "fieldbackground": DARK_FIELD}
        if IS_MACOS:
            base_style["font"] = UI_FONT
        style.configure(".", **base_style)
        style.configure("TFrame", background=DARK_BG)
        style.configure("Panel.TFrame", background=DARK_PANEL)
        style.configure("Topbar.TFrame", background="#0d292d")
        style.configure("TLabel", background=DARK_BG, foreground=DARK_TEXT)
        style.configure("Panel.TLabel", background=DARK_PANEL, foreground=DARK_TEXT)
        style.configure("Topbar.TLabel", background="#0d292d", foreground="#f4fbf8")
        style.configure("TopbarMuted.TLabel", background="#0d292d", foreground="#9fc1b7")
        style.configure("Brand.Topbar.TLabel", font=(UI_FONT[0], 15, "bold"), background="#0d292d", foreground=DARK_ACCENT)
        style.configure("Step.Panel.TLabel", font=(UI_FONT[0], 8, "bold"), background=DARK_PANEL, foreground=DARK_ACCENT)
        style.configure("Muted.Panel.TLabel", background=DARK_PANEL, foreground=DARK_MUTED)
        style.configure("Header.TLabel", font=HEADER_FONT, background=DARK_PANEL, foreground=DARK_TEXT)
        style.configure("Value.TLabel", font=VALUE_FONT, background=DARK_PANEL, foreground=DARK_TEXT)
        style.configure(
            "TEntry",
            fieldbackground=DARK_FIELD,
            foreground=DARK_TEXT,
            insertcolor=DARK_TEXT,
            bordercolor=DARK_BORDER,
            lightcolor=DARK_BORDER,
            darkcolor=DARK_BORDER,
            padding=(4, 3),
        )
        style.map(
            "TEntry",
            fieldbackground=[("disabled", DARK_PANEL_ALT), ("readonly", DARK_FIELD), ("focus", DARK_FIELD)],
            foreground=[("disabled", DARK_MUTED), ("readonly", DARK_TEXT)],
            bordercolor=[("focus", DARK_ACCENT)],
        )
        style.configure(
            "TCombobox",
            fieldbackground=DARK_FIELD,
            background=DARK_PANEL_ALT,
            foreground=DARK_TEXT,
            arrowcolor=DARK_TEXT,
            bordercolor=DARK_BORDER,
            lightcolor=DARK_BORDER,
            darkcolor=DARK_BORDER,
            padding=(4, 3),
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", DARK_FIELD)],
            foreground=[("readonly", DARK_TEXT)],
            selectbackground=[("readonly", DARK_FIELD)],
            selectforeground=[("readonly", DARK_TEXT)],
            bordercolor=[("focus", DARK_ACCENT)],
        )
        style.configure(
            "TButton",
            padding=(10, 5),
            background=DARK_PANEL_ALT,
            foreground=DARK_TEXT,
            bordercolor=DARK_BORDER,
            lightcolor=DARK_BORDER,
            darkcolor=DARK_BORDER,
            focusthickness=1,
            focuscolor=DARK_ACCENT,
        )
        style.map(
            "TButton",
            background=[("active", "#1d342e"), ("pressed", "#176f65")],
            foreground=[("disabled", DARK_MUTED)],
        )
        style.configure("Primary.TButton", padding=(12, 6), background="#168f82", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#20a493"), ("pressed", "#11776d")])
        style.configure("TCheckbutton", background=DARK_PANEL, foreground=DARK_TEXT, indicatorbackground=DARK_FIELD)
        style.map(
            "TCheckbutton",
            background=[("active", DARK_PANEL)],
            foreground=[("disabled", DARK_MUTED)],
            indicatorbackground=[("selected", DARK_ACCENT), ("!selected", DARK_FIELD)],
        )
        style.configure("Vertical.TScrollbar", background=DARK_PANEL_ALT, troughcolor=DARK_FIELD, bordercolor=DARK_BORDER)
        style.configure(
            "TNotebook",
            background=DARK_BG,
            bordercolor=DARK_BORDER,
            lightcolor=DARK_BORDER,
            darkcolor=DARK_BORDER,
            tabmargins=(0, 0, 0, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background=DARK_PANEL_ALT,
            foreground=DARK_TEXT,
            bordercolor=DARK_BORDER,
            lightcolor=DARK_BORDER,
            darkcolor=DARK_BORDER,
            padding=(10, 5),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", DARK_SELECT), ("active", "#1d342e")],
            foreground=[("selected", "#ffffff"), ("active", DARK_TEXT)],
        )

    def _build_layout(self) -> None:
        header = ttk.Frame(self, style="Topbar.TFrame", padding=(16, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(2, weight=1)
        ttk.Label(header, text="SE", style="Brand.Topbar.TLabel").grid(row=0, column=0, rowspan=2, padx=(0, 14))
        ttk.Label(header, text="CIVIL DESIGN WORKSPACE", style="TopbarMuted.TLabel").grid(row=0, column=1, sticky="sw")
        ttk.Label(header, text="Superelevation Calculator", style="Topbar.TLabel", font=HEADER_FONT).grid(
            row=1, column=1, sticky="nw"
        )
        ttk.Label(
            header,
            text=f"LOCAL PROCESSING   APP {APP_VERSION}   ENGINE {CALCULATION_ENGINE_VERSION}",
            style="TopbarMuted.TLabel",
        ).grid(row=0, column=2, rowspan=2, sticky="e")

        root = ttk.Frame(self, padding=10)
        root.grid(row=1, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        if IS_MACOS:
            root.columnconfigure(0, weight=0, minsize=280)
            root.columnconfigure(1, weight=2, minsize=460)
            root.columnconfigure(2, weight=1, minsize=300)
        else:
            root.columnconfigure(0, weight=0)
            root.columnconfigure(1, weight=1)
            root.columnconfigure(2, weight=1)
        root.rowconfigure(0, weight=1)
        root.rowconfigure(1, weight=0)

        self._build_project_panel(root)
        self._build_input_panel(root)
        self._build_results_panel(root)
        self._build_output_bar(root)

    def _build_project_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=10)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        panel.rowconfigure(3, weight=1)

        ttk.Label(panel, text="01  Project", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        buttons = ttk.Frame(panel, style="Panel.TFrame")
        buttons.grid(row=1, column=0, sticky="ew", pady=(8, 10))
        for idx, (label, command) in enumerate(
            [
                ("New", self._new_project),
                ("Load", self._load_project),
                ("Save", self._save_project),
                ("Help", self._show_instructions),
            ]
        ):
            button_row, button_column = divmod(idx, 2)
            ttk.Button(buttons, text=label, command=command).grid(
                row=button_row,
                column=button_column,
                sticky="ew",
                padx=(0, 6),
                pady=(0, 6 if button_row == 0 else 0),
            )
            buttons.columnconfigure(button_column, weight=1)

        meta = ttk.Frame(panel, style="Panel.TFrame")
        meta.grid(row=2, column=0, sticky="ew")
        ttk.Label(meta, text="Project name", style="Panel.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 4))
        project_entry_width = 24 if IS_MACOS else 30
        ttk.Entry(meta, textvariable=self.vars["project_name"], width=project_entry_width).grid(
            row=1, column=0, sticky="ew", pady=(0, 8)
        )
        ttk.Label(meta, text="Route name", style="Panel.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(meta, textvariable=self.vars["route_name"], width=project_entry_width).grid(
            row=3, column=0, sticky="ew", pady=(0, 8)
        )
        ttk.Button(meta, text="Select LandXML", command=self._select_landxml).grid(row=4, column=0, sticky="ew", pady=(0, 4))
        ttk.Button(meta, text="Add All LandXML Curves", command=self._add_all_landxml_curves).grid(
            row=5, column=0, sticky="ew", pady=(0, 4)
        )
        self.landxml_status = tk.StringVar(value="LandXML: none")
        ttk.Label(meta, textvariable=self.landxml_status, style="Muted.Panel.TLabel", wraplength=240, justify="left").grid(
            row=6, column=0, sticky="w", pady=(0, 8)
        )
        meta.columnconfigure(0, weight=1)

        self.curve_listbox = tk.Listbox(
            panel,
            width=(22 if IS_MACOS else 30),
            height=12,
            activestyle="dotbox",
            background=DARK_FIELD,
            foreground=DARK_TEXT,
            selectbackground=DARK_SELECT,
            selectforeground=DARK_TEXT,
            highlightbackground=DARK_BORDER,
            highlightcolor=DARK_ACCENT,
            relief="flat",
            borderwidth=6,
        )
        self.curve_listbox.grid(row=3, column=0, sticky="nsew")
        self.curve_listbox.bind("<<ListboxSelect>>", self._load_selected_curve)

        curve_buttons = ttk.Frame(panel, style="Panel.TFrame")
        curve_buttons.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        for column, (label, command) in enumerate(
            [("Add", self._add_curve), ("Update", self._update_selected_curve), ("Remove", self._remove_curve)]
        ):
            ttk.Button(curve_buttons, text=label, command=command, width=7).grid(
                row=0, column=column, sticky="ew", padx=(0, 6 if column < 2 else 0)
            )
            curve_buttons.columnconfigure(column, weight=1)

    def _build_input_panel(self, parent: ttk.Frame) -> None:
        shell = ttk.Frame(parent, style="Panel.TFrame", padding=10)
        shell.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(0, weight=1)

        canvas = tk.Canvas(shell, highlightthickness=0, background=DARK_PANEL)
        scrollbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        body = ttk.Frame(canvas, style="Panel.TFrame")
        window = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        body.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))

        row = 0
        row = self._section(body, row, "02  Curve inputs")
        row = self._combo(body, row, "LandXML curve", "landxml_curve", [])
        row = self._field(body, row, "Alignment name", "alignment_name")
        row = self._field(body, row, "Curve name", "curve_name")
        row = self._combo(body, row, "Curve direction", "curve_direction", ["left", "right"])
        row = self._field(body, row, "PC station *", "pc")
        row = self._field(body, row, "PT station", "pt")
        row = self._combo(body, row, "Design speed (mph) *", "speed", [str(v) for v in range(15, 85, 5)])
        row = self._field(body, row, "Curve radius (ft) *", "radius")

        row = self._section(body, row, "Roadway")
        row = self._profile_combo(
            body,
            row,
            "Governing standard",
        )
        row = self._combo(
            body,
            row,
            "Facility / roadway layout",
            "facility",
            ["centerline", "outside edge", "undivided"],
        )
        row = self._combo(body, row, "Area type", "area", ["rural", "urban", "local"])
        row = self._field(body, row, "Lane width (ft)", "lane_width")
        row = self._field(body, row, "Lanes rotated", "lanes_rotated")
        ttk.Button(body,text="AASHTO / transition placement settings…",command=self._show_aashto_settings).grid(row=row,column=0,columnspan=3,sticky="ew",pady=8)
        row+=1

        advanced = ttk.Frame(body, style="Panel.TFrame")
        advanced.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(12, 4))
        ttk.Button(advanced, text="Advanced Settings…", command=self._show_advanced_settings).grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )
        ttk.Label(advanced, textvariable=self.advanced_summary, style="Muted.Panel.TLabel", wraplength=360).grid(
            row=0, column=1, sticky="w"
        )
        advanced.columnconfigure(1, weight=1)
        row += 1
        row = self._field(body, row, "Curve notes", "curve_notes")

        actions = ttk.Frame(body, style="Panel.TFrame")
        actions.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(12, 4))
        ttk.Button(actions, text="Compute", command=self._compute, style="Primary.TButton").grid(row=0, column=0, padx=(0, 8))
        ttk.Button(actions, text="Clear", command=self._clear).grid(row=0, column=1, padx=(0, 8))
        ttk.Checkbutton(actions, text="Station format", variable=self.vars["station_format"]).grid(row=0, column=2)
        body.columnconfigure(0, weight=0, minsize=124)
        body.columnconfigure(1, weight=0, minsize=168)
        body.columnconfigure(2, weight=1, minsize=170)

    def _build_output_bar(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent, style="Panel.TFrame", padding=(10, 8))
        bar.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        bar.columnconfigure(6, weight=1)

        ttk.Label(bar, text="04  Review & export", style="Header.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 16))

        ttk.Checkbutton(
            bar,
            text="Auto-open PDF",
            variable=self.vars["auto_open_pdf"],
            style="TCheckbutton",
        ).grid(row=0, column=1, sticky="w", padx=(0, 10))
        ttk.Button(bar, text="Export PDF", command=self._export_pdf, style="Primary.TButton").grid(
            row=0, column=2, padx=(0, 6)
        )
        ttk.Button(bar, text="Export ORD CSV", command=self._export_ord_csv).grid(row=0, column=3, padx=(0, 6))
        self.overlay_button = ttk.Button(bar, text="Export Overlay DXF", command=self._export_overlay_dxf)
        self.overlay_button.grid(row=0, column=4, padx=(0, 6))
        ttk.Button(bar, text="DXF Issues", command=self._show_overlay_issues).grid(row=0, column=5, padx=(0, 10))
        self.overlay_status = tk.StringVar(value="DXF: select LandXML and calculate a curve")
        ttk.Label(
            bar,
            textvariable=self.overlay_status,
            style="Muted.Panel.TLabel",
            wraplength=420,
            justify="left",
        ).grid(row=0, column=6, sticky="ew")

    def _build_results_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=10)
        panel.grid(row=0, column=2, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(2, weight=1)

        ttk.Label(panel, text="03  Results", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        self.summary = ttk.Frame(panel, style="Panel.TFrame")
        self.summary.grid(row=1, column=0, sticky="ew", pady=(8, 8))
        for idx, label in enumerate(["e", "Lr", "Lt"]):
            ttk.Label(self.summary, text=label, style="Panel.TLabel").grid(row=0, column=idx, sticky="w", padx=(0, 18))
            ttk.Label(self.summary, textvariable=self.computed_vars[label], style="Value.TLabel").grid(
                row=1, column=idx, sticky="w", padx=(0, 18)
            )

        notebook = ttk.Notebook(panel)
        notebook.grid(row=2, column=0, sticky="nsew")
        diagram_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=8)
        details_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=6)
        notebook.add(diagram_tab, text="Diagram")
        notebook.add(details_tab, text="Details")

        diagram_tab.columnconfigure(0, weight=1)
        diagram_tab.rowconfigure(1, weight=1)
        diagram_tools = ttk.Frame(diagram_tab, style="Panel.TFrame")
        diagram_tools.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.diagram_range = tk.StringVar(value="Calculate a curve to view its lane profile")
        ttk.Label(diagram_tools, textvariable=self.diagram_range, style="Muted.Panel.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        diagram_tools.columnconfigure(0, weight=1)
        ttk.Checkbutton(diagram_tools, text="Snap events", variable=self.diagram_snap_events).grid(
            row=0, column=1, padx=(4, 6)
        )
        ttk.Button(diagram_tools, text="-", width=3, command=lambda: self._zoom_desktop_diagram(1.3)).grid(
            row=0, column=2, padx=(4, 2)
        )
        ttk.Button(diagram_tools, text="+", width=3, command=lambda: self._zoom_desktop_diagram(0.77)).grid(
            row=0, column=3, padx=2
        )
        ttk.Button(diagram_tools, text="Reset", command=self._reset_desktop_diagram_zoom).grid(
            row=0, column=4, padx=(2, 0)
        )
        self.diagram_canvas = tk.Canvas(
            diagram_tab,
            height=330,
            background=DARK_FIELD,
            highlightbackground=DARK_BORDER,
            highlightcolor=DARK_ACCENT,
            highlightthickness=1,
            cursor="crosshair",
        )
        self.diagram_canvas.grid(row=1, column=0, sticky="nsew")
        self.diagram_canvas.bind("<Configure>", lambda _event: self._draw_desktop_diagram())
        self.diagram_canvas.bind("<Button-1>", self._inspect_desktop_diagram)
        self.diagram_canvas.bind("<MouseWheel>", self._wheel_desktop_diagram)
        self.diagram_canvas.bind("<Button-4>", lambda event: self._wheel_desktop_diagram(event, -1))
        self.diagram_canvas.bind("<Button-5>", lambda event: self._wheel_desktop_diagram(event, 1))
        self.diagram_inspector = tk.StringVar(value="Select a point on the diagram to inspect station, slope, and criteria.")
        ttk.Label(
            diagram_tab,
            textvariable=self.diagram_inspector,
            style="Muted.Panel.TLabel",
            wraplength=420,
            justify="left",
        ).grid(row=2, column=0, sticky="ew", pady=(8, 0))

        details_tab.columnconfigure(0, weight=1)
        details_tab.rowconfigure(0, weight=1)
        details_tab.rowconfigure(2, weight=1)
        self.output = tk.Text(
            details_tab,
            wrap="word",
            width=(35 if IS_MACOS else 42),
            height=12,
            font=TEXT_FONT,
            state="disabled",
            background=DARK_FIELD,
            foreground=DARK_TEXT,
            insertbackground=DARK_TEXT,
            selectbackground=DARK_SELECT,
            selectforeground=DARK_TEXT,
            relief="flat",
            borderwidth=8,
        )
        self.output.grid(row=0, column=0, sticky="nsew")

        lookup = ttk.Frame(details_tab, style="Panel.TFrame")
        lookup.grid(row=1, column=0, sticky="ew", pady=(8, 6))
        if IS_MACOS:
            ttk.Label(lookup, text="Lookup station", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
            ttk.Entry(lookup, textvariable=self.vars["lookup_station"], width=8).grid(
                row=0, column=1, sticky="ew", padx=(6, 10), pady=(0, 4)
            )
            ttk.Label(lookup, text="Super", style="Panel.TLabel").grid(row=1, column=0, sticky="w")
            ttk.Entry(lookup, textvariable=self.vars["lookup_super"], width=6).grid(
                row=1, column=1, sticky="ew", padx=(6, 10)
            )
            ttk.Button(lookup, text="Lookup", command=self._compute_lookup).grid(row=0, column=2, rowspan=2)
            lookup.columnconfigure(1, weight=1)
        else:
            ttk.Label(lookup, text="Lookup station", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
            ttk.Entry(lookup, textvariable=self.vars["lookup_station"], width=14).grid(row=0, column=1, padx=(6, 10))
            ttk.Label(lookup, text="Super", style="Panel.TLabel").grid(row=0, column=2, sticky="w")
            ttk.Entry(lookup, textvariable=self.vars["lookup_super"], width=10).grid(row=0, column=3, padx=(6, 10))
            ttk.Button(lookup, text="Lookup", command=self._compute_lookup).grid(row=0, column=4)

        self.table = tk.Text(
            details_tab,
            wrap="none",
            width=(35 if IS_MACOS else 42),
            height=8,
            font=MONO_FONT,
            state="disabled",
            background=DARK_FIELD,
            foreground=DARK_TEXT,
            insertbackground=DARK_TEXT,
            selectbackground=DARK_SELECT,
            selectforeground=DARK_TEXT,
            relief="flat",
            borderwidth=8,
        )
        self.table.grid(row=2, column=0, sticky="nsew")

    def _set_desktop_diagram(self, results: dict, direction: str) -> None:
        self._desktop_diagram_data = super_qa.curve_diagram(results, direction)
        domain = self._desktop_diagram_data.get("domain", {})
        self._desktop_diagram_domain = (float(domain.get("start_ft", 0.0)), float(domain.get("end_ft", 0.0)))
        self._desktop_diagram_station = None
        self.diagram_inspector.set("Select a point on the diagram to inspect station, slope, and criteria.")
        self._draw_desktop_diagram()

    def _reset_desktop_diagram_zoom(self) -> None:
        if not self._desktop_diagram_data:
            return
        domain = self._desktop_diagram_data["domain"]
        self._desktop_diagram_domain = (float(domain["start_ft"]), float(domain["end_ft"]))
        self._draw_desktop_diagram()

    def _zoom_desktop_diagram(self, factor: float, anchor_ratio: float = 0.5) -> None:
        if not self._desktop_diagram_data or not self._desktop_diagram_domain:
            return
        full = self._desktop_diagram_data["domain"]
        full_start, full_end = float(full["start_ft"]), float(full["end_ft"])
        start, end = self._desktop_diagram_domain
        full_span = full_end - full_start
        if full_span <= 0:
            return
        span = min(full_span, max(max(full_span / 120.0, 1.0), (end - start) * factor))
        anchor = start + (end - start) * anchor_ratio
        next_start = anchor - span * anchor_ratio
        next_end = next_start + span
        if next_start < full_start:
            next_start, next_end = full_start, full_start + span
        if next_end > full_end:
            next_start, next_end = full_end - span, full_end
        self._desktop_diagram_domain = (next_start, next_end)
        self._draw_desktop_diagram()

    def _wheel_desktop_diagram(self, event: tk.Event, direction: int | None = None) -> str:
        width = max(1, self.diagram_canvas.winfo_width() - 72)
        ratio = max(0.0, min(1.0, (float(event.x) - 52.0) / width))
        wheel_direction = direction if direction is not None else (-1 if float(event.delta) > 0 else 1)
        self._zoom_desktop_diagram(0.78 if wheel_direction < 0 else 1.28, ratio)
        return "break"

    def _inspect_desktop_diagram(self, event: tk.Event) -> None:
        if not self.last_results or not self._desktop_diagram_domain:
            return
        width = max(1, self.diagram_canvas.winfo_width() - 72)
        ratio = max(0.0, min(1.0, (float(event.x) - 52.0) / width))
        start, end = self._desktop_diagram_domain
        station = start + (end - start) * ratio
        snap_label = ""
        if self.diagram_snap_events.get() and self._desktop_diagram_data.get("snap_points"):
            nearest = min(
                self._desktop_diagram_data["snap_points"],
                key=lambda point: abs(float(point["station_ft"]) - station),
            )
            threshold = max((end - start) * 14.0 / width, 0.5)
            if abs(float(nearest["station_ft"]) - station) <= threshold:
                station = float(nearest["station_ft"])
                snap_label = f" [{'/'.join(nearest['labels'])}]"
        self._desktop_diagram_station = station
        lookup = super_qa.diagram_lookup(self.last_results, self.last_meta.get("curve_direction", "left"), station)
        self.diagram_inspector.set(
            f"{lookup['station']}{snap_label}  |  "+"  |  ".join(
                f"{name.title()} {lane['slope_label']} - {lane['phase']} - {lane['criterion']['reference']}" for name,lane in lookup["lanes"].items())
        )
        self._draw_desktop_diagram()

    def _draw_desktop_diagram(self) -> None:
        canvas = getattr(self, "diagram_canvas", None)
        if canvas is None:
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 260)
        height = max(canvas.winfo_height(), 220)
        left, right, top, bottom = 52.0, width - 20.0, 22.0, height - 42.0
        if not self._desktop_diagram_data or not self._desktop_diagram_domain:
            canvas.create_text(width / 2, height / 2, text="Calculate a curve to view the diagram", fill=DARK_MUTED, font=UI_FONT)
            return
        start, end = self._desktop_diagram_domain
        if end <= start:
            return
        profiles = self._desktop_diagram_data["profiles"]
        if self._desktop_diagram_data.get("section_profiles"):
            profiles={lane["name"]:lane["points"] for lane in self._desktop_diagram_data["section_profiles"]}
        max_slope = max(3.0, max(abs(float(point["slope_pct"])) for lane in profiles.values() for point in lane) * 1.2)

        def x(station: float) -> float:
            return left + (station - start) / (end - start) * (right - left)

        def y(slope: float) -> float:
            return top + (max_slope - slope) / (2 * max_slope) * (bottom - top)

        for index in range(5):
            slope = max_slope - index * max_slope / 2
            py = y(slope)
            canvas.create_line(left, py, right, py, fill="#263b34", dash=(3, 5))
            canvas.create_text(left - 7, py, text=f"{slope:.0f}%", fill=DARK_MUTED, anchor="e", font=MONO_FONT)
        for index in range(5):
            station = start + (end - start) * index / 4
            px = x(station)
            canvas.create_line(px, top, px, bottom, fill="#1c2c27")
            label = Super.format_result_station(self.last_results or {}, station, True).split(".", 1)[0]
            canvas.create_text(px, bottom + 14, text=label, fill=DARK_MUTED, font=(MONO_FONT[0], 8))
        canvas.create_line(left, y(0.0), right, y(0.0), fill="#80918c", width=1)

        for marker in self._desktop_diagram_data.get("markers", []):
            station = float(marker["station_ft"])
            if start <= station <= end and marker["kind"] in {"PC", "PT", "TS", "SC", "CS", "ST", "STATION EQUATION"}:
                px = x(station)
                color = AMBER_ACCENT if marker["kind"] == "STATION EQUATION" else "#69837b"
                canvas.create_line(px, top, px, bottom, fill=color, dash=(3, 3))
                canvas.create_text(px + 3, top + 3, text=marker["label"], fill=color, anchor="nw", font=(MONO_FONT[0], 8))

        for index,(lane,points) in enumerate(profiles.items()):
            color=(DARK_ACCENT,AMBER_ACCENT)[index%2]
            raw = [(float(point["station_ft"]), float(point["slope_pct"])) for point in points]
            if not raw:
                continue
            sampled = [(start, slope_at_station(raw, start))]
            sampled.extend((station, slope) for station, slope in raw if start < station < end)
            sampled.append((end, slope_at_station(raw, end)))
            coords = [coordinate for station, slope in sampled for coordinate in (x(station), y(slope))]
            if len(coords) >= 4:
                canvas.create_line(*coords, fill=color, width=2, smooth=False)
            legend_x=left+index*90
            canvas.create_line(legend_x,bottom+31,legend_x+18,bottom+31,fill=color,width=2)
            canvas.create_text(legend_x+23,bottom+31,text=lane.title(),fill=DARK_MUTED,anchor="w",font=(UI_FONT[0],8))
        if self._desktop_diagram_station is not None and start <= self._desktop_diagram_station <= end:
            px = x(self._desktop_diagram_station)
            canvas.create_line(px, top, px, bottom, fill="#ffffff", width=1)
        self.diagram_range.set(
            f"{Super.format_result_station(self.last_results or {}, start, True)} to "
            f"{Super.format_result_station(self.last_results or {}, end, True)}  -  mouse wheel to zoom"
        )

    def _show_instructions(self) -> None:
        """Show in-app guidance without requiring the user to leave the calculator."""
        dialog = tk.Toplevel(self)
        dialog.title("Superelevation Calculator Instructions")
        dialog.geometry("820x650")
        dialog.minsize(620, 460)
        dialog.transient(self)
        dialog.configure(background=DARK_BG)
        dialog.rowconfigure(0, weight=1)
        dialog.columnconfigure(0, weight=1)

        notebook = ttk.Notebook(dialog)
        notebook.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 6))

        tabs = [
            (
                "Quick start",
                """QUICK START

1. Enter a curve manually, or select a LandXML file first.
2. Confirm the curve direction, PC, PT, and radius. LandXML values are a starting point; verify them against the design.
3. Enter the required values marked with an asterisk: PC station, design speed, and curve radius.
4. Set the roadway choices and any project-specific overrides. Leave an override blank to use the calculated value.
5. Click Compute, review the transition stations and lane slopes, then add the curve to the project when it is ready.
6. Save the project and export a PDF, ORD CSV, or overlay DXF as needed.

The calculator is an engineering aid. Verify applicable criteria, stationing, lane names, and all exported geometry in the project design file before production use.

STATION FORMAT

Station format displays values such as 12+34.56. Turn it off to display raw station values. Station equations are applied when formatting exported and displayed stations.
""",
            ),
            (
                "Inputs",
                """PROJECT AND CURVE

Project name / Route name: Labels used to organize saved work and reports.
Alignment name: Name of the roadway alignment. A loaded LandXML alignment can fill this in.
Curve name: Your label for the curve in the project list and exports.
Curve direction: Choose left or right in the direction of increasing stationing.
LandXML curve: Selects a circular curve found in the loaded LandXML and fills its available geometry values.
PC station *: Point of curvature, where the circular curve begins. This is required.
PT station: Point of tangency, where the circular curve ends. It is recommended for review and length checks.
Manual station equations: Enter one or more equations as Back=Ahead. Use this only when LandXML does not supply the station equations.
Manual internal alignment range: Enter start,end in internal alignment stationing when no LandXML is loaded. It helps validate transition stations.
Design speed (mph) *: Design speed used to determine calculated superelevation criteria.
Curve radius (ft) *: Horizontal circular-curve radius.

ROADWAY

Governing standard: Select the versioned MDOT or TDOT criteria profile before calculating.
Facility / roadway layout: MDOT uses centerline or outside edge. The active TDOT lane-event model is undivided; divided-roadway drawings are recorded but blocked pending a carriageway-specific lane/pivot model.
Area type: Rural, urban, or local. TDOT supports its rural and urban RD11-LR tables; MDOT local uses centerline rotation.
Lane width (ft): Width of one rotated lane. Default is 12 ft.
Lanes rotated: Number of lanes included in the rotation. Default is 2.

OVERRIDES

e (ft/ft): Full superelevation rate. Leave blank for the calculated rate.
Runoff Lr (ft): Length used to transition from normal crown to full superelevation. Leave blank for calculated length.
Runout Lt (ft): Length used to remove adverse crown before runoff. Leave blank for calculated length.
Relative gradient: Maximum rate of cross-slope change used by the calculation. Leave blank for calculated value.
Side friction: Side-friction factor for applicable MDOT formula paths. TDOT table calculations do not consume this override.
Normal crown: Typical tangent cross slope, expressed as a decimal (0.0200 = 2%).
Curve notes: Project-specific notes included with the curve.

Values shown beside override fields are the current calculated values. Enter an override only when it has been checked against the governing project criteria.
""",
            ),
            (
                "LandXML & exports",
                """LANDXML WORKFLOW

Select LandXML loads the first available alignment and reads its alignment name, start station, linear units, line and circular-arc geometry, and station equations. The curve picker lists detected circular curves; selecting one fills available PC, PT, radius, direction, and curve name values.

Add All LandXML Curves creates project curves from every detected circular curve using the shared roadway settings and design speed. Review each created curve before export.

SUPPORTED AND WARNINGS

The application supports line and circular-arc alignment geometry. It warns when it encounters spirals, incomplete or unsupported geometry, ambiguous displayed stations, out-of-range export stations, or missing coordinate context. A warning does not prove the geometry is usable—review it in the design file.

Station equations from LandXML take precedence over the manual station-equation field. If LandXML contains none, manual equations can be used. Use Back=Ahead notation, for example 1000=1100.

EXPORTS

PDF: A calculation and review report for the curves in the project.
ORD CSV: Superelevation rows for OpenRoads Designer. Confirm the target section and lanes exist, lane names match, station formatting/regions are correct, and pivot and transition settings match project requirements.
Overlay DXF: A graphical overlay with lane slope labels, leaders, PC/PT callouts, and curve information. It is not a native civil model.

DXF COORDINATES

LandXML points are interpreted as Northing/Easting. DXF output uses X=Easting and Y=Northing and preserves the source coordinates without reprojection. The app reports coordinate-system metadata when LandXML declares it. In ORD or MicroStation, verify the detected system, working units, project adjustment, origin, placement, rotation, stationing, text scale, and readability.
""",
            ),
        ]
        for title, content in tabs:
            self._add_instruction_tab(notebook, title, content)

        ttk.Button(dialog, text="Close", command=dialog.destroy).grid(row=1, column=0, sticky="e", padx=12, pady=(0, 12))
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

    def _add_instruction_tab(self, notebook: ttk.Notebook, title: str, content: str) -> None:
        """Create a read-only, scrollable help page."""
        page = ttk.Frame(notebook, style="Panel.TFrame", padding=8)
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)
        text = tk.Text(
            page,
            wrap="word",
            state="normal",
            font=TEXT_FONT,
            background=DARK_FIELD,
            foreground=DARK_TEXT,
            insertbackground=DARK_TEXT,
            selectbackground=DARK_SELECT,
            selectforeground=DARK_TEXT,
            relief="flat",
            borderwidth=8,
            padx=8,
            pady=8,
        )
        scrollbar = ttk.Scrollbar(page, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.insert("1.0", content.strip())
        text.configure(state="disabled")
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        notebook.add(page, text=title)

    def _show_advanced_settings(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Advanced Settings")
        dialog.transient(self)
        dialog.configure(background=DARK_PANEL)
        dialog.minsize(520, 460)
        dialog.geometry("660x580")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        advanced_keys = (
            "station_equations",
            "alignment_station_range",
            "e_manual",
            "Lr_manual",
            "Lt_manual",
            "rel_grad",
            "friction",
            "normal_crown",
        )
        temporary = {key: tk.StringVar(value=self.vars[key].get()) for key in advanced_keys}

        shell = ttk.Frame(dialog, style="Panel.TFrame", padding=(14, 14, 8, 8))
        shell.grid(row=0, column=0, sticky="nsew")
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(0, weight=1)
        canvas = tk.Canvas(shell, highlightthickness=0, background=DARK_PANEL)
        scrollbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        body = ttk.Frame(canvas, style="Panel.TFrame")
        window = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        body.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, weight=1)

        row = 0
        ttk.Label(body, text="Advanced Settings", style="Header.TLabel").grid(
            row=row, column=0, columnspan=3, sticky="w"
        )
        row += 1
        ttk.Label(
            body,
            text="Optional values replace automatic criteria. Changes are not used until you select Apply.",
            style="Muted.Panel.TLabel",
            wraplength=570,
            justify="left",
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(4, 12))
        row += 1

        row = self._section(body, row, "Manual Stationing")
        station_fields = [
            ("Station equations (Back=Ahead)", "station_equations"),
            ("Internal alignment range (start,end)", "alignment_station_range"),
        ]
        landxml_equations = bool(self._landxml_data and self._landxml_data.station_equations)
        landxml_range = self._landxml_data is not None
        for label, key in station_fields:
            ttk.Label(body, text=label, style="Panel.TLabel").grid(
                row=row, column=0, sticky="w", padx=(0, 10), pady=4
            )
            entry = ttk.Entry(body, textvariable=temporary[key], width=34)
            entry.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
            if (key == "station_equations" and landxml_equations) or (
                key == "alignment_station_range" and landxml_range
            ):
                entry.configure(state="disabled")
            row += 1
        if landxml_equations or landxml_range:
            ttk.Label(
                body,
                text="LandXML stationing is active; affected manual fields are disabled.",
                style="Muted.Panel.TLabel",
            ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(2, 8))
            row += 1

        row = self._section(body, row, "Criteria Overrides")
        override_fields = [
            ("e (ft/ft)", "e_manual", "e"),
            ("Runoff Lr (ft)", "Lr_manual", "Lr"),
            ("Runout Lt (ft)", "Lt_manual", "Lt"),
            ("Relative gradient", "rel_grad", "rel_grad"),
            ("Side friction", "friction", "friction"),
            ("Normal crown", "normal_crown", "normal_crown"),
        ]
        first_override_entry: ttk.Entry | None = None
        for label, key, computed_key in override_fields:
            ttk.Label(body, text=label, style="Panel.TLabel").grid(
                row=row, column=0, sticky="w", padx=(0, 10), pady=4
            )
            entry = ttk.Entry(body, textvariable=temporary[key], width=18)
            entry.grid(row=row, column=1, sticky="ew", pady=4)
            if first_override_entry is None:
                first_override_entry = entry
            ttk.Label(
                body,
                text=f"Current: {self.computed_vars[computed_key].get()}",
                style="Muted.Panel.TLabel",
            ).grid(row=row, column=2, sticky="w", padx=(10, 0), pady=4)
            row += 1

        buttons = ttk.Frame(dialog, style="Panel.TFrame", padding=(14, 8, 14, 14))
        buttons.grid(row=1, column=0, sticky="ew")
        buttons.columnconfigure(1, weight=1)

        def reset_defaults() -> None:
            for key in advanced_keys:
                temporary[key].set("0.02" if key == "normal_crown" else "")

        def apply_changes() -> None:
            values = {key: variable.get().strip() for key, variable in temporary.items()}
            try:
                self._validate_advanced_values(
                    values,
                    validate_equations=not landxml_equations,
                    validate_range=not landxml_range,
                )
            except ValueError as exc:
                messagebox.showerror("Advanced Settings", str(exc), parent=dialog)
                return
            self._suspend_auto = True
            try:
                for key, value in values.items():
                    self.vars[key].set(value)
            finally:
                self._suspend_auto = False
            self._update_advanced_summary()
            dialog.destroy()
            if self._required_fields_present():
                self._compute(show_errors=True)

        ttk.Button(buttons, text="Reset Defaults", command=reset_defaults).grid(row=0, column=0, sticky="w")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(buttons, text="Apply", command=apply_changes, style="Primary.TButton").grid(row=0, column=3)

        def scroll(event: tk.Event) -> None:
            if event.delta:
                canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

        dialog.bind("<MouseWheel>", scroll)
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.grab_set()
        if first_override_entry is not None:
            first_override_entry.focus_set()

    @staticmethod
    def _validate_advanced_values(
        values: dict[str, str], validate_equations: bool = True, validate_range: bool = True
    ) -> None:
        numeric_fields = {
            "e_manual": ("Manual e", True),
            "Lr_manual": ("Runoff Lr", True),
            "Lt_manual": ("Runout Lt", True),
            "rel_grad": ("Relative gradient", False),
            "friction": ("Side friction", True),
            "normal_crown": ("Normal crown", False),
        }
        for key, (label, allow_zero) in numeric_fields.items():
            text = values.get(key, "").strip()
            if not text:
                continue
            try:
                number = float(text)
            except ValueError as exc:
                raise ValueError(f"{label} must be a number.") from exc
            if not math.isfinite(number) or number < 0 or (not allow_zero and number == 0):
                qualifier = "zero or greater" if allow_zero else "greater than zero"
                raise ValueError(f"{label} must be {qualifier}.")

        if validate_equations:
            for entry in values.get("station_equations", "").split(";"):
                entry = entry.strip()
                if not entry:
                    continue
                if "=" not in entry:
                    raise ValueError("Station equations must use Back=Ahead format.")
                back, ahead = (part.strip() for part in entry.split("=", 1))
                Super.parse_station(back)
                Super.parse_station(ahead)

        range_text = values.get("alignment_station_range", "").strip()
        if validate_range and range_text:
            if "," not in range_text:
                raise ValueError("Internal alignment range must use Start,End format.")
            start_text, end_text = (part.strip() for part in range_text.split(",", 1))
            start = Super.parse_station(start_text)
            end = Super.parse_station(end_text)
            if end < start:
                raise ValueError("Internal alignment range end must be greater than its start.")

    def _update_advanced_summary(self) -> None:
        active: list[str] = []
        for key, label in [
            ("e_manual", "e"),
            ("Lr_manual", "Lr"),
            ("Lt_manual", "Lt"),
            ("rel_grad", "gradient"),
            ("friction", "friction"),
        ]:
            if self.vars[key].get().strip():
                active.append(label)
        crown = self.vars["normal_crown"].get().strip()
        try:
            custom_crown = bool(crown) and not math.isclose(float(crown), 0.02)
        except ValueError:
            custom_crown = bool(crown)
        if custom_crown:
            active.append("crown")
        if self._landxml_data and (self._landxml_data.station_equations or self._landxml_data.station_range()):
            active.append("LandXML stationing")
        elif self.vars["station_equations"].get().strip() or self.vars["alignment_station_range"].get().strip():
            active.append("manual stationing")
        summary = ", ".join(active) if active else "Automatic defaults"
        self.advanced_summary.set(f"Advanced: {summary}")

    def _section(self, parent: ttk.Frame, row: int, title: str) -> int:
        ttk.Label(parent, text=title, style="Header.TLabel").grid(row=row, column=0, columnspan=3, sticky="w", pady=(10, 4))
        return row + 1

    def _field(self, parent: ttk.Frame, row: int, label: str, key: str) -> int:
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(parent, textvariable=self.vars[key], width=22).grid(row=row, column=1, sticky="w", pady=3)
        return row + 1

    def _combo(self, parent: ttk.Frame, row: int, label: str, key: str, values: list[str]) -> int:
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        combo = ttk.Combobox(parent, textvariable=self.vars[key], values=values, state="readonly", width=20)
        combo.grid(row=row, column=1, sticky="w", pady=3)
        if key == "landxml_curve":
            self.landxml_curve_combo = combo
            combo.configure(state="disabled")
        elif key=="area":self.area_combo=combo
        return row + 1

    def _profile_combo(self, parent: ttk.Frame, row: int, label: str) -> int:
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=3
        )
        combo = ttk.Combobox(
            parent,
            textvariable=self.criteria_profile_display,
            values=list(CRITERIA_PROFILE_IDS),
            state="readonly",
            width=48,
        )
        combo.grid(row=row, column=1, columnspan=2, sticky="ew", pady=3)
        combo.bind("<<ComboboxSelected>>", self._on_profile_display_selected)
        self.criteria_profile_combo = combo
        return row + 1

    def _setup_auto_handlers(self) -> None:
        for key, var in self.vars.items():
            if key in {"lookup_station", "lookup_super", "auto_open_pdf"}:
                continue
            var.trace_add("write", self._on_input_change)
        self.vars["landxml_curve"].trace_add("write", self._on_landxml_curve_change)
        self.vars["criteria_profile"].trace_add("write", self._sync_profile_display)
        self.vars["criteria_profile"].trace_add("write", self._on_profile_change)

    def _on_profile_display_selected(self, *_: object) -> None:
        profile_id = CRITERIA_PROFILE_IDS.get(self.criteria_profile_display.get())
        if profile_id and self.vars["criteria_profile"].get() != profile_id:
            self.vars["criteria_profile"].set(profile_id)

    def _sync_profile_display(self, *_: object) -> None:
        profile_id = self.vars["criteria_profile"].get()
        self.criteria_profile_display.set(CRITERIA_PROFILE_LABELS.get(profile_id, profile_id))

    def _on_profile_change(self, *_: object) -> None:
        if self._suspend_auto:
            return
        is_tdot = self.vars["criteria_profile"].get().startswith("tdot")
        is_aashto=self.vars["criteria_profile"].get().startswith("aashto")
        self.area_combo.configure(values=["rural","urban_freeway","urban_high_speed"] if is_aashto else ["rural","urban","local"])
        if is_aashto and self.vars["area"].get() not in {"rural","urban_freeway","urban_high_speed"}:self.vars["area"].set("rural")
        if is_tdot:
            if self.vars["facility"].get() != "undivided":
                self.vars["facility"].set("undivided")
            if self.vars["area"].get() == "local":
                self.vars["area"].set("rural")
        elif self.vars["facility"].get() not in {"centerline", "outside edge"}:
            self.vars["facility"].set("centerline")

    def _on_input_change(self, *_: object) -> None:
        self._update_advanced_summary()
        if self._suspend_auto:
            return
        if self._auto_job:
            self.after_cancel(self._auto_job)
        self._auto_job = self.after(350, self._auto_compute)

    def _required_fields_present(self) -> bool:
        return all(self.vars[key].get().strip() for key in ("pc", "speed", "radius"))

    def _auto_compute(self) -> None:
        self._auto_job = None
        if self._required_fields_present():
            self._compute(show_errors=False)

    def _calculate(self, include_overrides: bool = True) -> dict:
        e_manual = self.vars["e_manual"].get() if include_overrides else ""
        Lr_manual = self.vars["Lr_manual"].get() if include_overrides else ""
        Lt_manual = self.vars["Lt_manual"].get() if include_overrides else ""
        rel_grad = self.vars["rel_grad"].get() if include_overrides else ""
        friction = self.vars["friction"].get() if include_overrides else ""
        normal_crown = self.vars["normal_crown"].get()
        preset=next((p for p in self._landxml_curve_presets if self._curve_preset_label(p)==self.vars["landxml_curve"].get()),None)
        geometry={"source":"LandXML",**{key:preset[key] for key in ("available_entry_tangent_ft","available_exit_tangent_ft")}} if preset else {}
        if (
            self.vars["criteria_profile"].get() == MDOT_PROFILE_ID
            and self.vars["area"].get().strip().lower().startswith("local")
        ):
            self.vars["facility"].set("centerline")
        return Super.calculate_superelevation(
            self.vars["pc"].get(),
            self.vars["pt"].get(),
            self.vars["speed"].get(),
            self.vars["radius"].get(),
            self.vars["facility"].get(),
            self.vars["area"].get(),
            self.vars["lane_width"].get(),
            self.vars["lanes_rotated"].get(),
            e_manual,
            friction,
            rel_grad,
            normal_crown,
            Lr_manual,
            Lt_manual,
            self._station_equations(),
            self._alignment_station_range(),
            self.vars["criteria_profile"].get(),
            profile_options={**{key:var.get() for key,var in self.vars.items()},"e_manual":e_manual,"Lr_manual":Lr_manual,"Lt_manual":Lt_manual,"rel_grad":rel_grad,"friction":friction,
                             "linear_unit":self._landxml_data.linear_unit if self._landxml_data else self.vars["linear_unit"].get(),
                             "geometry_provenance":geometry,
                             "aashto_tables":json.loads(self.vars["aashto_tables"].get()) if self.vars["aashto_tables"].get() else None},
        )

    def _show_aashto_settings(self) -> None:
        dialog=tk.Toplevel(self)
        dialog.title("AASHTO / transition placement")
        dialog.geometry("620x780")
        fields={"max_superelevation":["4","6","8","10","12"],"roadway":["two_way","one_way"],
                "initial_section":["crowned","single_slope"],"rotation_axis":["centerline","left_edge","right_edge"],
                "alignment_type":["circular","spiral"],"runout_placement":["on_tangent","in_spiral"],
                "override_standard_placement":["false","true"],"acknowledge_spiral_override":["false","true"]}
        keys=["max_superelevation","roadway","initial_section","rotation_axis","lane_widths","crown_from_left",
              "left_normal_slope","right_normal_slope","initial_slope","alignment_type","ts","st","runout_placement",
              "runoff_tangent_percent","override_standard_placement","acknowledge_spiral_override"]
        local={key:tk.StringVar(value=self.vars[key].get()) for key in keys}
        for row,key in enumerate(keys):
            ttk.Label(dialog,text=key.replace("_"," ").capitalize()).grid(row=row,column=0,sticky="w",padx=10,pady=5)
            widget=ttk.Combobox(dialog,textvariable=local[key],values=fields[key],state="readonly") if key in fields else ttk.Entry(dialog,textvariable=local[key])
            widget.grid(row=row,column=1,sticky="ew",padx=10)
        dialog.columnconfigure(1,weight=1)
        ttk.Label(dialog,text="AASHTO only: widths in ft; slopes in decimals. Left/right follow increasing station.\nCircular AASHTO requires a runoff percentage. DOT placement requires an override.\nLonger-spiral zero-crown holds require acknowledgement and drainage review.",wraplength=590).grid(row=len(keys)+1,column=0,columnspan=2,padx=10,pady=8)
        def apply():
            for key,var in local.items():self.vars[key].set(var.get())
            dialog.destroy()
        def check_lengths():
            from super_service import required_spiral_lengths
            try:
                values = {**{key:var.get() for key,var in self.vars.items()}, **{key:var.get() for key,var in local.items()}}
                values["aashto_tables"] = json.loads(values["aashto_tables"]) if values.get("aashto_tables") else None
                result = required_spiral_lengths(values)
                messagebox.showinfo("Required spiral lengths", f"Rate e: {result['e']:.4f} ft/ft\nRunoff: {result['Lr']:.3f} ft\nTangent runout: {result['Lt']:.3f} ft\n\nRunout on tangent: {result['minimum_spiral_on_tangent_ft']:.3f} ft minimum spiral\nRunout in spiral: {result['minimum_spiral_in_spiral_ft']:.3f} ft minimum spiral\n\n{result['scope_note']}" + "".join(f"\n\n{warning}" for warning in result["warnings"]), parent=dialog)
            except ValueError as exc:
                messagebox.showerror("Check inputs", str(exc), parent=dialog)
        ttk.Button(dialog,text="Apply",command=apply).grid(row=len(keys)+2,column=0,columnspan=2,pady=8)
        ttk.Button(dialog,text="Required spiral lengths (manual input)",command=check_lengths,
                   state="disabled" if self._landxml_data or not self.vars["criteria_profile"].get().startswith("aashto") else "normal").grid(row=len(keys)+3,column=0,columnspan=2,pady=8)

    def _station_equations(self) -> list[dict]:
        if self._landxml_data and self._landxml_data.station_equations:
            return self._landxml_data.station_equations
        equations: list[dict] = []
        for entry in self.vars["station_equations"].get().split(";"):
            entry = entry.strip()
            if not entry:
                continue
            if "=" not in entry:
                raise ValueError("Manual station equations must use Back=Ahead format, for example 1543+52.403=1233+15.920.")
            back, ahead = (part.strip() for part in entry.split("=", 1))
            equations.append({"staBack": str(Super.parse_station(back)), "staAhead": str(Super.parse_station(ahead))})
        return equations

    def _alignment_station_range(self) -> tuple[float, float] | None:
        if self._landxml_data:
            return self._landxml_data.station_range()
        value = self.vars["alignment_station_range"].get().strip()
        if not value:
            return None
        if "," not in value:
            raise ValueError("Manual internal alignment range must use Start,End format, for example 1417+36,1570+52.")
        start_text, end_text = (part.strip() for part in value.split(",", 1))
        start = Super.parse_station(start_text)
        end = Super.parse_station(end_text)
        if end < start:
            raise ValueError("Manual internal alignment range end must be greater than its start.")
        return start, end

    def _compute(self, show_errors: bool = True) -> None:
        try:
            results = self._calculate(include_overrides=True)
            try:
                baseline = self._calculate(include_overrides=False)
            except ValueError:
                baseline = results
        except ValueError as exc:
            if self.vars["criteria_profile"].get().startswith("aashto"):
                self.last_results=None
                self._diagnostic_findings=getattr(exc,"findings",[]) or [{"code":"INVALID_OR_UNSUPPORTED_INPUT","severity":"block","message":str(exc)}]
                self._write_text(self.output,f"BLOCKED: {exc}")
                self._write_text(self.table,"")
                self._update_overlay_button()
            if show_errors:
                messagebox.showerror("Input Error", str(exc))
            return
        self.last_results = results
        self._diagnostic_findings=[]
        self.last_meta = self._current_meta()
        self._update_computed_values(results, baseline)
        self._render_results(results)
        self._update_overlay_button()

    def _update_computed_values(self, results: dict, baseline: dict) -> None:
        def override_label(key: str, value: str) -> str:
            return "override" if self.vars[key].get().strip() else value

        self.computed_vars["e"].set(f"{results.get('e', 0):.4f} ({override_label('e_manual', baseline.get('e_source', 'auto'))})")
        self.computed_vars["Lr"].set(f"{results.get('Lr', 0):.2f} ft ({'override' if self.vars['Lr_manual'].get().strip() else 'auto'})")
        self.computed_vars["Lt"].set(f"{results.get('Lt', 0):.2f} ft ({'override' if self.vars['Lt_manual'].get().strip() else 'auto'})")
        self.computed_vars["rel_grad"].set(f"{results.get('relative_gradient', 0):.4f}")
        friction = results.get("friction")
        self.computed_vars["friction"].set("n/a" if friction is None else f"{friction:.4f}")
        self.computed_vars["normal_crown"].set(f"{results.get('inputs', {}).get('normal_crown', 0.02):.4f}")

    def _render_results(self, results: dict, lookup_lines: list[str] | None = None) -> None:
        station_format = self.vars["station_format"].get()
        lines = Super.format_results(results, station_format)
        meta = self._current_meta()
        lines.insert(0, f"Route: {meta.get('route_name', 'n/a')}")
        lines.insert(0, f"Project: {meta.get('project_name', 'n/a')}")
        lines.insert(0, f"Curve direction: {meta.get('curve_direction', 'left')}")
        lines.insert(0, f"Curve name: {meta.get('curve_name', 'n/a')}")
        lines.insert(0, f"Alignment: {meta.get('alignment_name', 'n/a')}")
        if self._landxml_data:
            coordinate_system = super_landxml.coordinate_system_summary(self._landxml_data.coordinate_system)
            lines.append("")
            lines.append(
                f"LandXML: {self._landxml_data.alignment_name or 'Unnamed'} | start {Super.format_station(self._landxml_data.start_station, True)} | unit {self._landxml_data.linear_unit or 'unknown'}"
            )
            lines.append(f"Coordinate system: {coordinate_system['display_name']} | DXF preserves source XY")
        if self.vars["curve_notes"].get().strip():
            lines.append("")
            lines.append(f"Curve notes: {self.vars['curve_notes'].get().strip()}")
        if lookup_lines:
            lines = lookup_lines + [""] + lines
        self._write_text(self.output, "\n".join(lines))

        left_rows, right_rows = build_lane_rows(results, meta.get("curve_direction", "left"), station_format)
        table_lines = self._format_lane_table("Left Lane", left_rows) + [""] + self._format_lane_table("Right Lane", right_rows)
        if results.get("section_lanes"):
            table_lines=[]
            for lane in results["section_lanes"]:
                rows=[{**e,"station":Super.format_result_station(results,e["station_ft"],station_format),"slope":super_exports.format_slope_value(e["slope_pct"])} for e in lane["events"]]
                table_lines.extend(self._format_lane_table(lane["lane_name"],rows)+[""])
        self._write_text(self.table, "\n".join(table_lines))
        if lookup_lines is None:
            self.last_meta = meta
            self._set_desktop_diagram(results, meta.get("curve_direction", "left"))

    def _format_lane_table(self, title: str, rows: list[dict]) -> list[str]:
        lines = [title, f"{'Point':<14}{'Station':<16}{'Slope (%)':>10}  Note", "-" * 68]
        for row in rows:
            lines.append(f"{row['label']:<14}{row['station']:<16}{row['slope']:>10}  {row['note']}")
        return lines

    def _write_text(self, widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _compute_lookup(self) -> None:
        if not self.last_results:
            messagebox.showinfo("Lookup", "Run a calculation first.")
            return
        station_text = self.vars["lookup_station"].get().strip()
        super_text = self.vars["lookup_super"].get().strip()
        if not station_text and not super_text:
            messagebox.showinfo("Lookup", "Enter a station, a super value, or both.")
            return
        if self.last_results.get("section_lanes"):
            import super_service
            try:
                answer=super_service.lookup(self.last_results,self.vars["curve_direction"].get(),station_text,super_text)
            except ValueError as exc:
                messagebox.showerror("Lookup",str(exc));return
            lines=["--- Lookup ---"]
            if answer["station"]:
                lines.append(answer["station"]["label"])
                lines.extend(f"{name}: {slope['label']}" for name,slope in answer["station"]["slopes"].items())
                lines.extend(f"{name} relative edges: left {edges['left_elevation_ft']:.4f} ft; right {edges['right_elevation_ft']:.4f} ft" for name,edges in answer["station"].get("edge_elevations",{}).items())
            for name,matches in answer["lanes"].items():
                lines.extend(f"{name}: {m['start']} to {m['end']}" if m["is_range"] else f"{name}: {m['start']}" for m in matches)
            self._render_results(self.last_results,lines);return
        points = lane_profile_points(self.last_results, self.vars["curve_direction"].get())
        lookup_lines = ["--- Lookup ---"]
        reference = float(self.last_results.get("reverse_crown_ft", 0.0))
        if station_text:
            try:
                station = Super.civil_to_internal_station(
                    Super.parse_station(station_text),
                    self.last_results.get("station_equations"),
                    self.last_results.get("alignment_station_range"),
                )
            except ValueError:
                messagebox.showerror("Lookup", "Invalid lookup station.")
                return
            reference = station
            lookup_lines.append(f"Lookup station: {Super.format_result_station(self.last_results, station, True)}")
            for lane in ("left", "right"):
                slope = slope_at_station(points[lane], station)
                lookup_lines.append(
                    f"{lane.title()} lane super: {super_exports.format_slope_label(slope)} ({super_exports.slope_decimal(slope)} ft/ft)"
                )
        if super_text:
            try:
                target = parse_slope_percent(super_text)
            except ValueError:
                messagebox.showerror("Lookup", "Invalid lookup super value. Enter 2, 2%, or 0.02 for two percent.")
                return
            lookup_lines.append(
                f"Lookup super: {super_exports.format_slope_label(target)} ({super_exports.slope_decimal(target)} ft/ft)"
            )
            for lane in ("left", "right"):
                matches = slope_matches(points[lane], target)
                lookup_lines.append(f"{lane.title()} lane:")
                if not matches:
                    lookup_lines.append("  No match")
                    continue

                nearest_index = None
                if station_text:
                    nearest_index = min(
                        range(len(matches)),
                        key=lambda index: self._distance_to_station_range(matches[index], reference),
                    )
                point_indexes = [
                    index for index, (start, end) in enumerate(matches) if abs(end - start) <= 1e-6
                ]
                for index, (start, end) in enumerate(matches):
                    suffix = " (nearest to lookup station)" if index == nearest_index else ""
                    if end - start > 1e-6:
                        rate = abs(float(self.last_results.get("e", 0.0))) * 100.0
                        label = "Full-super range" if abs(abs(target) - rate) <= 1e-6 else "Constant range"
                        lookup_lines.append(
                            f"  {label}: {Super.format_result_station(self.last_results, start, True)} to "
                            f"{Super.format_result_station(self.last_results, end, True)}{suffix}"
                        )
                        continue
                    if len(point_indexes) == 1:
                        label = "Station"
                    elif index == point_indexes[0]:
                        label = "Entering"
                    elif index == point_indexes[-1]:
                        label = "Exiting"
                    else:
                        label = f"Match {point_indexes.index(index) + 1}"
                    lookup_lines.append(
                        f"  {label}: {Super.format_result_station(self.last_results, start, True)}{suffix}"
                    )
        self._render_results(self.last_results, lookup_lines)

    @staticmethod
    def _distance_to_station_range(station_range: tuple[float, float], station: float) -> float:
        start, end = station_range
        if start <= station <= end:
            return 0.0
        return min(abs(station - start), abs(station - end))

    def _current_meta(self) -> dict:
        return {
            "project_name": self.vars["project_name"].get().strip() or "Unnamed project",
            "route_name": self.vars["route_name"].get().strip() or "Unnamed route",
            "alignment_name": self.vars["alignment_name"].get().strip() or "Unnamed alignment",
            "curve_name": self.vars["curve_name"].get().strip() or "Unnamed curve",
            "curve_direction": self.vars["curve_direction"].get().strip() or "left",
        }

    def _shared_curve_inputs(self) -> dict[str, str]:
        return {
            **{key:var.get() for key,var in self.vars.items()},
            "aashto_tables":json.loads(self.vars["aashto_tables"].get()) if self.vars["aashto_tables"].get() else None,
            "criteria_profile": self.vars["criteria_profile"].get().strip(),
            "project_name": self.vars["project_name"].get().strip(),
            "route_name": self.vars["route_name"].get().strip(),
            "speed": self.vars["speed"].get().strip(),
            "facility": self.vars["facility"].get().strip(),
            "area": self.vars["area"].get().strip(),
            "lane_width": self.vars["lane_width"].get().strip(),
            "lanes_rotated": self.vars["lanes_rotated"].get().strip(),
            "e_manual": self.vars["e_manual"].get().strip(),
            "friction": self.vars["friction"].get().strip(),
            "rel_grad": self.vars["rel_grad"].get().strip(),
            "normal_crown": self.vars["normal_crown"].get().strip(),
            "Lr_manual": self.vars["Lr_manual"].get().strip(),
            "Lt_manual": self.vars["Lt_manual"].get().strip(),
            "curve_notes": self.vars["curve_notes"].get().strip(),
        }

    def _collect_vars(self) -> dict:
        data: dict[str, object] = {}
        for key, var in self.vars.items():
            data[key] = bool(var.get()) if isinstance(var, tk.BooleanVar) else var.get()
        return data

    def _new_project(self) -> None:
        self._suspend_auto = True
        self.curves = []
        self.project_path = None
        self.curve_listbox.delete(0, "end")
        self._clear()
        self._suspend_auto = False

    def _clear(self) -> None:
        self._suspend_auto = True
        for key, var in self.vars.items():
            if isinstance(var, tk.BooleanVar):
                var.set(True)
            else:
                var.set("")
        self.vars["curve_direction"].set("left")
        self.vars["criteria_profile"].set(MDOT_PROFILE_ID)
        self.vars["facility"].set("centerline")
        self.vars["area"].set("rural")
        self.vars["lane_width"].set("12")
        self.vars["lanes_rotated"].set("2")
        self.vars["normal_crown"].set("0.02")
        self.vars["landxml_curve"].set("")
        self.last_results = None
        self._diagnostic_findings=[]
        self.last_meta = {}
        for var in self.computed_vars.values():
            var.set("auto")
        self._write_text(self.output, "")
        self._write_text(self.table, "")
        self._desktop_diagram_data = None
        self._desktop_diagram_domain = None
        self._desktop_diagram_station = None
        self.diagram_range.set("Calculate a curve to view its lane profile")
        self.diagram_inspector.set("Select a point on the diagram to inspect station, slope, and criteria.")
        self._draw_desktop_diagram()
        self._landxml_data = None
        self._landxml_curve_presets = []
        self._landxml_source = None
        self.excluded_landxml_curve_indexes = []
        self.landxml_status.set("LandXML: none")
        self._refresh_landxml_curve_picker()
        self._update_advanced_summary()
        self._update_overlay_button()
        self._suspend_auto = False

    def _project_payload(self) -> dict:
        engine_version, project_criteria = super_project.calculation_provenance(self.curves, self.last_results)
        return {
            "version": super_project.PROJECT_VERSION,
            "application_version": APP_VERSION,
            "calculation_engine_version": engine_version,
            "criteria": project_criteria,
            "vars": {**self._collect_vars(),"diagnostic_findings":self._diagnostic_findings},
            "curves": self.curves,
            "last_results": self.last_results,
            "last_meta": self.last_meta,
            "landxml_source": self._landxml_source,
            "excluded_landxml_curve_indexes": self.excluded_landxml_curve_indexes,
        }

    def _save_project(self) -> None:
        dialog_options = {
            "defaultextension": ".json",
            "filetypes": [("Project files", "*.json")],
            "title": "Save Project",
        }
        if self.project_path:
            dialog_options["initialdir"] = os.path.dirname(self.project_path)
            dialog_options["initialfile"] = os.path.basename(self.project_path)
        path = filedialog.asksaveasfilename(**dialog_options)
        if not path:
            return
        try:
            super_project.save_project(path, self._project_payload())
        except (OSError, ValueError) as exc:
            self._show_operation_error("Save Project", "project_save", exc, path)
            return
        self.project_path = path
        messagebox.showinfo("Save Project", f"Saved project to:\n{os.path.basename(path)}")

    def _load_project(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Project files", "*.json")], title="Load Project")
        if not path:
            return
        try:
            data = super_project.load_project(path)
        except (OSError, ValueError) as exc:
            self._show_operation_error("Load Project", "project_load", exc, path)
            return
        self._apply_project(data)
        self.project_path = path
        messagebox.showinfo("Load Project", f"Loaded project from:\n{os.path.basename(path)}")

    def _apply_project(self, data: dict) -> None:
        self._suspend_auto = True
        vars_data = data.get("vars", {}) or {}
        self._diagnostic_findings=vars_data.get("diagnostic_findings",[]) or []
        for key, var in self.vars.items():
            if key not in vars_data:
                continue
            value = vars_data[key]
            if isinstance(var, tk.BooleanVar):
                var.set(bool(value))
            elif key=="aashto_tables" and isinstance(value,dict):
                var.set(json.dumps(value))
            elif value is None:
                var.set("")
            elif isinstance(value, (int, float)) and float(value).is_integer():
                var.set(str(int(value)))
            else:
                var.set(str(value))
        self.curves = data.get("curves", []) or []
        self.curve_listbox.delete(0, "end")
        for curve in self.curves:
            self.curve_listbox.insert("end", super_project.curve_label(curve.get("meta", {}), curve.get("results")))
        self.last_results = data.get("last_results")
        self.last_meta = data.get("last_meta", {}) or {}
        self.excluded_landxml_curve_indexes = data.get("excluded_landxml_curve_indexes", []) or []
        self._landxml_data = None
        self._landxml_curve_presets = []
        self._landxml_source = data.get("landxml_source")
        self._load_landxml_data(show_errors=False, autofill=False)
        if self.last_results:
            self._render_results(self.last_results)
        else:
            self._write_text(self.output, "")
            self._write_text(self.table, "")
            self._desktop_diagram_data = None
            self._desktop_diagram_domain = None
            self._draw_desktop_diagram()
        self._suspend_auto = False
        self._update_overlay_button()

    def _add_curve(self) -> None:
        if not self.last_results:
            messagebox.showinfo("Add Curve", "Run a calculation first.")
            return
        curve = {
            "results": self.last_results,
            "meta": self._current_meta(),
            "notes": self.vars["curve_notes"].get().strip(),
        }
        self.curves.append(curve)
        self.curve_listbox.insert("end", super_project.curve_label(curve["meta"], curve["results"]))
        self.curve_listbox.selection_clear(0, "end")
        self.curve_listbox.selection_set(self.curve_listbox.size() - 1)
        self._update_overlay_button()

    def _add_all_landxml_curves(self) -> None:
        data = self._load_landxml_data(show_errors=True)
        if data is None or not self._landxml_curve_presets:
            messagebox.showinfo("Add All LandXML Curves", "Load a LandXML file with curve geometry first.")
            return
        if not self.vars["speed"].get().strip():
            messagebox.showinfo("Add All LandXML Curves", "Enter a design speed before building all curves.")
            return
        try:
            curves = super_batch.build_curves_from_presets(self._landxml_curve_presets, self._shared_curve_inputs())
        except ValueError as exc:
            if self.vars["criteria_profile"].get().startswith("aashto"):
                self._diagnostic_findings=getattr(exc,"findings",[]) or [{"code":"INVALID_OR_UNSUPPORTED_INPUT","severity":"block","message":str(exc)}]
            messagebox.showerror("Add All LandXML Curves", str(exc))
            return
        self.curves = curves
        self._diagnostic_findings=[]
        self.excluded_landxml_curve_indexes = []
        self.curve_listbox.delete(0, "end")
        for curve in self.curves:
            self.curve_listbox.insert("end", super_project.curve_label(curve.get("meta", {}), curve.get("results")))
        if self.curves:
            self.curve_listbox.selection_clear(0, "end")
            self.curve_listbox.selection_set(0)
            self._load_selected_curve(tk.Event())
        self._update_overlay_button()
        messagebox.showinfo("Add All LandXML Curves", f"Loaded {len(self.curves)} curves for combined export.")

    def _update_selected_curve(self) -> None:
        if not self.last_results:
            messagebox.showinfo("Update Curve", "Run a calculation first.")
            return
        selection = list(self.curve_listbox.curselection())
        if not selection:
            messagebox.showinfo("Update Curve", "Select a curve to update.")
            return
        idx = selection[0]
        curve = {
            "results": self.last_results,
            "meta": self._current_meta(),
            "notes": self.vars["curve_notes"].get().strip(),
        }
        self.curves[idx] = curve
        self.curve_listbox.delete(idx)
        self.curve_listbox.insert(idx, super_project.curve_label(curve["meta"], curve["results"]))
        self.curve_listbox.selection_set(idx)
        self._update_overlay_button()

    def _remove_curve(self) -> None:
        for idx in reversed(self.curve_listbox.curselection()):
            self.curve_listbox.delete(idx)
            if idx < len(self.curves):
                self.curves.pop(idx)
        self._update_overlay_button()

    def _load_selected_curve(self, _event: tk.Event) -> None:
        selection = list(self.curve_listbox.curselection())
        if not selection:
            return
        idx = selection[0]
        if idx >= len(self.curves):
            return
        curve = self.curves[idx]
        results = curve.get("results")
        meta = curve.get("meta", {}) or {}
        if not results:
            return
        inputs = results.get("inputs", {}) or {}
        self._suspend_auto = True
        for key in ("max_superelevation","roadway","initial_section","rotation_axis","lane_widths","crown_from_left","left_normal_slope","right_normal_slope","initial_slope","alignment_type","ts","st","runout_placement","runoff_tangent_percent","override_standard_placement","acknowledge_spiral_override","aashto_tables","linear_unit"):
            if key in inputs:self.vars[key].set(json.dumps(inputs[key]) if key=="aashto_tables" and inputs[key] else str(inputs[key]) if inputs[key] is not None else "")
        self.vars["alignment_name"].set(meta.get("alignment_name", ""))
        self.vars["curve_name"].set(meta.get("curve_name", ""))
        self.vars["curve_direction"].set(meta.get("curve_direction", "left"))
        self.vars["project_name"].set(meta.get("project_name", self.vars["project_name"].get()))
        self.vars["route_name"].set(meta.get("route_name", self.vars["route_name"].get()))
        self.vars["pc"].set(inputs.get("pc", ""))
        self.vars["pt"].set(inputs.get("pt", ""))
        self.vars["speed"].set(str(inputs.get("speed_mph", "")))
        self.vars["radius"].set(str(inputs.get("radius_ft", "")))
        self.vars["criteria_profile"].set(
            inputs.get("criteria_profile", (results.get("calculation_metadata", {}).get("criteria", {}) or {}).get("profile_id", MDOT_PROFILE_ID))
        )
        self.vars["facility"].set(inputs.get("facility", "centerline"))
        self.vars["area"].set(inputs.get("area_type", "rural"))
        self.vars["lane_width"].set(str(inputs.get("lane_width_ft", "")))
        self.vars["lanes_rotated"].set(str(inputs.get("lanes_rotated", "")))
        self.vars["e_manual"].set("" if inputs.get("e_manual") is None else str(inputs.get("e_manual")))
        self.vars["friction"].set(inputs.get("friction_input", ""))
        self.vars["rel_grad"].set(inputs.get("relative_gradient_input", ""))
        self.vars["normal_crown"].set(str(inputs.get("normal_crown", "")))
        self.vars["Lr_manual"].set("" if inputs.get("Lr_manual") is None else str(inputs.get("Lr_manual")))
        self.vars["Lt_manual"].set("" if inputs.get("Lt_manual") is None else str(inputs.get("Lt_manual")))
        self.vars["curve_notes"].set(curve.get("notes", ""))
        self.last_results = results
        self.last_meta = meta
        self._render_results(results)
        self._suspend_auto = False
        self._compute(show_errors=False)

    def _export_curves(self) -> list[dict]:
        if self._diagnostic_findings:
            return []
        if self.curves:
            return self.curves
        if not self.last_results:
            return []
        return [
            {
                "results": self.last_results,
                "meta": self.last_meta or self._current_meta(),
                "notes": self.vars["curve_notes"].get().strip(),
            }
        ]

    def _write_warning_report(self, path: str, warnings: list[str], title: str) -> None:
        if not warnings:
            return
        report_path = f"{os.path.splitext(path)[0]}_{title}_warnings.txt"
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(warnings) + "\n")

    def _select_landxml(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("LandXML", "*.xml"), ("XML files", "*.xml")], title="Select LandXML")
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8")
            source = super_project.make_landxml_source(os.path.basename(path), content)
            super_landxml.parse_landxml_text(content, source["filename"])
        except (OSError, ValueError) as exc:
            self._show_operation_error("LandXML", "landxml", exc, path)
            return
        self.vars["landxml_path"].set(path)
        self._landxml_source = source
        self._load_landxml_data(show_errors=True, autofill=True)
        if self.last_results:
            self._render_results(self.last_results)

    def _load_landxml_data(self, show_errors: bool = False, autofill: bool = False) -> super_landxml.LandXMLData | None:
        path = self.vars["landxml_path"].get().strip()
        if not path and not self._landxml_source:
            self._landxml_data = None
            self._landxml_curve_presets = []
            self.landxml_status.set("LandXML: none")
            self._refresh_landxml_curve_picker()
            self._update_advanced_summary()
            self._update_overlay_button()
            return None
        try:
            if self._landxml_source:
                data = super_landxml.parse_landxml_text(
                    self._landxml_source["content"], self._landxml_source["filename"]
                )
            else:
                data = super_landxml.load_landxml(path)
                content = Path(path).read_text(encoding="utf-8")
                self._landxml_source = super_project.make_landxml_source(os.path.basename(path), content)
        except (OSError, ValueError, ET.ParseError) as exc:
            self._landxml_data = None
            self._landxml_curve_presets = []
            display_name = self._landxml_source["filename"] if self._landxml_source else os.path.basename(path)
            self.landxml_status.set(f"LandXML: failed ({display_name})")
            self._refresh_landxml_curve_picker()
            self._update_advanced_summary()
            self._update_overlay_button()
            if show_errors:
                self._show_operation_error("LandXML", "landxml", exc, path)
            return None
        self._landxml_data = data
        self._landxml_curve_presets = data.curve_records()
        warning_suffix = f" | warnings: {len(data.warnings)}" if data.warnings else ""
        equation_suffix = f" | station equations: {len(data.station_equations)} (auto)" if data.station_equations else ""
        coordinate_system = super_landxml.coordinate_system_summary(data.coordinate_system)
        display_name = self._landxml_source["filename"] if self._landxml_source else os.path.basename(path)
        self.landxml_status.set(
            f"LandXML: {display_name} | {data.alignment_name or 'Unnamed'} | {data.linear_unit or 'unknown'} | "
            f"CRS: {coordinate_system['display_name']} | curves: {len(self._landxml_curve_presets)}{equation_suffix}{warning_suffix}"
        )
        self._refresh_landxml_curve_picker()
        if self._landxml_curve_presets and autofill:
            if not self.vars["route_name"].get().strip():
                self.vars["route_name"].set(data.alignment_name)
            self._apply_landxml_curve(0)
        self._update_advanced_summary()
        self._update_overlay_button()
        return data

    def _curve_preset_label(self, preset: dict) -> str:
        return (
            f"{preset['curve_name']} | {preset['curve_direction']} | "
            f"PC {preset['pc_station_label']} PT {preset['pt_station_label']} | "
            f"R {preset['radius_ft']:.0f} ft"
        )

    def _refresh_landxml_curve_picker(self) -> None:
        if not hasattr(self, "vars"):
            return
        values = [self._curve_preset_label(preset) for preset in self._landxml_curve_presets]
        if hasattr(self, "landxml_curve_combo"):
            self.landxml_curve_combo.configure(values=values, state=("readonly" if values else "disabled"))
        current = self.vars["landxml_curve"].get()
        if current not in values:
            self.vars["landxml_curve"].set(values[0] if values else "")

    def _on_landxml_curve_change(self, *_: object) -> None:
        if self._suspend_auto:
            return
        label = self.vars["landxml_curve"].get().strip()
        if not label or not self._landxml_curve_presets:
            return
        for index, preset in enumerate(self._landxml_curve_presets):
            if self._curve_preset_label(preset) == label:
                self._apply_landxml_curve(index)
                break

    def _apply_landxml_curve(self, index: int) -> None:
        if index < 0 or index >= len(self._landxml_curve_presets):
            return
        preset = self._landxml_curve_presets[index]
        label = self._curve_preset_label(preset)
        self._suspend_auto = True
        self.vars["landxml_curve"].set(label)
        self.vars["alignment_name"].set(preset["alignment_name"])
        self.vars["curve_name"].set(preset["curve_name"])
        self.vars["curve_direction"].set(preset["curve_direction"])
        self.vars["pc"].set(preset["pc_station_label"])
        self.vars["pt"].set(preset["pt_station_label"])
        self.vars["alignment_type"].set(preset.get("alignment_type","circular"))
        self.vars["ts"].set(preset.get("ts_station_label",""))
        self.vars["st"].set(preset.get("st_station_label",""))
        self.vars["linear_unit"].set(preset.get("linear_unit","") or "")
        self.vars["radius"].set(str(int(preset["radius_ft"])) if float(preset["radius_ft"]).is_integer() else str(preset["radius_ft"]))
        self._suspend_auto = False
        if self._required_fields_present():
            self._compute(show_errors=False)

    def _overlay_diagnostics(self) -> tuple[list[str], list[str]]:
        data = self._landxml_data
        if data is None:
            return ["No LandXML is loaded. Select a LandXML file before exporting an overlay DXF."], []
        curves = self._export_curves()
        if not curves:
            return ["No calculated curves are available. Run a calculation, then add or keep the calculated curve for export."], list(data.warnings)
        return super_dxf.overlay_export_issues(curves, data)

    def _overlay_ready(self) -> bool:
        errors, _warnings = self._overlay_diagnostics()
        return not errors

    def _update_overlay_button(self) -> None:
        errors, warnings = self._overlay_diagnostics()
        if hasattr(self, "overlay_button"):
            self.overlay_button.configure(state=("normal" if not errors else "disabled"))
        if hasattr(self, "overlay_status"):
            if errors:
                self.overlay_status.set(f"DXF blocked: {errors[0]} Click Show DXF Issues for details.")
            elif warnings:
                self.overlay_status.set(f"DXF ready with {len(warnings)} warning(s). Click Show DXF Issues to review.")
            else:
                self.overlay_status.set("DXF ready for overlay export.")

    def _show_overlay_issues(self) -> None:
        errors, warnings = self._overlay_diagnostics()
        if not errors and not warnings:
            messagebox.showinfo("DXF Issues", "Overlay DXF is ready. No warnings were found.")
            return
        sections: list[str] = []
        if errors:
            sections.append("DXF export is blocked by:\n\n" + "\n".join(f"• {issue}" for issue in errors))
        if warnings:
            sections.append("Warnings (do not block export):\n\n" + "\n".join(f"• {warning}" for warning in warnings))
        if errors:
            sections.append(
                "To resolve an out-of-range station, extend/re-export the alignment geometry or remove that curve from the export list."
            )
        messagebox.showwarning("DXF Issues" if errors else "DXF Warnings", "\n\n".join(sections))

    def _export_ord_csv(self) -> None:
        curves = self._export_curves()
        if not curves:
            messagebox.showinfo("Export ORD CSV", "Run a calculation first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], title="Save ORD CSV")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                warnings = super_exports.write_ord_csv(handle, curves)
            self._write_warning_report(path, warnings, "ord_csv")
        except Exception as exc:
            self._show_operation_error("Export ORD CSV", "csv_export", exc, path)
            return
        messagebox.showinfo("Export ORD CSV", f"Saved ORD CSV to:\n{os.path.basename(path)}")

    def _export_detail_dxf(self) -> None:
        curves = self._export_curves()
        if not curves:
            messagebox.showinfo("Export Detail DXF", "Run a calculation first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".dxf", filetypes=[("DXF files", "*.dxf")], title="Save Detail DXF")
        if not path:
            return
        try:
            warnings = super_dxf.export_detail_dxf(path, curves)
            self._write_warning_report(path, warnings, "detail_dxf")
        except Exception as exc:
            self._show_operation_error("Export Detail DXF", "detail_dxf_export", exc, path)
            return
        messagebox.showinfo("Export Detail DXF", f"Saved detail DXF to:\n{os.path.basename(path)}")

    def _export_overlay_dxf(self) -> None:
        curves = self._export_curves()
        if not curves:
            messagebox.showinfo("Export Overlay DXF", "Run a calculation first.")
            return
        data = self._load_landxml_data(show_errors=True)
        if data is None:
            return
        if not self._overlay_ready():
            messagebox.showwarning(
                "Export Overlay DXF",
                "Overlay export is disabled until the LandXML geometry is usable and all export stations fall within the alignment range.",
            )
            return
        path = filedialog.asksaveasfilename(defaultextension=".dxf", filetypes=[("DXF files", "*.dxf")], title="Save Overlay DXF")
        if not path:
            return
        try:
            warnings = super_dxf.export_overlay_dxf(path, curves, data)
            self._write_warning_report(path, warnings, "overlay_dxf")
        except Exception as exc:
            self._show_operation_error("Export Overlay DXF", "overlay_dxf_export", exc, path)
            return
        messagebox.showinfo("Export Overlay DXF", f"Saved overlay DXF to:\n{os.path.basename(path)}")

    def _export_pdf(self) -> None:
        curves = self._export_curves()
        if not curves and not self._diagnostic_findings:
            messagebox.showinfo("Export PDF", "Run a calculation first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Save PDF",
        )
        if not path:
            return
        try:
            report={"criteria_profile":self.vars["criteria_profile"].get(),"calculation_engine_version":CALCULATION_ENGINE_VERSION,"findings":self._diagnostic_findings,"status":"block"} if self._diagnostic_findings else None
            super_pdf.export_pdf(path, curves, report)
        except ImportError as exc:
            self._show_operation_error("Missing Dependency", "pdf_export", exc, path)
            return
        except Exception as exc:
            self._show_operation_error("Export PDF", "pdf_export", exc, path)
            return
        messagebox.showinfo("Export PDF", f"Saved PDF to:\n{os.path.basename(path)}")
        if self.vars["auto_open_pdf"].get():
            try:
                super_pdf.open_file(path)
            except Exception:
                messagebox.showwarning("Open PDF", f"Saved PDF to:\n{path}")


if __name__ == "__main__":
    if "--version" in sys.argv:
        print(version_label())
        raise SystemExit(0)
    app_logging.configure_logging()
    app = ModernSuperElevationUI()
    app.mainloop()
