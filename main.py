from __future__ import annotations

import argparse
import math
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from performance_tuning import install

install()

from evolve_engine import ACTIONS, Robot, World

BG="#071018"; PANEL="#0c1720"; PANEL2="#101f2b"; TEXT="#eaf6fb"; MUTED="#8ba4b2"; ACCENT="#6be0b4"; WARN="#ffd166"; DANGER="#ff7180"; BLUE="#64b5ff"; FOOD="#90e59a"


class EvolveApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("EVOLVE — Artificial Life Laboratory")
        root.geometry("1550x940")
        root.minsize(1240, 780)
        root.configure(bg=BG)
        self.world = World()
        self.running = False  # Start with exactly the two founders visible.
        self.fast = False
        self.selected_id: int | None = None
        self.show_rays = True
        self.show_labels = False
        self.show_scents = True
        self.last = time.perf_counter()
        self.fps = 0.0
        self.frame = 0
        self.lineage_archive: dict[int, dict] = {}
        self.build()
        self.bind_keys()
        self.set_status("● READY • 2 FOUNDERS", WARN)
        self.loop()

    def set_status(self, text: str, foreground: str) -> None:
        self.status.configure(text=text, foreground=foreground)

    def archive_population(self) -> None:
        for robot in self.world.population:
            self.lineage_archive[robot.id] = {
                "id": robot.id,
                "sex": robot.sex,
                "generation": robot.generation,
                "parent_ids": robot.parent_ids,
                "fitness": robot.fitness,
                "offspring": robot.offspring,
            }
        if len(self.lineage_archive) > 5000:
            keep = sorted(
                self.lineage_archive.values(),
                key=lambda item: (item["generation"], item["id"]),
                reverse=True,
            )[:5000]
            self.lineage_archive = {item["id"]: item for item in keep}

    def build(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", padding=7, font=("Segoe UI", 9, "bold"))
        style.configure("TEntry", padding=5)
        style.configure("TNotebook", background=PANEL)
        style.configure("TNotebook.Tab", padding=(10, 5))
        style.configure("TLabel", background=PANEL, foreground=TEXT)

        header = tk.Frame(self.root, bg=PANEL, height=68)
        header.pack(fill="x")
        ttk.Label(header, text="EVOLVE", font=("Segoe UI", 21, "bold"), background=PANEL, foreground="#fff").pack(side="left", padx=20, pady=12)
        ttk.Label(header, text="2D ARTIFICIAL LIFE • DOG-INSPIRED COGNITION • EVOLUTIONARY LAB", background=PANEL, foreground=MUTED, font=("Segoe UI", 9)).pack(side="left", pady=20)
        self.status = ttk.Label(header, text="● READY • 2 FOUNDERS", background=PANEL, foreground=WARN, font=("Segoe UI", 10, "bold"))
        self.status.pack(side="right", padx=20)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=12)
        scene = tk.Frame(body, bg=BG)
        scene.pack(side="left", fill="both", expand=True)
        side = tk.Frame(body, bg=PANEL, width=390)
        side.pack(side="right", fill="y", padx=(12, 0))

        self.canvas = tk.Canvas(scene, bg="#08131b", highlightthickness=1, highlightbackground="#1e3541")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.select_robot)
        self._controls(side)
        self._tabs(side)

    def _controls(self, panel: tk.Frame) -> None:
        box = tk.Frame(panel, bg=PANEL)
        box.pack(fill="x", padx=12, pady=9)
        for text, command in [
            ("⏯  START / PAUSE", self.toggle),
            ("⏭  FORCE NEXT GENERATION", self.next_generation),
            ("↻  RESET EXPERIMENT", self.reset),
            ("⚡  FAST MODE", self.toggle_fast),
            ("💾  SAVE WORLD SNAPSHOT", self.save_snapshot),
            ("🧬  EXPORT SELECTED GENOME", self.export_genome),
        ]:
            ttk.Button(box, text=text, command=command).pack(fill="x", pady=2)

        ttk.Label(box, text="EXPERIMENTER POWERS", background=PANEL, foreground="#fff", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(10, 4))
        for text, command in [
            ("+ FOOD AT CURSOR", self.add_food),
            ("+ WATER AT CURSOR", self.add_water),
            ("+ HAZARD AT CURSOR", self.add_hazard),
            ("+ PREDATOR AT CURSOR", self.add_predator),
            ("REWARD SELECTED +10", lambda: self.reward(10)),
            ("PUNISH SELECTED −10", lambda: self.reward(-10)),
            ("HEAL SELECTED", self.heal),
            ("BOOST SELECTED", self.boost),
            ("☠ KILL SELECTED", self.kill),
            ("TELEPORT SELECTED", self.teleport),
        ]:
            ttk.Button(box, text=text, command=command).pack(fill="x", pady=1)

        self.rays = tk.BooleanVar(value=True)
        self.labels = tk.BooleanVar(value=False)
        self.scents = tk.BooleanVar(value=True)
        for text, variable in [
            ("Show evolved sensory rays", self.rays),
            ("Show robot labels", self.labels),
            ("Show scent trails", self.scents),
        ]:
            ttk.Checkbutton(box, text=text, variable=variable, command=self.sync).pack(anchor="w")

        ttk.Label(box, text="EXPERIMENT", background=PANEL, foreground="#fff", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(9, 4))
        self.vars: dict[str, tk.StringVar] = {}
        for key in ["population", "food", "water", "hazards", "predators", "mutation", "episode"]:
            row = tk.Frame(box, bg=PANEL)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=key, background=PANEL, foreground=MUTED).pack(side="left")
            value = tk.StringVar(value=str(self.world.experiment[key]))
            ttk.Entry(row, textvariable=value, width=10).pack(side="right")
            self.vars[key] = value
        ttk.Button(box, text="APPLY + RESET", command=self.apply).pack(fill="x", pady=(5, 2))

    def _tabs(self, panel: tk.Frame) -> None:
        notebook = ttk.Notebook(panel)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)
        brain_tab = tk.Frame(notebook, bg=PANEL)
        lineage_tab = tk.Frame(notebook, bg=PANEL)
        analytics_tab = tk.Frame(notebook, bg=PANEL)
        notebook.add(brain_tab, text="BRAIN")
        notebook.add(lineage_tab, text="LINEAGE")
        notebook.add(analytics_tab, text="ANALYTICS")

        ttk.Label(brain_tab, text="LIVE BRAIN MAP", background=PANEL, foreground="#fff", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8, pady=(8, 4))
        self.brain_canvas = tk.Canvas(brain_tab, height=230, bg=PANEL2, highlightthickness=0)
        self.brain_canvas.pack(fill="x", padx=8, pady=4)
        self.inspector = tk.Text(brain_tab, height=18, bg=PANEL2, fg=TEXT, relief="flat", state="disabled", font=("Consolas", 8), padx=8, pady=8)
        self.inspector.pack(fill="both", expand=True, padx=8, pady=6)

        ttk.Label(lineage_tab, text="FAMILY TREE", background=PANEL, foreground="#fff", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8, pady=(8, 4))
        self.lineage = tk.Canvas(lineage_tab, height=260, bg=PANEL2, highlightthickness=0)
        self.lineage.pack(fill="x", padx=8, pady=4)
        self.lineage_text = tk.Text(lineage_tab, height=12, bg=PANEL2, fg=TEXT, relief="flat", state="disabled", font=("Consolas", 8), padx=8, pady=8)
        self.lineage_text.pack(fill="both", expand=True, padx=8, pady=6)

        ttk.Label(analytics_tab, text="MACRO ECOSYSTEM", background=PANEL, foreground="#fff", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8, pady=(8, 4))
        self.graph = tk.Canvas(analytics_tab, height=260, bg=PANEL2, highlightthickness=0)
        self.graph.pack(fill="x", padx=8, pady=4)
        self.metrics = tk.Text(analytics_tab, height=14, bg=PANEL2, fg=TEXT, relief="flat", state="disabled", font=("Consolas", 8), padx=8, pady=8)
        self.metrics.pack(fill="both", expand=True, padx=8, pady=6)

    def bind_keys(self) -> None:
        self.root.bind("<space>", lambda _event: self.toggle())
        self.root.bind("<f>", lambda _event: self.toggle_fast())
        self.root.bind("<n>", lambda _event: self.next_generation())
        self.root.bind("<r>", lambda _event: self.reset())
        self.root.bind("<Escape>", lambda _event: self.root.destroy())

    def sync(self) -> None:
        self.show_rays = self.rays.get()
        self.show_labels = self.labels.get()
        self.show_scents = self.scents.get()

    def toggle(self) -> None:
        self.running = not self.running
        self.set_status("● RUNNING" if self.running else "● PAUSED", ACCENT if self.running else WARN)

    def toggle_fast(self) -> None:
        self.fast = not self.fast
        self.set_status("● FAST MODE" if self.fast and self.running else ("● PAUSED" if not self.running else "● RUNNING"), WARN if self.fast and not self.running else ACCENT)

    def reset(self) -> None:
        self.world.reset()
        self.lineage_archive.clear()
        self.selected_id = None
        self.running = False
        self.set_status("● READY • 2 FOUNDERS", WARN)

    def apply(self) -> None:
        try:
            values = {}
            for key, variable in self.vars.items():
                values[key] = float(variable.get()) if key == "mutation" else int(variable.get())
            self.world.configure(**values)
            self.reset()
        except ValueError:
            messagebox.showerror("Invalid settings", "Enter valid numeric experiment settings.")

    def next_generation(self) -> None:
        self.running = False
        start = self.world.generation
        self.archive_population()
        limit = self.world.experiment["episode"] + 20
        for _ in range(max(1, limit)):
            self.world.step(1)
            if self.world.generation != start:
                break
        self.archive_population()
        self.running = False
        self.set_status(f"● GENERATION {self.world.generation} • PAUSED", WARN)

    def cursor(self) -> tuple[float, float]:
        cx = self.root.winfo_pointerx() - self.canvas.winfo_rootx()
        cy = self.root.winfo_pointery() - self.canvas.winfo_rooty()
        return self.canvas_to_world(cx, cy)

    def add_food(self) -> None:
        self.world.spawn_food(*self.cursor())

    def add_water(self) -> None:
        self.world.spawn_water(*self.cursor())

    def add_hazard(self) -> None:
        self.world.spawn_hazard(*self.cursor())

    def add_predator(self) -> None:
        self.world.spawn_predator(*self.cursor())

    def selected(self) -> Robot | None:
        return next((robot for robot in self.world.population if robot.id == self.selected_id), None)

    def reward(self, amount: float) -> None:
        robot = self.selected()
        if robot:
            self.world.reward_robot(robot.id, amount)

    def heal(self) -> None:
        robot = self.selected()
        if robot:
            self.world.heal_robot(robot.id)

    def boost(self) -> None:
        robot = self.selected()
        if robot:
            self.world.boost_robot(robot.id)

    def kill(self) -> None:
        robot = self.selected()
        if robot:
            self.world.kill_robot(robot.id)

    def teleport(self) -> None:
        robot = self.selected()
        if robot:
            self.world.teleport_robot(robot.id, *self.cursor())

    def export_genome(self) -> None:
        robot = self.selected()
        if not robot:
            return
        path = filedialog.asksaveasfilename(defaultextension=".genome.json", filetypes=[("Genome JSON", "*.genome.json")])
        if path:
            World.save_genome(robot, path)

    def save_snapshot(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            self.world.save_snapshot(path)

    def canvas_to_world(self, x: float, y: float) -> tuple[float, float]:
        return x / max(1, self.canvas.winfo_width()) * self.world.width, y / max(1, self.canvas.winfo_height()) * self.world.height

    def world_to_canvas(self, x: float, y: float) -> tuple[float, float]:
        return x / self.world.width * max(1, self.canvas.winfo_width()), y / self.world.height * max(1, self.canvas.winfo_height())

    def select_robot(self, event: tk.Event) -> None:
        x, y = self.canvas_to_world(event.x, event.y)
        robot = min(self.world.population, key=lambda candidate: (candidate.x - x) ** 2 + (candidate.y - y) ** 2, default=None)
        if robot and math.hypot(robot.x - x, robot.y - y) < 35:
            self.selected_id = robot.id

    def draw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width, height = max(1, canvas.winfo_width()), max(1, canvas.winfo_height())
        for gx in range(0, self.world.width + 1, 50):
            x, _ = self.world_to_canvas(gx, 0)
            canvas.create_line(x, 0, x, height, fill="#10232e")
        for gy in range(0, self.world.height + 1, 50):
            _, y = self.world_to_canvas(0, gy)
            canvas.create_line(0, y, width, y, fill="#10232e")

        if self.show_scents:
            for scent in self.world.scents[::4]:
                x, y = self.world_to_canvas(scent.x, scent.y)
                radius = max(2, 7 * scent.strength)
                canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline=FOOD if scent.kind == "food" else DANGER)

        for shelter in self.world.shelters:
            x, y = self.world_to_canvas(shelter.x, shelter.y)
            radius = shelter.radius / self.world.width * width
            canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline="#355466", dash=(3, 3))

        for hazard in self.world.hazards:
            x, y = self.world_to_canvas(hazard.x, hazard.y)
            radius = hazard.radius / self.world.width * width
            canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill="#351821", outline=DANGER, width=2)
            canvas.create_text(x, y, text="!", fill=DANGER)

        for food in self.world.food:
            x, y = self.world_to_canvas(food.x, food.y)
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=FOOD, outline="")
        for water in self.world.water:
            x, y = self.world_to_canvas(water.x, water.y)
            canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill=BLUE, outline="")
        for predator in self.world.predators:
            x, y = self.world_to_canvas(predator.x, predator.y)
            canvas.create_polygon(x - 10, y + 8, x, y - 10, x + 10, y + 8, fill=DANGER, outline="#ff98a5")

        for robot in self.world.population:
            x, y = self.world_to_canvas(robot.x, robot.y)
            selected = robot.id == self.selected_id
            radius = 9 * robot.genome.body_size
            body = "#e5fff4" if selected else ("#7bbcf2" if robot.sex == "male" else "#e78bb7")
            if selected:
                canvas.create_oval(x - radius - 10, y - radius - 10, x + radius + 10, y + radius + 10, outline=ACCENT, width=2)
            hx = x + (radius + 5) * math.cos(robot.angle)
            hy = y + (radius + 5) * math.sin(robot.angle)
            canvas.create_line(x, y, hx, hy, fill=TEXT, width=2)
            canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=body, outline="#061018")
            if self.show_labels:
                canvas.create_text(x, y - radius - 9, text=f"#{robot.id} {robot.sex[0].upper()} G{robot.generation}", fill=MUTED, font=("Segoe UI", 7))
            if selected and self.show_rays:
                for ray in robot.genome.rays:
                    ex, ey = self.world_to_canvas(robot.x + math.cos(robot.angle + ray.angle) * ray.length, robot.y + math.sin(robot.angle + ray.angle) * ray.length)
                    canvas.create_line(x, y, ex, ey, fill="#2b6678", dash=(3, 5))

    def bars(self, canvas: tk.Canvas, values: list[float], labels: list[str]) -> None:
        canvas.delete("all")
        width, height = max(1, canvas.winfo_width()), max(1, canvas.winfo_height())
        gap = 8
        count = len(values)
        bar_width = max(18, (width - gap * (count + 1)) / count)
        for index, (value, label) in enumerate(zip(values, labels)):
            x = gap + index * (bar_width + gap)
            bar_height = max(2, (height - 55) * max(0, min(1, value)))
            canvas.create_rectangle(x, height - 25 - bar_height, x + bar_width, height - 25, fill=ACCENT, outline="")
            canvas.create_text(x + bar_width / 2, height - 14, text=label, fill=MUTED, font=("Segoe UI", 8))
            canvas.create_text(x + bar_width / 2, height - 31 - bar_height, text=f"{value:.2f}", fill=TEXT, font=("Consolas", 8))

    def update_brain(self) -> None:
        robot = self.selected()
        if not robot:
            self.brain_canvas.delete("all")
            self.inspector.configure(state="normal")
            self.inspector.delete("1.0", "end")
            self.inspector.insert("1.0", "Select a robot to map its live brain.")
            self.inspector.configure(state="disabled")
            return
        state, codes, cue, _ = robot.observe(self.world)
        hunger, thirst, fatigue, fear, curiosity, social, sleepiness = robot.drives(self.world)
        self.bars(self.brain_canvas, [hunger, thirst, fatigue, fear, curiosity, social, sleepiness], ["HUN", "THI", "FAT", "FEAR", "CUR", "SOC", "SLEEP"])
        brain = robot.brain
        values = brain.values(state)
        preferred = ACTIONS[max(range(len(values)), key=values.__getitem__)]
        lines = [
            f"ROBOT #{robot.id} • {robot.sex.upper()} • GEN {robot.generation}",
            f"age={robot.age} health={robot.health:.1f} energy={robot.energy:.1f}/{robot.genome.effective_max_energy():.1f}",
            f"hydration={robot.hydration:.1f}/{robot.genome.effective_max_hydration():.1f}",
            f"fitness={robot.fitness:.2f} food={robot.food_eaten} water={robot.water_found} damage={robot.damage_taken:.1f}",
            "", "SENSORY ATTENTION", f"cue={cue} codes={codes}", "", "BRAIN / MEMORY",
            f"states={len(brain.q)} associations={len(brain.associations)}",
            f"working={len(brain.working)} episodic={len(brain.episodic)}",
            f"confidence={brain.confidence:.2f} stress={brain.stress:.2f} arousal={brain.arousal:.2f}",
            f"valence={brain.valence:.2f} exploration={brain.epsilon:.2f}",
            f"preferred action={preferred}", "", "EVOLVABLE BODY",
            f"size={robot.genome.body_size:.2f} speed={robot.genome.speed:.2f} efficiency={robot.genome.efficiency:.2f}",
            f"learning α={robot.genome.learning_rate:.3f} discount γ={robot.genome.discount:.3f} memory={robot.genome.memory_capacity}",
            f"rays={[(round(ray.angle, 2), round(ray.length)) for ray in robot.genome.rays]}",
        ]
        self.inspector.configure(state="normal")
        self.inspector.delete("1.0", "end")
        self.inspector.insert("1.0", "\n".join(lines))
        self.inspector.configure(state="disabled")

    def lineage_lookup(self, robot_id: int) -> dict | None:
        current = next((robot for robot in self.world.population if robot.id == robot_id), None)
        if current:
            return {"id": current.id, "sex": current.sex, "generation": current.generation, "parent_ids": current.parent_ids, "fitness": current.fitness, "offspring": current.offspring}
        return self.lineage_archive.get(robot_id)

    def update_lineage(self) -> None:
        robot = self.selected()
        self.lineage.delete("all")
        self.lineage_text.configure(state="normal")
        self.lineage_text.delete("1.0", "end")
        if not robot:
            self.lineage_text.insert("1.0", "Select an evolved robot to inspect its lineage.")
            self.lineage_text.configure(state="disabled")
            return
        chain: list[dict] = [self.lineage_lookup(robot.id) or {}]
        seen = {robot.id}
        while len(chain) < 6:
            parent_ids = chain[-1].get("parent_ids", (0, 0))
            parent_id = next((parent for parent in parent_ids if parent), 0)
            parent = self.lineage_lookup(parent_id) if parent_id else None
            if not parent or parent["id"] in seen:
                break
            chain.append(parent)
            seen.add(parent["id"])
        width = max(1, self.lineage.winfo_width())
        gap = min(105, max(65, (width - 80) / max(1, len(chain) - 1)))
        y = 48
        for index, node in enumerate(chain):
            x = 35 + index * gap
            fill = "#7bbcf2" if node.get("sex") == "male" else "#e78bb7"
            self.lineage.create_oval(x - 18, y - 18, x + 18, y + 18, fill=fill, outline=ACCENT if index == 0 else "#2a4351", width=2)
            self.lineage.create_text(x, y + 34, text=f"#{node.get('id')}\nG{node.get('generation')}", fill=TEXT, font=("Segoe UI", 8))
            if index + 1 < len(chain):
                self.lineage.create_line(x + 18, y, x + gap - 18, y, fill="#3f6878", arrow="last")
        lines = [f"SELECTED #{robot.id}", f"parents={robot.parent_ids}", f"generation={robot.generation}", f"offspring={robot.offspring}", "", "ANCESTRAL PATH"]
        lines += [f"#{node.get('id')}  G{node.get('generation')}  {node.get('sex')}  fitness={node.get('fitness', 0):.2f}" for node in chain]
        self.lineage_text.insert("1.0", "\n".join(lines))
        self.lineage_text.configure(state="disabled")

    def update_graph(self) -> None:
        canvas = self.graph
        canvas.delete("all")
        width, height = max(1, canvas.winfo_width()), max(1, canvas.winfo_height())
        history = self.world.history[-50:]
        if not history:
            return
        series = [("fitness", lambda row: row.get("best_fitness", 0), ACCENT), ("food", lambda row: row.get("food", 0), FOOD), ("predators", lambda row: row.get("predators", 0), DANGER)]
        maximum = max(1, max(max(abs(fn(row)) for row in history) for _, fn, _ in series))
        step = (width - 45) / max(1, len(history) - 1)
        for index, (name, fn, color) in enumerate(series):
            points: list[float] = []
            for i, row in enumerate(history):
                points += [45 + i * step, height - 20 - (fn(row) / maximum) * (height - 45)]
            canvas.create_line(*points, fill=color, width=2)
            canvas.create_text(8, 20 + index * 20, text=name, anchor="w", fill=color, font=("Segoe UI", 8))
        canvas.create_line(40, 10, 40, height - 20, fill="#36515e")
        canvas.create_line(40, height - 20, width, height - 20, fill="#36515e")

    def update_metrics(self) -> None:
        summary = self.world.summary()
        males = sum(robot.sex == "male" for robot in self.world.population)
        females = sum(robot.sex == "female" for robot in self.world.population)
        lines = [
            f"GENERATION       {summary['generation']}",
            f"ALIVE            {summary['alive']:>3}/{summary['population']}",
            f"MALE/FEMALE      {males}/{females}",
            f"BEST FITNESS     {summary['best_fitness']:>8.2f}",
            f"AVG FITNESS      {summary['avg_fitness']:>8.2f}",
            f"LEARNED STATES   {summary['known_states']:>8}",
            f"FOUNDERS BRED    {'YES' if summary['founders_established'] else 'NO'}",
            f"NIGHT FACTOR     {self.world.night_factor():>8.2f}",
            f"SCENT MARKERS    {len(self.world.scents):>8}",
            f"ARCHIVED LINEAGE {len(self.lineage_archive):>8}",
            f"FPS              {self.fps:>8.1f}",
            "", "SPACE start/pause • F fast • N next generation • R reset",
        ]
        self.metrics.configure(state="normal")
        self.metrics.delete("1.0", "end")
        self.metrics.insert("1.0", "\n".join(lines))
        self.metrics.configure(state="disabled")

    def loop(self) -> None:
        now = time.perf_counter()
        self.fps = 1 / max(1e-6, now - self.last)
        self.last = now
        if self.running:
            self.world.step(4 if self.fast else 1)
            if self.frame % 5 == 0:
                self.archive_population()
        self.draw()
        if self.frame % 4 == 0:
            self.update_brain()
            self.update_lineage()
            self.update_graph()
            self.update_metrics()
        self.frame += 1
        self.root.after(25 if self.fast else 45, self.loop)


def run_headless(generations: int, population: int, seed: int) -> int:
    world = World(seed=seed)
    world.configure(population=max(2, population))
    world.reset()
    world.run_generations(max(1, generations))
    print("EVOLVE HEADLESS RESULT")
    for row in world.history[-generations:]:
        print(row)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="EVOLVE — self-contained 2D artificial-life laboratory")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--generations", type=int, default=5)
    parser.add_argument("--population", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    if args.headless:
        return run_headless(args.generations, args.population, args.seed)
    root = tk.Tk()
    EvolveApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
