from __future__ import annotations

import argparse, math, time, tkinter as tk
from tkinter import filedialog, messagebox, ttk
from evolve_core_v2 import Robot, World, clamp

BG="#071018"; PANEL="#0c1720"; PANEL2="#101f2b"; TEXT="#eaf6fb"; MUTED="#8ba4b2"; ACCENT="#6be0b4"; WARN="#ffd166"; DANGER="#ff7180"; BLUE="#64b5ff"

class EvolveApp:
    def __init__(self, root: tk.Tk)->None:
        self.root=root; root.title("EVOLVE — Artificial Life Laboratory"); root.geometry("1450x900"); root.minsize(1180,720); root.configure(bg=BG)
        self.world=World(); self.running=True; self.fast=False; self.selected_id=None; self.show_rays=True; self.show_labels=False; self.last=time.perf_counter(); self.fps=0.0
        self.build(); self.bind_keys(); self.loop()

    def build(self)->None:
        st=ttk.Style(); st.theme_use("clam"); st.configure("TButton",padding=7,font=("Segoe UI",9,"bold")); st.configure("TEntry",padding=5); st.configure("TLabel",background=PANEL,foreground=TEXT); st.configure("Title.TLabel",background=PANEL,foreground="#fff",font=("Segoe UI",21,"bold")); st.configure("Sub.TLabel",background=PANEL,foreground=MUTED,font=("Segoe UI",9))
        header=tk.Frame(self.root,bg=PANEL,height=68); header.pack(fill="x"); ttk.Label(header,text="EVOLVE",style="Title.TLabel").pack(side="left",padx=20,pady=12); ttk.Label(header,text="2D ARTIFICIAL LIFE LAB • DOG-INSPIRED LEARNING",style="Sub.TLabel").pack(side="left",pady=20); self.status=ttk.Label(header,text="● RUNNING",background=PANEL,foreground=ACCENT,font=("Segoe UI",10,"bold")); self.status.pack(side="right",padx=20)
        body=tk.Frame(self.root,bg=BG); body.pack(fill="both",expand=True,padx=12,pady=12); scene=tk.Frame(body,bg=BG); scene.pack(side="left",fill="both",expand=True); panel=tk.Frame(body,bg=PANEL,width=340); panel.pack(side="right",fill="y",padx=(12,0)); self.canvas=tk.Canvas(scene,bg="#08131b",highlightthickness=1,highlightbackground="#1e3541"); self.canvas.pack(fill="both",expand=True); self.canvas.bind("<Button-1>",self.select_robot); self.build_controls(panel); self.build_inspector(panel)

    def build_controls(self,panel:tk.Frame)->None:
        box=tk.Frame(panel,bg=PANEL); box.pack(fill="x",padx=12,pady=10)
        for text,cmd in [("⏯  PAUSE / RESUME",self.toggle),("⏭  NEXT GENERATION",self.next_generation),("↻  RESET EXPERIMENT",self.reset),("⚡  FAST MODE",self.toggle_fast),("💾  SAVE SNAPSHOT",self.save_snapshot)]: ttk.Button(box,text=text,command=cmd).pack(fill="x",pady=2)
        ttk.Label(box,text="EXPERIMENTER POWERS",background=PANEL,foreground="#fff",font=("Segoe UI",11,"bold")).pack(anchor="w",pady=(12,5))
        for text,cmd in [("+ FOOD AT CURSOR",self.add_food),("+ WATER AT CURSOR",self.add_water),("+ HAZARD AT CURSOR",self.add_hazard),("+ PREDATOR AT CURSOR",self.add_predator),("REWARD SELECTED +10",lambda:self.reward(10)),("PUNISH SELECTED −10",lambda:self.reward(-10)),("HEAL SELECTED",self.heal),("BOOST SELECTED",self.boost),("☠ KILL SELECTED",self.kill),("TELEPORT SELECTED",self.teleport)]: ttk.Button(box,text=text,command=cmd).pack(fill="x",pady=1)
        self.rays=tk.BooleanVar(value=True); self.labels=tk.BooleanVar(value=False); ttk.Checkbutton(box,text="Show sensory rays",variable=self.rays,command=self.sync).pack(anchor="w"); ttk.Checkbutton(box,text="Show robot labels",variable=self.labels,command=self.sync).pack(anchor="w")
        ttk.Label(box,text="EXPERIMENT SETTINGS",background=PANEL,foreground="#fff",font=("Segoe UI",11,"bold")).pack(anchor="w",pady=(10,5)); self.vars={}
        for key in ["population","food","water","hazards","predators","mutation","episode"]:
            row=tk.Frame(box,bg=PANEL); row.pack(fill="x",pady=1); ttk.Label(row,text=key,background=PANEL,foreground=MUTED).pack(side="left"); v=tk.StringVar(value=str(self.world.experiment[key])); ttk.Entry(row,textvariable=v,width=10).pack(side="right"); self.vars[key]=v
        ttk.Button(box,text="APPLY + RESET",command=self.apply).pack(fill="x",pady=(5,2)); ttk.Label(box,text="The robot has no simulation flag. It only receives local senses and body state.",background=PANEL,foreground=MUTED,wraplength=300).pack(anchor="w",pady=8)

    def build_inspector(self,panel:tk.Frame)->None:
        tk.Frame(panel,bg="#233946",height=1).pack(fill="x",padx=12,pady=3); ttk.Label(panel,text="ROBOT LAB",background=PANEL,foreground="#fff",font=("Segoe UI",11,"bold")).pack(anchor="w",padx=12,pady=(7,5)); self.inspector=tk.Text(panel,height=25,bg=PANEL2,fg=TEXT,relief="flat",state="disabled",font=("Consolas",8),padx=9,pady=9); self.inspector.pack(fill="x",padx=12,pady=(0,8)); self.metrics=tk.Text(panel,height=9,bg=PANEL2,fg=TEXT,relief="flat",state="disabled",font=("Consolas",9),padx=9,pady=9); self.metrics.pack(fill="x",padx=12,pady=(0,12))
    def bind_keys(self)->None:
        self.root.bind("<space>",lambda _e:self.toggle()); self.root.bind("<f>",lambda _e:self.toggle_fast()); self.root.bind("<n>",lambda _e:self.next_generation()); self.root.bind("<r>",lambda _e:self.reset()); self.root.bind("<Escape>",lambda _e:self.root.destroy())
    def sync(self)->None: self.show_rays=self.rays.get(); self.show_labels=self.labels.get()
    def toggle(self)->None: self.running=not self.running; self.status.configure(text="● RUNNING" if self.running else "● PAUSED",foreground=ACCENT if self.running else WARN)
    def toggle_fast(self)->None: self.fast=not self.fast
    def reset(self)->None: self.world.reset(); self.selected_id=None; self.running=True; self.status.configure(text="● RUNNING",foreground=ACCENT)
    def apply(self)->None:
        try:
            for key,conv in [("population",int),("food",int),("water",int),("hazards",int),("predators",int),("mutation",float),("episode",int)]: self.world.experiment[key]=conv(self.vars[key].get())
            self.world.experiment["population"]=max(4,self.world.experiment["population"]); self.world.experiment["food"]=max(1,self.world.experiment["food"]); self.world.experiment["water"]=max(1,self.world.experiment["water"]); self.world.experiment["hazards"]=max(0,self.world.experiment["hazards"]); self.world.experiment["predators"]=max(0,self.world.experiment["predators"]); self.world.experiment["mutation"]=clamp(self.world.experiment["mutation"],0,1); self.world.experiment["episode"]=max(50,self.world.experiment["episode"]); self.reset()
        except ValueError: messagebox.showerror("Invalid settings","Enter valid numeric settings.")
    def next_generation(self)->None:
        self.running=False; start=self.world.generation
        for _ in range(int(self.world.experiment["episode"])+10): self.world.step(10); 
        self.running=True
        if self.world.generation==start: self.world.step(int(self.world.experiment["episode"]))
        self.status.configure(text="● RUNNING",foreground=ACCENT)
    def cursor(self)->tuple[float,float]:
        cx=self.root.winfo_pointerx()-self.canvas.winfo_rootx(); cy=self.root.winfo_pointery()-self.canvas.winfo_rooty(); return self.canvas_to_world(cx,cy)
    def add_food(self)->None:self.world.spawn_food(*self.cursor())
    def add_water(self)->None:self.world.spawn_water(*self.cursor())
    def add_hazard(self)->None:self.world.spawn_hazard(*self.cursor())
    def add_predator(self)->None:self.world.spawn_predator(*self.cursor())
    def selected(self)->Robot|None:return next((r for r in self.world.population if r.id==self.selected_id),None)
    def reward(self,a:float)->None:
        r=self.selected();
        if r:self.world.reward_robot(r.id,a)
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
    def canvas_to_world(self,x:float,y:float)->tuple[float,float]:return x/max(1,self.canvas.winfo_width())*self.world.width,y/max(1,self.canvas.winfo_height())*self.world.height
    def world_to_canvas(self,x:float,y:float)->tuple[float,float]:return x/self.world.width*max(1,self.canvas.winfo_width()),y/self.world.height*max(1,self.canvas.winfo_height())
    def select_robot(self,event:tk.Event)->None:
        x,y=self.canvas_to_world(event.x,event.y); r=min(self.world.population,key=lambda q:(q.x-x)**2+(q.y-y)**2,default=None)
        if r and math.hypot(r.x-x,r.y-y)<26:self.selected_id=r.id
    def draw(self)->None:
        c=self.canvas;c.delete("all");cw,ch=max(1,c.winfo_width()),max(1,c.winfo_height())
        for gx in range(0,self.world.width+1,50):x,_=self.world_to_canvas(gx,0);c.create_line(x,0,x,ch,fill="#10232e")
        for gy in range(0,self.world.height+1,50):_,y=self.world_to_canvas(0,gy);c.create_line(0,y,cw,y,fill="#10232e")
        for s in self.world.shelters:
            x,y=self.world_to_canvas(s.x,s.y);rr=s.radius/self.world.width*cw;c.create_oval(x-rr,y-rr,x+rr,y+rr,outline="#355466",dash=(3,3));c.create_text(x,y,text="S",fill="#57798a")
        for h in self.world.hazards:
            x,y=self.world_to_canvas(h.x,h.y);rr=h.radius/self.world.width*cw;c.create_oval(x-rr,y-rr,x+rr,y+rr,fill="#351821",outline=DANGER,width=2)
        for f in self.world.food:
            x,y=self.world_to_canvas(f.x,f.y);c.create_oval(x-4,y-4,x+4,y+4,fill="#90e59a",outline="")
        for w in self.world.water:
            x,y=self.world_to_canvas(w.x,w.y);c.create_oval(x-5,y-5,x+5,y+5,fill=BLUE,outline="")
        for p in self.world.predators:
            x,y=self.world_to_canvas(p.x,p.y);c.create_polygon(x-10,y+8,x,y-10,x+10,y+8,fill="#dc6678",outline="#ff98a5")
        for r in self.world.population:
            x,y=self.world_to_canvas(r.x,r.y);sel=r.id==self.selected_id
            if sel:c.create_oval(x-19,y-19,x+19,y+19,outline=ACCENT,width=2)
            hx,hy=x+13*math.cos(r.angle),y+13*math.sin(r.angle);body="#e5fff4" if sel else ("#7bbcf2" if r.sex=="male" else "#e78bb7");c.create_line(x,y,hx,hy,fill=TEXT,width=2);c.create_oval(x-9,y-9,x+9,y+9,fill=body,outline="#061018")
            if self.show_labels:c.create_text(x,y-19,text=f"#{r.id} {r.sex[0].upper()} G{r.generation}",fill=MUTED,font=("Segoe UI",7))
            if sel and self.show_rays:
                for off in RAY_OFFSETS:
                    ex,ey=self.world_to_canvas(r.x+math.cos(r.angle+off)*r.genome.vision,r.y+math.sin(r.angle+off)*r.genome.vision);c.create_line(x,y,ex,ey,fill="#2b6678",dash=(3,5))
    def update_inspector(self)->None:
        r=self.selected();self.inspector.configure(state="normal");self.inspector.delete("1.0","end")
        if r:
            h,t,fa,fe,cu,so=r.drives();b=r.brain;lines=[f"ROBOT #{r.id} • {r.sex.upper()} • GEN {r.generation}",f"age={r.age} health={r.health:.1f} energy={r.energy:.1f} water={r.hydration:.1f}",f"fitness={r.fitness:.2f} food={r.food_eaten} water={r.water_found}",f"damage={r.damage_taken:.1f} reward={r.recent_reward:.2f}","","DRIVES",f"hunger={h:.2f} thirst={t:.2f} fatigue={fa:.2f}",f"fear={fe:.2f} curiosity={cu:.2f} social={so:.2f}","","BRAIN",f"states={len(b.q)} working={len(b.working)} episodic={len(b.episodic)}",f"associations={len(b.associations)} confidence={b.confidence:.2f}",f"stress={b.stress:.2f} arousal={b.arousal:.2f} valence={b.valence:.2f}",f"exploration={b.epsilon:.2f}","","GENOME",f"speed={r.genome.speed:.2f} vision={r.genome.vision:.1f}",f"efficiency={r.genome.efficiency:.2f} curiosity={r.genome.curiosity:.2f}",f"boldness={r.genome.boldness:.2f} sociability={r.genome.sociability:.2f}",f"attachment={r.genome.attachment:.2f} patience={r.genome.patience:.2f}"]
            self.inspector.insert("1.0","\n".join(lines))
        else:self.inspector.insert("1.0","Click a robot to inspect its body, drives, brain, memory and genome.")
        self.inspector.configure(state="disabled")
    def update_metrics(self)->None:
        s=self.world.summary();m=sum(r.sex=="male" for r in self.world.population);f=sum(r.sex=="female" for r in self.world.population);found="YES" if s["founders_established"] else "NO";lines=[f"GENERATION      {s['generation']}",f"ALIVE           {s['alive']:>3}/{s['population']}",f"MALE/FEMALE     {m}/{f}",f"TICK            {s['tick']:>5}",f"BEST FITNESS    {s['best_fitness']:>7}",f"AVG FITNESS     {s['avg_fitness']:>7}",f"LEARNED STATES  {s['known_states']:>7}",f"FOUNDERS BRED   {found}",f"FPS             {self.fps:>7.1f}"]
        self.metrics.configure(state="normal");self.metrics.delete("1.0","end");self.metrics.insert("1.0","\n".join(lines));self.metrics.configure(state="disabled")
    def save_snapshot(self)->None:
        path=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("JSON","*.json")])
        if path:self.world.save_snapshot(path)
    def loop(self)->None:
        now=time.perf_counter();self.fps=1/max(1e-6,now-self.last);self.last=now
        if self.running:self.world.step(15 if self.fast else 3)
        self.draw();self.update_inspector();self.update_metrics();self.root.after(30 if self.fast else 50,self.loop)

RAY_OFFSETS=(-1,-0.5,-0.25,0,0.25,0.5,1)

def run_headless(generations:int,population:int,seed:int)->int:
    w=World(seed=seed);w.experiment["population"]=max(2,population);w.reset();w.run_generations(max(1,generations));print("EVOLVE HEADLESS RESULT");[print(row) for row in w.history[-generations:]];return 0

def main()->int:
    p=argparse.ArgumentParser(description="EVOLVE — 2D artificial-life laboratory");p.add_argument("--headless",action="store_true");p.add_argument("--generations",type=int,default=5);p.add_argument("--population",type=int,default=20);p.add_argument("--seed",type=int,default=7);a=p.parse_args()
    if a.headless:return run_headless(a.generations,a.population,a.seed)
    root=tk.Tk();EvolveApp(root);root.mainloop();return 0

if __name__=="__main__":raise SystemExit(main())
