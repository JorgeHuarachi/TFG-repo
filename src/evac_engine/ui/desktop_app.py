"""Tk desktop UI for configuring, running and visualizing EvacEngine."""

from __future__ import annotations

import json
import tkinter as tk
from dataclasses import asdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from ..application import ApplicationService
from ..visualization import EvacuationRenderer, save_result_gif


class EvacEngineDesktopApp(tk.Tk):
    def __init__(self, indoor_path: str | None = None, scenario_path: str | None = None) -> None:
        super().__init__()
        self.title("EvacEngine")
        self.geometry("1280x820")
        self.minsize(1020, 680)
        self.service = ApplicationService()
        self.renderer: EvacuationRenderer | None = None
        self.playing = False
        self.indoor_var = tk.StringVar(value=indoor_path or "")
        self.scenario_var = tk.StringVar(value=scenario_path or "")
        self.level_var = tk.StringVar(value="")
        self.time_step_var = tk.StringVar(value="0.5")
        self.max_steps_var = tk.StringVar(value="120")
        self.seed_var = tk.StringVar(value="1")
        self.output_var = tk.StringVar(value="outputs/evacengine_ui_run")
        self.group_count_var = tk.StringVar(value="0")
        self.algorithm_var = tk.StringVar(value="dijkstra")
        self.cost_var = tk.StringVar(value="shortest_distance")
        self.status_var = tk.StringVar(value="No project loaded")
        self._build()
        if scenario_path:
            self.after(100, self.load_project)

    def _build(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)

        file_bar = ttk.Frame(root)
        file_bar.pack(fill=tk.X)
        ttk.Label(file_bar, text="Indoor").pack(side=tk.LEFT)
        ttk.Entry(file_bar, textvariable=self.indoor_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(file_bar, text="...", width=3, command=self.pick_indoor).pack(side=tk.LEFT)
        ttk.Label(file_bar, text="Scenario").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Entry(file_bar, textvariable=self.scenario_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(file_bar, text="...", width=3, command=self.pick_scenario).pack(side=tk.LEFT)

        main = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        controls = ttk.Frame(main, width=340)
        viewer = ttk.Frame(main)
        main.add(controls, weight=0)
        main.add(viewer, weight=1)

        self._build_controls(controls)
        self._build_viewer(viewer)

        status = ttk.Label(root, textvariable=self.status_var, anchor=tk.W)
        status.pack(fill=tk.X, pady=(6, 0))

    def _build_controls(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)

        run_tab = ttk.Frame(notebook, padding=8)
        config_tab = ttk.Frame(notebook, padding=8)
        log_tab = ttk.Frame(notebook, padding=8)
        notebook.add(run_tab, text="Run")
        notebook.add(config_tab, text="Config")
        notebook.add(log_tab, text="Log")

        ttk.Button(run_tab, text="Load", command=self.load_project).pack(fill=tk.X)
        ttk.Button(run_tab, text="Validate", command=self.validate_project).pack(fill=tk.X, pady=(4, 0))
        ttk.Button(run_tab, text="Apply Config", command=self.apply_config).pack(fill=tk.X, pady=(12, 0))

        transport = ttk.LabelFrame(run_tab, text="Simulation")
        transport.pack(fill=tk.X, pady=10)
        row1 = ttk.Frame(transport)
        row1.pack(fill=tk.X, padx=6, pady=6)
        ttk.Button(row1, text="Step", command=self.step_once).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(row1, text="Play", command=self.toggle_play).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
        ttk.Button(row1, text="Run", command=self.run_full).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(transport, text="Reset", command=self.reset).pack(fill=tk.X, padx=6, pady=(0, 6))
        ttk.Button(transport, text="Save GIF", command=self.save_gif).pack(fill=tk.X, padx=6, pady=(0, 6))

        view_box = ttk.LabelFrame(run_tab, text="View")
        view_box.pack(fill=tk.X)
        ttk.Label(view_box, text="Level").pack(anchor=tk.W, padx=6, pady=(6, 0))
        self.level_combo = ttk.Combobox(view_box, textvariable=self.level_var, state="readonly", values=[])
        self.level_combo.pack(fill=tk.X, padx=6, pady=(0, 6))
        self.level_combo.bind("<<ComboboxSelected>>", lambda _event: self.redraw())

        metrics_box = ttk.LabelFrame(run_tab, text="Metrics")
        metrics_box.pack(fill=tk.BOTH, expand=True, pady=10)
        self.metrics_text = tk.Text(metrics_box, height=10, wrap=tk.WORD)
        self.metrics_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self._labeled_entry(config_tab, "Time step (s)", self.time_step_var)
        self._labeled_entry(config_tab, "Max steps", self.max_steps_var)
        self._labeled_entry(config_tab, "Random seed", self.seed_var)
        self._labeled_entry(config_tab, "First group count", self.group_count_var)
        ttk.Label(config_tab, text="Routing algorithm").pack(anchor=tk.W, pady=(8, 0))
        ttk.Combobox(config_tab, textvariable=self.algorithm_var, state="readonly", values=["dijkstra", "astar", "yen_ksp", "robust_agility"]).pack(fill=tk.X)
        ttk.Label(config_tab, text="Cost policy").pack(anchor=tk.W, pady=(8, 0))
        ttk.Combobox(config_tab, textvariable=self.cost_var, state="readonly", values=["shortest_distance", "minimum_travel_time"]).pack(fill=tk.X)
        ttk.Label(config_tab, text="Output folder").pack(anchor=tk.W, pady=(8, 0))
        output_row = ttk.Frame(config_tab)
        output_row.pack(fill=tk.X)
        ttk.Entry(output_row, textvariable=self.output_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(output_row, text="...", width=3, command=self.pick_output).pack(side=tk.LEFT, padx=(4, 0))

        self.log_text = tk.Text(log_tab, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _build_viewer(self, parent: ttk.Frame) -> None:
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.ax.text(0.5, 0.5, "Load an EvacEngine scenario", ha="center", va="center", transform=self.ax.transAxes)
        self.ax.set_axis_off()
        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        toolbar = NavigationToolbar2Tk(self.canvas, parent, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(fill=tk.X)

    def _labeled_entry(self, parent: ttk.Frame, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label).pack(anchor=tk.W, pady=(8, 0))
        ttk.Entry(parent, textvariable=variable).pack(fill=tk.X)

    def pick_indoor(self) -> None:
        path = filedialog.askopenfilename(title="Select indoor_model.json", filetypes=[("JSON", "*.json")])
        if path:
            self.indoor_var.set(path)

    def pick_scenario(self) -> None:
        path = filedialog.askopenfilename(title="Select scenario_model.json", filetypes=[("JSON", "*.json")])
        if path:
            self.scenario_var.set(path)

    def pick_output(self) -> None:
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self.output_var.set(path)

    def load_project(self) -> None:
        try:
            snapshot = self.service.load(self.indoor_var.get() or None, self.scenario_var.get())
            assert self.service.model is not None and self.service.scenario is not None
            self.renderer = EvacuationRenderer(self.service.model.topology)
            self._load_config_from_scenario()
            self._load_levels()
            self._show_snapshot(snapshot)
            self.redraw()
            self._log("Loaded project")
        except Exception as exc:
            messagebox.showerror("EvacEngine", str(exc))

    def validate_project(self) -> None:
        try:
            data = self.service.validate(self.indoor_var.get() or None, self.scenario_var.get())
            self._log_json(data)
            self.status_var.set("Validation OK")
        except Exception as exc:
            messagebox.showerror("EvacEngine", str(exc))

    def apply_config(self) -> None:
        try:
            snapshot = self.service.apply_runtime_settings(
                time_step_s=float(self.time_step_var.get()),
                max_steps=int(self.max_steps_var.get()),
                random_seed=int(self.seed_var.get()),
                output_folder=self.output_var.get(),
                routing_algorithm=self.algorithm_var.get(),
                cost_policy=self.cost_var.get(),
                first_group_count=int(self.group_count_var.get()) if self.group_count_var.get().strip() else None,
            )
            assert self.service.model is not None
            self.renderer = EvacuationRenderer(self.service.model.topology)
            self._show_snapshot(snapshot)
            self.redraw()
            self._log("Runtime configuration applied")
        except Exception as exc:
            messagebox.showerror("EvacEngine", str(exc))

    def step_once(self) -> None:
        try:
            self._show_snapshot(self.service.step())
            self.redraw()
        except Exception as exc:
            messagebox.showerror("EvacEngine", str(exc))

    def toggle_play(self) -> None:
        self.playing = not self.playing
        if self.playing:
            self._play_tick()

    def _play_tick(self) -> None:
        if not self.playing:
            return
        try:
            if self.service.model and any(agent.status == "active" for agent in self.service.model.agents):
                self._show_snapshot(self.service.step())
                self.redraw()
                self.after(120, self._play_tick)
            else:
                self.playing = False
        except Exception as exc:
            self.playing = False
            messagebox.showerror("EvacEngine", str(exc))

    def run_full(self) -> None:
        try:
            result = self.service.run(self.output_var.get() or None)
            self._log_json({"metrics": result.metrics, "outputDir": str(result.output_dir) if result.output_dir else None})
            self._show_snapshot(self.service.snapshot())
            self.redraw()
        except Exception as exc:
            messagebox.showerror("EvacEngine", str(exc))

    def reset(self) -> None:
        try:
            self._show_snapshot(self.service.reset())
            self.redraw()
        except Exception as exc:
            messagebox.showerror("EvacEngine", str(exc))

    def save_gif(self) -> None:
        try:
            if not self.service.model:
                raise RuntimeError("Load a scenario before saving a GIF")
            output = filedialog.asksaveasfilename(
                title="Save simulation GIF",
                defaultextension=".gif",
                filetypes=[("GIF", "*.gif")],
            )
            if not output:
                return
            result = self.service.run(self.output_var.get() or None)
            path = save_result_gif(
                self.service.model.topology,
                result,
                output,
                level=self.level_var.get() or None,
                fps=8,
                max_frames=160,
            )
            self._show_snapshot(self.service.snapshot())
            self.redraw()
            self._log(f"GIF saved: {path}")
        except Exception as exc:
            messagebox.showerror("EvacEngine", str(exc))

    def redraw(self) -> None:
        if not self.renderer or not self.service.model:
            return
        level = self.level_var.get() or None
        self.renderer.draw_model_frame(self.ax, self.service.model, level)
        self.canvas.draw_idle()
        self._show_metrics()

    def _load_config_from_scenario(self) -> None:
        scenario = self.service.scenario
        if scenario is None:
            return
        self.time_step_var.set(str(scenario.simulation_config.get("timeStepS", 0.5)))
        self.max_steps_var.set(str(scenario.simulation_config.get("maxSteps", 120)))
        self.seed_var.set(str(scenario.simulation_config.get("randomSeed", 1)))
        self.output_var.set(str(scenario.outputs.get("outputFolder", "outputs/evacengine_ui_run")))
        self.algorithm_var.set(str(scenario.routing.get("algorithm", "dijkstra")))
        self.cost_var.set(str(scenario.routing.get("costPolicy", "shortest_distance")))
        first_count = scenario.groups[0].get("count") if scenario.groups else 0
        self.group_count_var.set(str(first_count))

    def _load_levels(self) -> None:
        if not self.service.indoor:
            return
        levels = sorted(self.service.indoor.levels_by_id)
        self.level_combo.configure(values=[""] + levels)
        self.level_var.set(levels[0] if levels else "")

    def _show_snapshot(self, snapshot) -> None:
        self.status_var.set(
            f"Loaded={snapshot.loaded} | step={snapshot.step} | agents={snapshot.metrics.get('agentCount', 0)} | evacuated={snapshot.metrics.get('evacuated', 0)}"
        )
        self._show_metrics()

    def _show_metrics(self) -> None:
        self.metrics_text.delete("1.0", tk.END)
        if self.service.model:
            self.metrics_text.insert(tk.END, json.dumps(self.service.model.metrics(), ensure_ascii=True, indent=2))

    def _log(self, message: str) -> None:
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def _log_json(self, data) -> None:
        self._log(json.dumps(data, ensure_ascii=True, indent=2))


def run_desktop_app(indoor_path: str | None = None, scenario_path: str | None = None) -> None:
    app = EvacEngineDesktopApp(indoor_path, scenario_path)
    app.mainloop()
