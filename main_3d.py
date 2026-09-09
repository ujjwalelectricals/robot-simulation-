from __future__ import annotations

import argparse
import math
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from performance_tuning import install as install_performance

install_performance()

from evolve_engine import Predator, Robot, Shelter, World

BG = "#071018"
PANEL = "#0c1720"
PANEL2 = "#101f2b"
TEXT = "#eaf6fb"
MUTED = "#8ba4b2"
ACCENT = "#6be0b4"
WARN = "#ffd166"
DANGER = "#ff7180"
BLUE = "#64b5ff"
FOOD = "#90e59a"
GRID = "#1b343e"


class Evolve3DApp:
    """Software-rendered 3D laboratory using the existing self-contained engine."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("EVOLVE — 3D Artificial Life Laboratory")
        root.geometry("1560x960")
        root.minsize(1180, 760)
        root.configure(bg=BG)
        self.world = World()
        self.running = False
        self.fast = False
        self.selected_id: int | None = None
        self.show_sensors = True
        self.show_labels = False
        self.show_trails = True
        self.yaw = -0.72
        self.pitch = 0.85
        self.zoom = 1.0
        self.last = time.perf_counter()
        self.fps = 0.0
        self.frame = 0
        self.drag_last: tuple[int, int] | None = None
        self.build()
        self.bind_keys()
        self.set_status("● READY • 2 FOUNDERS", WARN)
        self.loop()

    def build(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", padding=7, font=("Segoe UI", 9, "bold"))
        style.configure("TEntry", padding=5)
        style.configure("TNotebook", background=PANEL)
        style.configure("TNotebook.Tab", padding=(10, 5))
        style.configure("TLabel", background=PANEL, foreground=TEXT)
        header = tk.Frame(self.root, bg=PANEL, height=66)
        header.pack(fill="x")
        ttk.Label(header, text="EVOLVE 3D", background=PANEL, foreground="#fff", font=("Segoe UI", 21, "bold")).pack(side="left", padx=18, pady=10)
        ttk.Label(header, text="ARTIFICIAL LIFE • COGNITION • ECOLOGY • EVOLUTION", background=PANEL, foreground=MUTED, font=("Segoe UI", 9)).pack(side="left", pady=19)
        self.status = ttk.Label(header, text="● READY • 2 FOUNDERS", background=PANEL, foreground=WARN, font=("Segoe UI", 10, "bold"))
        self.status.pack(side="right", padx=18)
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=10)
        scene = tk.Frame(body, bg=BG)
        scene.pack(side="left", fill="both", expand=True)
        side = tk.Frame(body, bg=PANEL, width=390)
        side.pack(side="right", fill="y", padx=(10, 0))
        self.canvas = tk.Canvas(scene, bg="#071015", highlightthickness=1, highlightbackground="#1e3541")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.select_robot)
        self.canvas.bind("<ButtonPress-3>", self.start_orbit)
        self.canvas.bind("<B3-Motion>", self.orbit)
        self.canvas.bind("<MouseWheel>", self.zoom_mouse)
        self._controls(side)
        self._tabs(side)

    def _controls(self, panel: tk.Frame) -> None:
        box = tk.Frame(panel, bg=PANEL)
        box.pack(fill="x", padx=10, pady=8)
        for text, command in [
            ("⏯ START / PAUSE", self.toggle),
            ("↻ RESET", self.reset),
            ("⚡ FAST MODE", self.toggle_fast),
            ("⏭ NEXT GENERATION", self.next_generation),
            ("💾 SNAPSHOT", self.save_snapshot),
            ("🧬 EXPORT GENOME", self.export_genome),
        ]:
            ttk.Button(box, text=text, command=command).pack(fill="x", pady=2)
        ttk.Label(box, text="EXPERIMENTER", background=PANEL, foreground="#fff", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(9, 4))
        for text, command in [
            ("+ FOOD", self.add_food), ("+ WATER", self.add_water), ("+ HAZARD", self.add_hazard), ("+ PREDATOR", self.add_predator),
            ("REWARD +10", lambda: self.reward(10)), ("PUNISH −10", lambda: self.reward(-10)),
            ("HEAL", self.heal), ("BOOST", self.boost), ("☠ KILL", self.kill), ("TELEPORT", self.teleport),
        ]:
            ttk.Button(box, text=text, command=command).pack(fill="x", pady=1)
        self.sensor_var = tk.BooleanVar(value=True)
        self.label_var = tk.BooleanVar(value=False)
        self.trail_var = tk.BooleanVar(value=True)
        for text, var in [("Show sensory rays", self.sensor_var), ("Show labels", self.label_var), ("Show scent/trails", self.trail_var)]:
            ttk.Checkbutton(box, text=text, variable=var, command=self.sync).pack(anchor="w")
        ttk.Label(box, text="WORLD", background=PANEL, foreground="#fff", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(9, 4))
        self.vars: dict[str, tk.StringVar] = {}
        for key in ["population", "food", "water", "hazards", "predators", "mutation", "episode"]:
            row = tk.Frame(box, bg=PANEL); row.pack(fill="x", pady=1)
            ttk.Label(row, text=key, background=PANEL, foreground=MUTED).pack(side="left")
            sv = tk.StringVar(value=str(self.world.experiment[key]))
            ttk.Entry(row, textvariable=sv, width=10).pack(side="right")
            self.vars[key] = sv
        ttk.Button(box, text="APPLY + RESET", command=self.apply).pack(fill="x", pady=(4, 2))

    def _tabs(self, panel: tk.Frame) -> None:
        nb = ttk.Notebook(panel); nb.pack(fill="both", expand=True, padx=7, pady=7)
        brain, world_tab, stats = (tk.Frame(nb, bg=PANEL) for _ in range(3))
        nb.add(brain, text="BRAIN"); nb.add(world_tab, text="WORLD"); nb.add(stats, text="STATS")
        self.inspector = tk.Text(brain, bg=PANEL2, fg=TEXT, relief="flat", state="disabled", font=("Consolas", 8), height=30); self.inspector.pack(fill="both", expand=True, padx=7, pady=7)
        self.world_info = tk.Text(world_tab, bg=PANEL2, fg=TEXT, relief="flat", state="disabled", font=("Consolas", 8), height=30); self.world_info.pack(fill="both", expand=True, padx=7, pady=7)
        self.stats = tk.Text(stats, bg=PANEL2, fg=TEXT, relief="flat", state="disabled", font=("Consolas", 8), height=30); self.stats.pack(fill="both", expand=True, padx=7, pady=7)

    def bind_keys(self) -> None:
        self.root.bind("<space>", lambda _e: self.toggle())
        self.root.bind("<f>", lambda _e: self.toggle_fast())
        self.root.bind("<n>", lambda _e: self.next_generation())
        self.root.bind("<r>", lambda _e: self.reset())
        self.root.bind("<Escape>", lambda _e: self.root.destroy())
        self.root.bind("<plus>", lambda _e: self.adjust_zoom(1.12))
        self.root.bind("<minus>", lambda _e: self.adjust_zoom(0.89))

    def set_status(self, text: str, foreground: str) -> None: self.status.configure(text=text, foreground=foreground)
    def sync(self) -> None:
        self.show_sensors, self.show_labels, self.show_trails = self.sensor_var.get(), self.label_var.get(), self.trail_var.get()
    def toggle(self) -> None:
        self.running = not self.running; self.set_status("● RUNNING" if self.running else "● PAUSED", ACCENT if self.running else WARN)
    def toggle_fast(self) -> None:
        self.fast = not self.fast; self.set_status("● FAST MODE" if self.fast and self.running else ("● PAUSED" if not self.running else "● RUNNING"), WARN if self.fast else ACCENT)
    def reset(self) -> None:
        self.world.reset(); self.selected_id = None; self.running = False; self.set_status("● READY • 2 FOUNDERS", WARN)

    def apply(self) -> None:
        try:
            values = {k: (float(v.get()) if k == "mutation" else int(v.get())) for k, v in self.vars.items()}
            self.world.configure(**values); self.reset()
        except ValueError:
            messagebox.showerror("Invalid settings", "Enter valid numeric values.")

    def next_generation(self) -> None:
        self.running = False; start = self.world.generation
        for _ in range(max(1, self.world.experiment["episode"] + 20)):
            self.world.step(1)
            if self.world.generation != start: break
        self.set_status(f"● GENERATION {self.world.generation} • PAUSED", WARN)

    def cursor_world(self) -> tuple[float, float]:
        cx = self.root.winfo_pointerx() - self.canvas.winfo_rootx(); cy = self.root.winfo_pointery() - self.canvas.winfo_rooty()
        return self.canvas_to_world(cx, cy)
    def add_food(self) -> None: self.world.spawn_food(*self.cursor_world())
    def add_water(self) -> None: self.world.spawn_water(*self.cursor_world())
    def add_hazard(self) -> None: self.world.spawn_hazard(*self.cursor_world())
    def add_predator(self) -> None: self.world.spawn_predator(*self.cursor_world())
    def selected(self) -> Robot | None: return next((r for r in self.world.population if r.id == self.selected_id), None)
    def reward(self, amount: float) -> None:
        r = self.selected();
        if r: self.world.reward_robot(r.id, amount)
    def heal(self) -> None:
        r = self.selected();
        if r: self.world.heal_robot(r.id)
    def boost(self) -> None:
        r = self.selected();
        if r: self.world.boost_robot(r.id)
    def kill(self) -> None:
        r = self.selected();
        if r: self.world.kill_robot(r.id)
    def teleport(self) -> None:
        r = self.selected();
        if r: self.world.teleport_robot(r.id, *self.cursor_world())

    def export_genome(self) -> None:
        r = self.selected()
        if not r: return
        path = filedialog.asksaveasfilename(defaultextension=".genome.json", filetypes=[("Genome JSON", "*.genome.json")])
        if path: World.save_genome(r, path)

    def save_snapshot(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path: self.world.save_snapshot(path)

    def start_orbit(self, event: tk.Event) -> None: self.drag_last = (event.x, event.y)
    def orbit(self, event: tk.Event) -> None:
        if self.drag_last is None: return
        px, py = self.drag_last; self.yaw += (event.x - px) * 0.008; self.pitch = max(0.35, min(1.35, self.pitch + (event.y - py) * 0.006)); self.drag_last = (event.x, event.y)
    def zoom_mouse(self, event: tk.Event) -> None: self.adjust_zoom(1.1 if event.delta > 0 else 0.91)
    def adjust_zoom(self, factor: float) -> None: self.zoom = max(0.45, min(2.6, self.zoom * factor))

    def world_to_camera(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        cy, sy = math.cos(self.yaw), math.sin(self.yaw); x1, z1 = x * cy - z * sy, x * sy + z * cy
        cp, sp = math.cos(self.pitch), math.sin(self.pitch); y2, z2 = y * cp - z1 * sp, y * sp + z1 * cp
        return x1, y2, z2

    def project(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        w, h = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height()); scale = min(w / self.world.width, h / self.world.height) * 0.78 * self.zoom
        cx, cy, cz = self.world_to_camera(x - self.world.width / 2, y, z - self.world.height / 2); depth = cz + 900.0; factor = 700.0 / max(150.0, depth)
        return w / 2 + cx * scale * factor, h * 0.58 - cy * scale * factor, depth

    def terrain_height(self, x: float, z: float) -> float:
        return 18.0 * math.sin(x * 0.018) * math.cos(z * 0.015) + 8.0 * math.sin((x + z) * 0.028)

    def draw(self) -> None:
        c = self.canvas; c.delete("all"); w, h = max(1, c.winfo_width()), max(1, c.winfo_height())
        c.create_rectangle(0, 0, w, h, fill="#071015", outline=""); horizon = h * 0.48; c.create_rectangle(0, 0, w, horizon, fill="#091821", outline="")
        for gx in range(0, int(self.world.width) + 1, 80):
            pts=[]
            for z in range(0, int(self.world.height)+1, 80): pts.extend(self.project(gx, self.terrain_height(gx,z), z)[:2])
            c.create_line(*pts, fill=GRID, width=1)
        for gz in range(0, int(self.world.height) + 1, 80):
            pts=[]
            for x in range(0, int(self.world.width)+1, 80): pts.extend(self.project(x, self.terrain_height(x,gz), gz)[:2])
            c.create_line(*pts, fill=GRID, width=1)
        items=[]
        for f in self.world.food:
            if f.alive: items.append((self.project(f.x, self.terrain_height(f.x,f.y)+2, f.y)[2], "food", f))
        for wt in self.world.water:
            if wt.alive: items.append((self.project(wt.x, self.terrain_height(wt.x,wt.y)+1, wt.y)[2], "water", wt))
        for sh in self.world.shelters: items.append((self.project(sh.x, self.terrain_height(sh.x,sh.y), sh.y)[2], "shelter", sh))
        for hz in self.world.hazards: items.append((self.project(hz.x, self.terrain_height(hz.x,hz.y)+1, hz.y)[2], "hazard", hz))
        for p in self.world.predators:
            if p.alive: items.append((self.project(p.x, self.terrain_height(p.x,p.y)+13, p.y)[2], "predator", p))
        for r in self.world.population:
            if r.alive: items.append((self.project(r.x, self.terrain_height(r.x,r.y)+r.radius()*1.5, r.y)[2], "robot", r))
        for _depth, kind, obj in sorted(items, reverse=True, key=lambda i: i[0]):
            if kind == "food": self.draw_resource(obj.x,obj.y,FOOD,5)
            elif kind == "water": self.draw_resource(obj.x,obj.y,BLUE,7)
            elif kind == "shelter": self.draw_shelter(obj)
            elif kind == "hazard": self.draw_hazard(obj)
            elif kind == "predator": self.draw_actor(obj.x,obj.y,DANGER,12,getattr(obj,"angle",0.0))
            else: self.draw_robot(obj)
        self.draw_hud()

    def draw_resource(self,x,z,fill,size):
        sx,sy,_=self.project(x,self.terrain_height(x,z)+5,z); self.canvas.create_oval(sx-size,sy-size,sx+size,sy+size,fill=fill,outline="")
    def draw_shelter(self,sh):
        sx,sy,_=self.project(sh.x,self.terrain_height(sh.x,sh.y),sh.y); r=max(8,sh.radius*self.zoom*0.20); self.canvas.create_oval(sx-r,sy-r*.45,sx+r,sy+r*.45,outline="#527888",width=2)
    def draw_hazard(self,hz):
        sx,sy,_=self.project(hz.x,self.terrain_height(hz.x,hz.y)+4,hz.y); r=max(6,hz.radius*self.zoom*.18); self.canvas.create_polygon(sx,sy-r,sx+r*.8,sy+r*.4,sx-r*.8,sy+r*.4,fill=DANGER,outline="")
    def draw_actor(self,x,z,fill,size,angle):
        gx,gy,_=self.project(x,self.terrain_height(x,z),z); sx,sy,_=self.project(x,self.terrain_height(x,z)+size,z); self.canvas.create_oval(sx-size,sy-size,sx+size,sy+size,fill=fill,outline=""); self.canvas.create_line(sx,sy,gx,gy,fill="#111c22",width=2)
        hx,hy,_=self.project(x+math.cos(angle)*size*1.8,self.terrain_height(x,z)+size,z+math.sin(angle)*size*1.8); self.canvas.create_line(sx,sy,hx,hy,fill=fill,width=2)
    def draw_robot(self,r):
        sx,sy,_=self.project(r.x,self.terrain_height(r.x,r.y)+r.radius()*1.7,r.y); rr=max(7,r.radius()*self.zoom*.22); fill=BLUE if r.sex=="male" else "#e78bb7"; outline=ACCENT if r.id==self.selected_id else "#d9eef5"
        self.canvas.create_oval(sx-rr,sy-rr,sx+rr,sy+rr,fill=fill,outline=outline,width=2); self.canvas.create_line(sx,sy,sx+math.cos(r.angle)*rr*1.9,sy-math.sin(r.angle)*rr*1.9,fill="#fff",width=2)
        if r.id==self.selected_id and self.show_sensors:
            for ray in r.genome.rays:
                a=r.angle+ray.angle; tx,ty,_=self.project(r.x+math.cos(a)*ray.length,self.terrain_height(r.x,r.y)+r.radius(),r.y+math.sin(a)*ray.length); self.canvas.create_line(sx,sy,tx,ty,fill="#5fe0c0",width=1)
        if self.show_labels: self.canvas.create_text(sx,sy-rr-10,text=f"#{r.id} G{r.generation}",fill=TEXT,font=("Segoe UI",8))
    def draw_hud(self):
        alive=sum(r.alive for r in self.world.population); text=f"3D  |  G{self.world.generation}  |  POP {alive}/{len(self.world.population)}  |  PRED {sum(p.alive for p in self.world.predators)}  |  FPS {self.fps:5.1f}"
        self.canvas.create_rectangle(14,14,540,42,fill="#0a1720",outline="#284554"); self.canvas.create_text(24,28,text=text,anchor="w",fill=TEXT,font=("Consolas",9,"bold"))

    def update_panels(self):
        r=self.selected()
        if r:
            lines=[f"SELECTED #{r.id}",f"SEX          {r.sex}",f"GENERATION   {r.generation}",f"AGE          {r.age}",f"HEALTH       {r.health:6.1f}",f"ENERGY       {r.energy:6.1f}",f"HYDRATION    {r.hydration:6.1f}",f"FITNESS      {r.fitness:6.2f}","",f"GOAL         {getattr(r.brain,'current_goal','explore')}",f"Q STATES     {len(r.brain.q)}",f"MEMORY       {len(getattr(r,'long_memory',[]))}",f"FOOD EATEN   {r.food_eaten}",f"WATER FOUND  {r.water_found}",f"OFFSPRING    {r.offspring}",f"BOLDNESS     {r.genome.boldness:.2f}",f"CURIOSITY    {r.genome.curiosity:.2f}"]
        else: lines=["NO ROBOT SELECTED","","Left click a robot.","Right-drag to orbit.","Mouse wheel / +/- to zoom."]
        self.inspector.configure(state="normal"); self.inspector.delete("1.0","end"); self.inspector.insert("1.0","\n".join(lines)); self.inspector.configure(state="disabled")
        s=self.world.summary(); world_lines=[f"DAY FACTOR    {self.world.night_factor():.3f}",f"FOOD          {sum(f.alive for f in self.world.food)}",f"WATER         {sum(w.alive for w in self.world.water)}",f"HAZARDS       {len(self.world.hazards)}",f"PREDATORS     {sum(p.alive for p in self.world.predators)}",f"SHELTERS      {len(self.world.shelters)}",f"SCENTS        {len(self.world.scents)}"]
        self.world_info.configure(state="normal"); self.world_info.delete("1.0","end"); self.world_info.insert("1.0","\n".join(world_lines)); self.world_info.configure(state="disabled")
        stat_lines=[f"GENERATION    {s['generation']}",f"BEST FITNESS  {s['best_fitness']:.2f}",f"AVG FITNESS   {s['avg_fitness']:.2f}",f"ALIVE         {s['alive']}",f"KNOWN STATES  {s['known_states']}",f"FOUNDERS BRED {s['founders_established']}","","CAMERA","Right-drag = orbit","Wheel / +/- = zoom"]
        self.stats.configure(state="normal"); self.stats.delete("1.0","end"); self.stats.insert("1.0","\n".join(stat_lines)); self.stats.configure(state="disabled")

    def select_robot(self,event):
        best=None; bd=32.0*32.0
        for r in self.world.population:
            if not r.alive: continue
            sx,sy,_=self.project(r.x,self.terrain_height(r.x,r.y)+r.radius()*1.6,r.y); d=(sx-event.x)**2+(sy-event.y)**2
            if d<bd: best,bd=r,d
        self.selected_id=best.id if best else None
    def canvas_to_world(self,x,y):
        return x/max(1,self.canvas.winfo_width())*self.world.width,y/max(1,self.canvas.winfo_height())*self.world.height

    def loop(self):
        now=time.perf_counter(); dt=max(1e-6,now-self.last); self.last=now; inst=1.0/dt; self.fps=0.92*self.fps+0.08*inst if self.fps else inst
        if self.running: self.world.step(2 if self.fast else 1)
        self.draw();
        if self.frame%5==0: self.update_panels()
        self.frame+=1; self.root.after(25 if self.fast else 40,self.loop)


def run_headless(generations:int,population:int,seed:int)->int:
    world=World(seed=seed); world.configure(population=max(2,population)); world.reset(); world.run_generations(max(1,generations)); print("EVOLVE 3D HEADLESS RESULT"); [print(row) for row in world.history[-max(1,generations):]]; return 0


def main()->int:
    parser=argparse.ArgumentParser(description="EVOLVE — 3D artificial-life laboratory"); parser.add_argument("--headless",action="store_true"); parser.add_argument("--generations",type=int,default=5); parser.add_argument("--population",type=int,default=20); parser.add_argument("--seed",type=int,default=7); args=parser.parse_args()
    if args.headless: return run_headless(args.generations,args.population,args.seed)
    root=tk.Tk(); Evolve3DApp(root); root.mainloop(); return 0

if __name__=="__main__": raise SystemExit(main())
