from __future__ import annotations

import argparse
import math
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from evolve_engine import ACTIONS, Genome, Robot, World, clamp

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
SOCIAL = "#d49cff"


class EvolveApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("EVOLVE — Artificial Life Laboratory")
        root.geometry("1500x920")
        root.minsize(1200, 760)
        root.configure(bg=BG)
        self.world = World()
        self.running = True
        self.fast = False
        self.selected_id: int | None = None
        self.show_rays = True
        self.show_labels = False
        self.show_scents = True
        self.last = time.perf_counter()
        self.fps = 0.0
        self.build()
        self.bind_keys()
        self.loop()

    def build(self) -> None:
        style = ttk.Style(); style.theme_use("clam")
        style.configure("TButton", padding=7, font=("Segoe UI", 9, "bold"))
        style.configure("TEntry", padding=5)
        style.configure("TLabel", background=PANEL, foreground=TEXT)
        style.configure("Title.TLabel", background=PANEL, foreground="#fff", font=("Segoe UI", 21, "bold"))
        style.configure("Sub.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))
        header = tk.Frame(self.root, bg=PANEL, height=68); header.pack(fill="x")
        ttk.Label(header, text="EVOLVE", style="Title.TLabel").pack(side="left", padx=20, pady=12)
        ttk.Label(header, text="2D ARTIFICIAL LIFE LAB • DOG-INSPIRED COGNITION", style="Sub.TLabel").pack(side="left", pady=20)
        self.status = ttk.Label(header, text="● RUNNING", background=PANEL, foreground=ACCENT, font=("Segoe UI", 10, "bold")); self.status.pack(side="right", padx=20)
        body = tk.Frame(self.root, bg=BG); body.pack(fill="both", expand=True, padx=12, pady=12)
        scene = tk.Frame(body, bg=BG); scene.pack(side="left", fill="both", expand=True)
        panel = tk.Frame(body, bg=PANEL, width=360); panel.pack(side="right", fill="y", padx=(12, 0))
        self.canvas = tk.Canvas(scene, bg="#08131b", highlightthickness=1, highlightbackground="#1e3541"); self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.select_robot)
        self.build_controls(panel); self.build_inspector(panel)

    def build_controls(self, panel: tk.Frame) -> None:
        box = tk.Frame(panel, bg=PANEL); box.pack(fill="x", padx=12, pady=10)
        for text, cmd in [("⏯  PAUSE / RESUME", self.toggle), ("⏭  FORCE NEXT GENERATION", self.next_generation), ("↻  RESET EXPERIMENT", self.reset), ("⚡  FAST MODE", self.toggle_fast), ("💾  SAVE WORLD SNAPSHOT", self.save_snapshot), ("🧬  EXPORT SELECTED GENOME", self.export_genome)]:
            ttk.Button(box, text=text, command=cmd).pack(fill="x", pady=2)
        ttk.Label(box, text="EXPERIMENTER POWERS", background=PANEL, foreground="#fff", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(12,5))
        powers = [("+ FOOD AT CURSOR", self.add_food), ("+ WATER AT CURSOR", self.add_water), ("+ HAZARD AT CURSOR", self.add_hazard), ("+ PREDATOR AT CURSOR", self.add_predator), ("REWARD SELECTED +10", lambda: self.reward(10)), ("PUNISH SELECTED −10", lambda: self.reward(-10)), ("HEAL SELECTED", self.heal), ("BOOST SELECTED", self.boost), ("☠ KILL SELECTED", self.kill), ("TELEPORT SELECTED", self.teleport)]
        for text, cmd in powers: ttk.Button(box, text=text, command=cmd).pack(fill="x", pady=1)
        self.rays = tk.BooleanVar(value=True); self.labels = tk.BooleanVar(value=False); self.scents = tk.BooleanVar(value=True)
        for text, var in [("Show evolved sensory rays", self.rays), ("Show robot labels", self.labels), ("Show scent trails", self.scents)]: ttk.Checkbutton(box, text=text, variable=var, command=self.sync).pack(anchor="w")
        ttk.Label(box, text="EXPERIMENT SETTINGS", background=PANEL, foreground="#fff", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(10,5))
        self.vars: dict[str, tk.StringVar] = {}
        for key in ["population", "food", "water", "hazards", "predators", "mutation", "episode"]:
            row=tk.Frame(box,bg=PANEL); row.pack(fill="x", pady=1); ttk.Label(row,text=key,background=PANEL,foreground=MUTED).pack(side="left"); v=tk.StringVar(value=str(self.world.experiment[key])); ttk.Entry(row,textvariable=v,width=10).pack(side="right"); self.vars[key]=v
        ttk.Button(box,text="APPLY + RESET",command=self.apply).pack(fill="x",pady=(5,2))
        ttk.Label(box, text="Founders: exactly one male + one female. If either founder dies before their first reproduction, the entire experiment resets.", background=PANEL, foreground=MUTED, wraplength=320).pack(anchor="w", pady=8)

    def build_inspector(self, panel: tk.Frame) -> None:
        tk.Frame(panel,bg="#233946",height=1).pack(fill="x",padx=12,pady=3)
        ttk.Label(panel,text="ROBOT BRAIN MAP",background=PANEL,foreground="#fff",font=("Segoe UI",11,"bold")).pack(anchor="w",padx=12,pady=(7,5))
        self.inspector=tk.Text(panel,height=24,bg=PANEL2,fg=TEXT,relief="flat",state="disabled",font=("Consolas",8),padx=9,pady=9); self.inspector.pack(fill="x",padx=12,pady=(0,8))
        ttk.Label(panel,text="LIVE LAB METRICS",background=PANEL,foreground="#fff",font=("Segoe UI",11,"bold")).pack(anchor="w",padx=12,pady=(2,5))
        self.metrics=tk.Text(panel,height=11,bg=PANEL2,fg=TEXT,relief="flat",state="disabled",font=("Consolas",9),padx=9,pady=9); self.metrics.pack(fill="x",padx=12,pady=(0,12))

    def bind_keys(self)->None:
        self.root.bind("<space>", lambda _e:self.toggle()); self.root.bind("<f>", lambda _e:self.toggle_fast()); self.root.bind("<n>", lambda _e:self.next_generation()); self.root.bind("<r>", lambda _e:self.reset()); self.root.bind("<Escape>", lambda _e:self.root.destroy())

    def sync(self)->None:
        self.show_rays=self.rays.get(); self.show_labels=self.labels.get(); self.show_scents=self.scents.get()
    def toggle(self)->None:
        self.running=not self.running; self.status.configure(text="● RUNNING" if self.running else "● PAUSED", foreground=ACCENT if self.running else WARN)
    def toggle_fast(self)->None: self.fast=not self.fast
    def reset(self)->None:
        self.world.reset(); self.selected_id=None; self.running=True; self.status.configure(text="● RUNNING", foreground=ACCENT)
    def apply(self)->None:
        try:
            self.world.configure(**{k:(int(v) if k != "mutation" else float(v)) for k,v in ((key,self.vars[key].get()) for key in self.vars)})
            self.reset()
        except ValueError: messagebox.showerror("Invalid settings", "Enter valid numeric settings.")
    def next_generation(self)->None:
        self.running=False; start=self.world.generation
        for _ in range(self.world.experiment["episode"]//10 + 3):
            self.world.step(10)
            if self.world.generation != start: break
        self.running=True
    def cursor(self)->tuple[float,float]:
        cx=self.root.winfo_pointerx()-self.canvas.winfo_rootx(); cy=self.root.winfo_pointery()-self.canvas.winfo_rooty(); return self.canvas_to_world(cx,cy)
    def add_food(self)->None:self.world.spawn_food(*self.cursor())
    def add_water(self)->None:self.world.spawn_water(*self.cursor())
    def add_hazard(self)->None:self.world.spawn_hazard(*self.cursor())
    def add_predator(self)->None:self.world.spawn_predator(*self.cursor())
    def selected(self)->Robot|None:return next((r for r in self.world.population if r.id==self.selected_id),None)
    def reward(self, amount:float)->None:
        r=self.selected();
        if r:self.world.reward_robot(r.id,amount)
    def heal(self)->None:
        r=self.selected();
        if r:self.world.heal_robot(r.id)
    def boost(self)->None:
        r=self.selected();
        if r:self.world.boost_robot(r.id)
    def kill(self)->None:
        r=self.selected();
        if r:self.world.kill_robot(r.id)
    def teleport(self)->None:
        r=self.selected();
        if r:self.world.teleport_robot(r.id,*self.cursor())
    def export_genome(self)->None:
        r=self.selected()
        if not r: return
        path=filedialog.asksaveasfilename(defaultextension=".genome.json",filetypes=[("Genome JSON","*.genome.json"), ("JSON","*.json")])
        if path: World.save_genome(r,path)
    def save_snapshot(self)->None:
        path=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("JSON","*.json")])
        if path:self.world.save_snapshot(path)
    def canvas_to_world(self,x:float,y:float)->tuple[float,float]: return x/max(1,self.canvas.winfo_width())*self.world.width,y/max(1,self.canvas.winfo_height())*self.world.height
    def world_to_canvas(self,x:float,y:float)->tuple[float,float]: return x/self.world.width*max(1,self.canvas.winfo_width()),y/self.world.height*max(1,self.canvas.winfo_height())
    def select_robot(self,event:tk.Event)->None:
        x,y=self.canvas_to_world(event.x,event.y); candidate=min(self.world.population,key=lambda r:(r.x-x)**2+(r.y-y)**2,default=None)
        if candidate and math.hypot(candidate.x-x,candidate.y-y)<30:self.selected_id=candidate.id

    def draw(self)->None:
        c=self.canvas;c.delete("all");cw,ch=max(1,c.winfo_width()),max(1,c.winfo_height())
        for gx in range(0,self.world.width+1,50):
            x,_=self.world_to_canvas(gx,0); c.create_line(x,0,x,ch,fill="#10232e")
        for gy in range(0,self.world.height+1,50):
            _,y=self.world_to_canvas(0,gy); c.create_line(0,y,cw,y,fill="#10232e")
        if self.show_scents:
            for s in self.world.scents[::2]:
                x,y=self.world_to_canvas(s.x,s.y); radius=max(2, 8*s.strength)
                c.create_oval(x-radius,y-radius,x+radius,y+radius,outline=(FOOD if s.kind=="food" else DANGER),width=1)
        for s in self.world.shelters:
            x,y=self.world_to_canvas(s.x,s.y); rr=s.radius/self.world.width*cw; c.create_oval(x-rr,y-rr,x+rr,y+rr,outline="#355466",dash=(3,3)); c.create_text(x,y,text="S",fill="#57798a")
        for h in self.world.hazards:
            x,y=self.world_to_canvas(h.x,h.y); rr=h.radius/self.world.width*cw; c.create_oval(x-rr,y-rr,x+rr,y+rr,fill="#351821",outline=DANGER,width=2); c.create_text(x,y,text="!",fill=DANGER)
        for f in self.world.food:
            x,y=self.world_to_canvas(f.x,f.y); c.create_oval(x-4,y-4,x+4,y+4,fill=FOOD,outline="")
        for w in self.world.water:
            x,y=self.world_to_canvas(w.x,w.y); c.create_oval(x-5,y-5,x+5,y+5,fill=BLUE,outline="")
        for p in self.world.predators:
            x,y=self.world_to_canvas(p.x,p.y); c.create_polygon(x-10,y+8,x,y-10,x+10,y+8,fill=DANGER,outline="#ff98a5")
        for r in self.world.population:
            x,y=self.world_to_canvas(r.x,r.y); sel=r.id==self.selected_id; radius=9*r.genome.body_size; body="#e5fff4" if sel else ("#7bbcf2" if r.sex=="male" else "#e78bb7")
            if sel:c.create_oval(x-radius-10,y-radius-10,x+radius+10,y+radius+10,outline=ACCENT,width=2)
            hx,hy=x+(radius+5)*math.cos(r.angle),y+(radius+5)*math.sin(r.angle); c.create_line(x,y,hx,hy,fill=TEXT,width=2); c.create_oval(x-radius,y-radius,x+radius,y+radius,fill=body,outline="#061018")
            if self.show_labels:c.create_text(x,y-radius-9,text=f"#{r.id} {r.sex[0].upper()} G{r.generation}",fill=MUTED,font=("Segoe UI",7))
            if sel and self.show_rays:
                for ray in r.genome.rays:
                    ex,ey=self.world_to_canvas(r.x+math.cos(r.angle+ray.angle)*ray.length,r.y+math.sin(r.angle+ray.angle)*ray.length); c.create_line(x,y,ex,ey,fill="#2b6678",dash=(3,5))

    def update_inspector(self)->None:
        r=self.selected();self.inspector.configure(state="normal");self.inspector.delete("1.0","end")
        if r:
            h,t,fa,fe,cu,so,sl=r.drives(self.world);b=r.brain;mid=len(r.genome.rays)//2
            state,codes,cue,internal=r.observe(self.world);vals=b.values(state); action=ACTIONS[max(range(len(vals)),key=vals.__getitem__)]
            lines=[f"ROBOT #{r.id} • {r.sex.upper()} • GEN {r.generation}",f"age={r.age} health={r.health:.1f} energy={r.energy:.1f}/{r.genome.effective_max_energy():.1f}",f"hydration={r.hydration:.1f}/{r.genome.effective_max_hydration():.1f}",f"fitness={r.fitness:.2f} food={r.food_eaten} water={r.water_found} damage={r.damage_taken:.1f}","","COMPETING DRIVES",f"hunger     {h:.2f}  thirst      {t:.2f}",f"fatigue    {fa:.2f}  fear        {fe:.2f}",f"curiosity  {cu:.2f}  social      {so:.2f}",f"sleepiness {sl:.2f}","","SENSORY ATTENTION",f"center cue = {cue}",f"rays = {codes}",f"learned next action = {action}","","BRAIN / MEMORY",f"states={len(b.q)} associations={len(b.associations)}",f"working={len(b.working)} episodic={len(b.episodic)}",f"confidence={b.confidence:.2f} stress={b.stress:.2f}",f"arousal={b.arousal:.2f} valence={b.valence:.2f}",f"exploration={b.epsilon:.2f}","","EVOLVABLE BODY",f"size={r.genome.body_size:.2f} speed={r.genome.speed:.2f}",f"vision rays={len(r.genome.rays)} center={r.genome.rays[mid].length:.0f}px",f"learning α={r.genome.learning_rate:.3f} discount γ={r.genome.discount:.3f}",f"attachment={r.genome.attachment:.2f} patience={r.genome.patience:.2f}"]
            self.inspector.insert("1.0","\n".join(lines))
        else:self.inspector.insert("1.0","Click a robot to inspect its needs, sensory map, learning state, memory and genome.")
        self.inspector.configure(state="disabled")
    def update_metrics(self)->None:
        s=self.world.summary(); male=sum(r.sex=="male" for r in self.world.population); female=len(self.world.population)-male; lines=[f"GENERATION       {s['generation']}",f"ALIVE            {s['alive']:>3}/{s['population']}",f"MALE / FEMALE    {male:>3} / {female:<3}",f"TICK             {s['tick']:>5}",f"BEST FITNESS     {s['best_fitness']:>7}",f"AVG FITNESS      {s['avg_fitness']:>7}",f"LEARNED STATES   {s['known_states']:>7}",f"FOUNDERS BRED    {'YES' if s['founders_established'] else 'NO'}",f"NIGHT FACTOR     {self.world.night_factor():>7.2f}",f"SCENTS           {len(self.world.scents):>7}",f"FPS              {self.fps:>7.1f}"]
        self.metrics.configure(state="normal");self.metrics.delete("1.0","end");self.metrics.insert("1.0","\n".join(lines));self.metrics.configure(state="disabled")
    def loop(self)->None:
        now=time.perf_counter(); self.fps=1/max(1e-6,now-self.last); self.last=now
        if self.running:self.world.step(18 if self.fast else 3)
        self.draw(); self.update_inspector(); self.update_metrics(); self.root.after(25 if self.fast else 45,self.loop)


def run_headless(generations:int,population:int,seed:int)->int:
    world=World(seed=seed); world.configure(population=max(2,population)); world.reset(); world.run_generations(max(1,generations))
    print("EVOLVE HEADLESS RESULT")
    for row in world.history[-generations:]: print(row)
    return 0


def main()->int:
    parser=argparse.ArgumentParser(description="EVOLVE — self-contained 2D artificial-life laboratory")
    parser.add_argument("--headless",action="store_true"); parser.add_argument("--generations",type=int,default=5); parser.add_argument("--population",type=int,default=20); parser.add_argument("--seed",type=int,default=7)
    args=parser.parse_args()
    if args.headless:return run_headless(args.generations,args.population,args.seed)
    root=tk.Tk(); EvolveApp(root); root.mainloop(); return 0

if __name__ == "__main__": raise SystemExit(main())
