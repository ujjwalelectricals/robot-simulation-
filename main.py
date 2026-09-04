from __future__ import annotations

import argparse
import math
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from evolve_core import World, Robot, clamp

BG = "#071018"
PANEL = "#0c1720"
PANEL2 = "#101f2b"
TEXT = "#eaf6fb"
MUTED = "#8ba4b2"
ACCENT = "#6be0b4"
WARN = "#ffd166"
DANGER = "#ff7180"
BLUE = "#64b5ff"


class EvolveApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("EVOLVE — Artificial Life Laboratory")
        root.geometry("1450x900")
        root.minsize(1180, 720)
        root.configure(bg=BG)
        self.world = World()
        self.running = True
        self.fast = False
        self.selected_id: int | None = None
        self.show_rays = True
        self.show_labels = False
        self.show_brain = True
        self.last_draw = time.perf_counter()
        self.fps = 0.0
        self.build()
        self.bind_keys()
        self.loop()

    def build(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", padding=7, font=("Segoe UI", 9, "bold"))
        style.configure("TEntry", padding=5)
        style.configure("TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=PANEL, foreground="#fff", font=("Segoe UI", 21, "bold"))
        style.configure("Sub.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))

        header = tk.Frame(self.root, bg=PANEL, height=68)
        header.pack(fill="x")
        ttk.Label(header, text="EVOLVE", style="Title.TLabel").pack(side="left", padx=20, pady=12)
        ttk.Label(header, text="2D ARTIFICIAL LIFE LAB • ANIMAL-STYLE LEARNING", style="Sub.TLabel").pack(side="left", pady=20)
        self.status_label = ttk.Label(header, text="● RUNNING", background=PANEL, foreground=ACCENT, font=("Segoe UI", 10, "bold"))
        self.status_label.pack(side="right", padx=20)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=12)
        scene = tk.Frame(body, bg=BG)
        scene.pack(side="left", fill="both", expand=True)
        panel = tk.Frame(body, bg=PANEL, width=330)
        panel.pack(side="right", fill="y", padx=(12, 0))

        self.canvas = tk.Canvas(scene, bg="#08131b", highlightthickness=1, highlightbackground="#1e3541")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.select_robot)
        self._build_controls(panel)
        self._build_inspector(panel)

    def _build_controls(self, panel: tk.Frame) -> None:
        section = tk.Frame(panel, bg=PANEL)
        section.pack(fill="x", padx=12, pady=12)
        for text, command in [
            ("⏯  PAUSE / RESUME", self.toggle),
            ("⏭  FORCE NEXT GENERATION", self.next_generation),
            ("↻  RESET EXPERIMENT", self.reset),
            ("⚡  FAST MODE", self.toggle_fast),
            ("💾  SAVE SNAPSHOT", self.save_snapshot),
        ]:
            ttk.Button(section, text=text, command=command).pack(fill="x", pady=3)

        ttk.Label(section, text="EXPERIMENTER POWERS", background=PANEL, foreground="#fff", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(15, 6))
        for text, command in [
            ("+ FOOD AT CURSOR", self.add_food_at_cursor),
            ("+ WATER AT CURSOR", self.add_water_at_cursor),
            ("+ HAZARD AT CURSOR", self.add_hazard_at_cursor),
            ("+ PREDATOR AT CURSOR", self.add_predator_at_cursor),
            ("REWARD SELECTED +10", lambda: self.modify_selected(10)),
            ("PUNISH SELECTED −10", lambda: self.modify_selected(-10)),
            ("HEAL SELECTED", lambda: self.heal_selected()),
            ("BOOST SELECTED ENERGY", lambda: self.boost_selected()),
        ]:
            ttk.Button(section, text=text, command=command).pack(fill="x", pady=2)

        self.rays_var = tk.BooleanVar(value=True)
        self.labels_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(section, text="Show sensory rays", variable=self.rays_var, command=self.sync_options).pack(anchor="w", pady=(8, 2))
        ttk.Checkbutton(section, text="Show robot labels", variable=self.labels_var, command=self.sync_options).pack(anchor="w", pady=2)

        ttk.Label(section, text="EXPERIMENT SETTINGS", background=PANEL, foreground="#fff", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(14, 6))
        self.vars: dict[str, tk.StringVar] = {}
        for key in ["population", "food", "water", "hazards", "predators", "mutation", "episode"]:
            row = tk.Frame(section, bg=PANEL)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=key, background=PANEL, foreground=MUTED).pack(side="left")
            v = tk.StringVar(value=str(self.world.experiment[key]))
            ttk.Entry(row, textvariable=v, width=10).pack(side="right")
            self.vars[key] = v
        ttk.Button(section, text="APPLY + RESET", command=self.apply_settings).pack(fill="x", pady=(6, 2))
        ttk.Label(section, text="Click any robot to inspect its brain, drives, memories and genome.", background=PANEL, foreground=MUTED, wraplength=290).pack(anchor="w", pady=10)

    def _build_inspector(self, panel: tk.Frame) -> None:
        tk.Frame(panel, bg="#233946", height=1).pack(fill="x", padx=12, pady=3)
        ttk.Label(panel, text="ROBOT LAB", background=PANEL, foreground="#fff", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(7, 5))
        self.inspector = tk.Text(panel, height=25, bg=PANEL2, fg=TEXT, relief="flat", state="disabled", font=("Consolas", 8), padx=9, pady=9)
        self.inspector.pack(fill="x", padx=12, pady=(0, 8))
        self.metrics = tk.Text(panel, height=8, bg=PANEL2, fg=TEXT, relief="flat", state="disabled", font=("Consolas", 9), padx=9, pady=9)
        self.metrics.pack(fill="x", padx=12, pady=(0, 12))

    def bind_keys(self) -> None:
        self.root.bind("<space>", lambda _e: self.toggle())
        self.root.bind("<f>", lambda _e: self.toggle_fast())
        self.root.bind("<n>", lambda _e: self.next_generation())
        self.root.bind("<r>", lambda _e: self.reset())
        self.root.bind("<Escape>", lambda _e: self.root.destroy())

    def sync_options(self) -> None:
        self.show_rays = self.rays_var.get()
        self.show_labels = self.labels_var.get()

    def toggle(self) -> None:
        self.running = not self.running
        self.status_label.configure(text="● RUNNING" if self.running else "● PAUSED", foreground=ACCENT if self.running else WARN)

    def toggle_fast(self) -> None:
        self.fast = not self.fast

    def reset(self) -> None:
        self.world.reset(); self.selected_id = None; self.running = True
        self.status_label.configure(text="● RUNNING", foreground=ACCENT)

    def apply_settings(self) -> None:
        try:
            self.world.experiment["population"] = max(4, int(self.vars["population"].get()))
            self.world.experiment["food"] = max(1, int(self.vars["food"].get()))
            self.world.experiment["water"] = max(1, int(self.vars["water"].get()))
            self.world.experiment["hazards"] = max(0, int(self.vars["hazards"].get()))
            self.world.experiment["predators"] = max(0, int(self.vars["predators"].get()))
            self.world.experiment["mutation"] = clamp(float(self.vars["mutation"].get()), 0.0, 1.0)
            self.world.experiment["episode"] = max(50, int(self.vars["episode"].get()))
            self.reset()
        except ValueError:
            messagebox.showerror("Invalid settings", "Enter valid numeric experiment values.")

    def next_generation(self) -> None:
        self.running = False
        target = self.world.generation
        for _ in range(self.world.experiment["episode"] // 10 + 2):
            old = self.world.generation
            self.world.step(10)
            if self.world.generation != old or self.world.generation != target:
                break
        self.running = True

    def cursor_world(self) -> tuple[float, float]:
        x = self.root.winfo_pointerx() - self.canvas.winfo_rootx()
        y = self.root.winfo_pointery() - self.canvas.winfo_rooty()
        return self.canvas_to_world(x, y)

    def add_food_at_cursor(self) -> None:
        x, y = self.cursor_world(); self.world.spawn_food(x, y)
    def add_water_at_cursor(self) -> None:
        x, y = self.cursor_world(); self.world.spawn_water(x, y)
    def add_hazard_at_cursor(self) -> None:
        x, y = self.cursor_world(); self.world.spawn_hazard(x, y)
    def add_predator_at_cursor(self) -> None:
        x, y = self.cursor_world(); self.world.spawn_predator(x, y)

    def modify_selected(self, amount: float) -> None:
        r = self.selected_robot()
        if r:
            r.fitness += amount; r.recent_reward = amount
            r.brain.valence = clamp(r.brain.valence + amount / 50, -1, 1)

    def heal_selected(self) -> None:
        r = self.selected_robot()
        if r: r.health = min(100, r.health + 30)

    def boost_selected(self) -> None:
        r = self.selected_robot()
        if r: r.energy = min(100, r.energy + 40); r.hydration = min(100, r.hydration + 30)

    def selected_robot(self) -> Robot | None:
        return next((r for r in self.world.population if r.id == self.selected_id), None)

    def canvas_to_world(self, x: float, y: float) -> tuple[float, float]:
        return x / max(1, self.canvas.winfo_width()) * self.world.width, y / max(1, self.canvas.winfo_height()) * self.world.height

    def world_to_canvas(self, x: float, y: float) -> tuple[float, float]:
        return x / self.world.width * max(1, self.canvas.winfo_width()), y / self.world.height * max(1, self.canvas.winfo_height())

    def select_robot(self, event: tk.Event) -> None:
        x, y = self.canvas_to_world(event.x, event.y)
        candidate = min(self.world.population, key=lambda r: (r.x-x) ** 2 + (r.y-y) ** 2, default=None)
        if candidate and math.hypot(candidate.x-x, candidate.y-y) < 25:
            self.selected_id = candidate.id

    def draw(self) -> None:
        c = self.canvas; c.delete("all")
        cw, ch = max(1, c.winfo_width()), max(1, c.winfo_height())
        for gx in range(0, self.world.width + 1, 50):
            x, _ = self.world_to_canvas(gx, 0); c.create_line(x, 0, x, ch, fill="#10232e")
        for gy in range(0, self.world.height + 1, 50):
            _, y = self.world_to_canvas(0, gy); c.create_line(0, y, cw, y, fill="#10232e")
        for s in self.world.shelters:
            x, y = self.world_to_canvas(s.x, s.y); r = s.radius / self.world.width * cw
            c.create_oval(x-r, y-r, x+r, y+r, outline="#355466", dash=(3, 3)); c.create_text(x, y, text="S", fill="#57798a")
        for h in self.world.hazards:
            x, y = self.world_to_canvas(h.x, h.y); r = h.radius / self.world.width * cw
            c.create_oval(x-r, y-r, x+r, y+r, fill="#351821", outline=DANGER, width=2); c.create_text(x, y, text="!", fill=DANGER)
        for f in self.world.food:
            x, y = self.world_to_canvas(f.x, f.y); c.create_oval(x-4, y-4, x+4, y+4, fill="#90e59a", outline="")
        for w in self.world.water:
            x, y = self.world_to_canvas(w.x, w.y); c.create_oval(x-5, y-5, x+5, y+5, fill=BLUE, outline="")
        for p in self.world.predators:
            x, y = self.world_to_canvas(p.x, p.y); c.create_polygon(x-10, y+8, x, y-10, x+10, y+8, fill="#dc6678", outline="#ff98a5")
        for r in self.world.population:
            x, y = self.world_to_canvas(r.x, r.y); selected = r.id == self.selected_id
            if selected: c.create_oval(x-19, y-19, x+19, y+19, outline=ACCENT, width=2)
            hx, hy = x + 13 * math.cos(r.angle), y + 13 * math.sin(r.angle)
            c.create_line(x, y, hx, hy, fill=TEXT, width=2)
            body = "#e5fff4" if selected else "#76b09f"
            c.create_oval(x-9, y-9, x+9, y+9, fill=body, outline="#061018")
            c.create_oval(hx-2.5, hy-2.5, hx+2.5, hy+2.5, fill="#061018", outline="")
            if self.show_labels: c.create_text(x, y-19, text=f"#{r.id} G{r.generation}", fill=MUTED, font=("Segoe UI", 7))
            if selected and self.show_rays:
                for off in (-0.8, -0.4, 0, 0.4, 0.8):
                    ex, ey = self.world_to_canvas(r.x + math.cos(r.angle+off)*r.genome.vision, r.y + math.sin(r.angle+off)*r.genome.vision)
                    c.create_line(x, y, ex, ey, fill="#2b6678", dash=(3, 5))

    def update_inspector(self) -> None:
        r = self.selected_robot()
        self.inspector.configure(state="normal"); self.inspector.delete("1.0", "end")
        if r:
            hunger, thirst, fatigue, fear, curiosity = r.drives()
            text = [
                f"ROBOT #{r.id}   GENERATION {r.generation}",
                f"age={r.age}  health={r.health:5.1f}  energy={r.energy:5.1f}  water={r.hydration:5.1f}",
                f"fitness={r.fitness:7.2f}  food={r.food_eaten}  water_found={r.water_found}",
                f"damage={r.damage_taken:5.1f}  reward={r.recent_reward:6.2f}  offspring={r.offspring}",
                "",
                "ANIMAL-STYLE DRIVES",
                f"hunger={hunger:.2f} thirst={thirst:.2f} fatigue={fatigue:.2f}",
                f"fear={fear:.2f} curiosity={curiosity:.2f}",
                "",
                "BRAIN",
                f"known states={len(r.brain.q)}",
                f"working memory={len(r.brain.working)}",
                f"episodic memory={len(r.brain.episodic)}",
                f"confidence={r.brain.confidence:.2f} stress={r.brain.stress:.2f}",
                f"valence={r.brain.valence:.2f} exploration={r.brain.epsilon:.2f}",
                "",
                "GENOME",
                f"speed={r.genome.speed:.2f} turn={r.genome.turn:.2f} vision={r.genome.vision:.1f}",
                f"efficiency={r.genome.efficiency:.2f} curiosity={r.genome.curiosity:.2f}",
                f"boldness={r.genome.boldness:.2f} sociability={r.genome.sociability:.2f}",
                f"learning={r.genome.learning_rate:.2f} discount={r.genome.discount:.2f}",
            ]
            self.inspector.insert("1.0", "\n".join(text))
        else:
            self.inspector.insert("1.0", "Click a robot to inspect its internal drives, associative brain, memory and inherited genome.")
        self.inspector.configure(state="disabled")

    def update_metrics(self) -> None:
        s = self.world.summary()
        hist = self.world.history[-1] if self.world.history else {}
        self.metrics.configure(state="normal"); self.metrics.delete("1.0", "end")
        lines = [
            f"GENERATION   {s['generation']}",
            f"ALIVE        {s['alive']:>3}/{s['population']}",
            f"TICK         {s['tick']:>4}",
            f"BEST FITNESS {s['best_fitness']:>7}",
            f"AVG FITNESS  {s['avg_fitness']:>7}",
            f"KNOWLEDGE    {s['known_states']:>7} states",
            f"FPS          {self.fps:>7.1f}",
            f"LAST BEST    {hist.get('best_age', '—')} age",
        ]
        self.metrics.insert("1.0", "\n".join(lines)); self.metrics.configure(state="disabled")

    def save_snapshot(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path: self.world.save_snapshot(path)

    def loop(self) -> None:
        now = time.perf_counter(); dt = max(1e-6, now - self.last_draw); self.fps = 1.0 / dt; self.last_draw = now
        if self.running: self.world.step(20 if self.fast else 3)
        self.draw(); self.update_inspector(); self.update_metrics()
        self.root.after(25 if self.fast else 45, self.loop)


def run_headless(generations: int, population: int, seed: int) -> int:
    world = World(seed=seed)
    world.experiment["population"] = population
    world.reset()
    world.run_generations(generations)
    print("EVOLVE HEADLESS RESULT")
    for row in world.history[-generations:]: print(row)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Evolve — 2D Artificial Life Laboratory")
    p.add_argument("--headless", action="store_true", help="run simulation without GUI")
    p.add_argument("--generations", type=int, default=5)
    p.add_argument("--population", type=int, default=100)
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args()
    if args.headless: return run_headless(max(1, args.generations), max(4, args.population), args.seed)
    root = tk.Tk(); EvolveApp(root); root.mainloop(); return 0


if __name__ == "__main__":
    raise SystemExit(main())
