from __future__ import annotations

import argparse
import math
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from evolve_engine import ACTIONS, Genome, Robot, World

BG="#071018"; PANEL="#0c1720"; PANEL2="#101f2b"; TEXT="#eaf6fb"; MUTED="#8ba4b2"; ACCENT="#6be0b4"; WARN="#ffd166"; DANGER="#ff7180"; BLUE="#64b5ff"; FOOD="#90e59a"; SOCIAL="#d49cff"

class EvolveApp:
    def __init__(self, root:tk.Tk)->None:
        self.root=root; root.title("EVOLVE — Artificial Life Laboratory"); root.geometry("1550x940"); root.minsize(1240,780); root.configure(bg=BG)
        self.world=World(); self.running=True; self.fast=False; self.selected_id=None; self.show_rays=True; self.show_labels=False; self.show_scents=True; self.last=time.perf_counter(); self.fps=0.0
        self.lineage_archive:dict[int,dict]={}
        self.build(); self.bind_keys(); self.loop()

    def archive_population(self)->None:
        for r in self.world.population:
            self.lineage_archive[r.id]={"id":r.id,"sex":r.sex,"generation":r.generation,"parent_ids":r.parent_ids,"fitness":r.fitness,"offspring":r.offspring}
        if len(self.lineage_archive)>5000:
            keep=sorted(self.lineage_archive.values(),key=lambda x:(x["generation"],x["id"]),reverse=True)[:5000]
            self.lineage_archive={item["id"]:item for item in keep}

    def build(self)->None:
        st=ttk.Style(); st.theme_use("clam"); st.configure("TButton",padding=7,font=("Segoe UI",9,"bold")); st.configure("TEntry",padding=5); st.configure("TNotebook",background=PANEL); st.configure("TNotebook.Tab",padding=(10,5)); st.configure("TLabel",background=PANEL,foreground=TEXT)
        header=tk.Frame(self.root,bg=PANEL,height=68); header.pack(fill="x"); ttk.Label(header,text="EVOLVE",font=("Segoe UI",21,"bold"),background=PANEL,foreground="#fff").pack(side="left",padx=20,pady=12); ttk.Label(header,text="2D ARTIFICIAL LIFE • DOG-INSPIRED COGNITION • EVOLUTIONARY LAB",background=PANEL,foreground=MUTED,font=("Segoe UI",9)).pack(side="left",pady=20); self.status=ttk.Label(header,text="● RUNNING",background=PANEL,foreground=ACCENT,font=("Segoe UI",10,"bold")); self.status.pack(side="right",padx=20)
        body=tk.Frame(self.root,bg=BG); body.pack(fill="both",expand=True,padx=12,pady=12); scene=tk.Frame(body,bg=BG); scene.pack(side="left",fill="both",expand=True); side=tk.Frame(body,bg=PANEL,width=390); side.pack(side="right",fill="y",padx=(12,0))
        self.canvas=tk.Canvas(scene,bg="#08131b",highlightthickness=1,highlightbackground="#1e3541"); self.canvas.pack(fill="both",expand=True); self.canvas.bind("<Button-1>",self.select_robot)
        self._controls(side); self._tabs(side)

    def _controls(self,panel:tk.Frame)->None:
        box=tk.Frame(panel,bg=PANEL); box.pack(fill="x",padx=12,pady=9)
        for text,cmd in [("⏯  PAUSE / RESUME",self.toggle),("⏭  FORCE NEXT GENERATION",self.next_generation),("↻  RESET EXPERIMENT",self.reset),("⚡  FAST MODE",self.toggle_fast),("💾  SAVE WORLD SNAPSHOT",self.save_snapshot),("🧬  EXPORT SELECTED GENOME",self.export_genome)]: ttk.Button(box,text=text,command=cmd).pack(fill="x",pady=2)
        ttk.Label(box,text="EXPERIMENTER POWERS",background=PANEL,foreground="#fff",font=("Segoe UI",11,"bold")).pack(anchor="w",pady=(10,4))
        for text,cmd in [("+ FOOD AT CURSOR",self.add_food),("+ WATER AT CURSOR",self.add_water),("+ HAZARD AT CURSOR",self.add_hazard),("+ PREDATOR AT CURSOR",self.add_predator),("REWARD SELECTED +10",lambda:self.reward(10)),("PUNISH SELECTED −10",lambda:self.reward(-10)),("HEAL SELECTED",self.heal),("BOOST SELECTED",self.boost),("☠ KILL SELECTED",self.kill),("TELEPORT SELECTED",self.teleport)]: ttk.Button(box,text=text,command=cmd).pack(fill="x",pady=1)
        self.rays=tk.BooleanVar(value=True); self.labels=tk.BooleanVar(value=False); self.scents=tk.BooleanVar(value=True)
        for text,var in [("Show evolved sensory rays",self.rays),("Show robot labels",self.labels),("Show scent trails",self.scents)]: ttk.Checkbutton(box,text=text,variable=var,command=self.sync).pack(anchor="w")
        ttk.Label(box,text="EXPERIMENT",background=PANEL,foreground="#fff",font=("Segoe UI",11,"bold")).pack(anchor="w",pady=(9,4)); self.vars={}
        for key in ["population","food","water","hazards","predators","mutation","episode"]:
            row=tk.Frame(box,bg=PANEL); row.pack(fill="x",pady=1); ttk.Label(row,text=key,background=PANEL,foreground=MUTED).pack(side="left"); v=tk.StringVar(value=str(self.world.experiment[key])); ttk.Entry(row,textvariable=v,width=10).pack(side="right"); self.vars[key]=v
        ttk.Button(box,text="APPLY + RESET",command=self.apply).pack(fill="x",pady=(5,2))

    def _tabs(self,panel:tk.Frame)->None:
        nb=ttk.Notebook(panel); nb.pack(fill="both",expand=True,padx=8,pady=8)
        brain_tab=tk.Frame(nb,bg=PANEL); lineage_tab=tk.Frame(nb,bg=PANEL); analytics_tab=tk.Frame(nb,bg=PANEL); nb.add(brain_tab,text="BRAIN"); nb.add(lineage_tab,text="LINEAGE"); nb.add(analytics_tab,text="ANALYTICS")
        ttk.Label(brain_tab,text="LIVE BRAIN MAP",background=PANEL,foreground="#fff",font=("Segoe UI",11,"bold")).pack(anchor="w",padx=8,pady=(8,4)); self.brain_canvas=tk.Canvas(brain_tab,height=230,bg=PANEL2,highlightthickness=0); self.brain_canvas.pack(fill="x",padx=8,pady=4); self.inspector=tk.Text(brain_tab,height=18,bg=PANEL2,fg=TEXT,relief="flat",state="disabled",font=("Consolas",8),padx=8,pady=8); self.inspector.pack(fill="both",expand=True,padx=8,pady=6)
        ttk.Label(lineage_tab,text="FAMILY TREE",background=PANEL,foreground="#fff",font=("Segoe UI",11,"bold")).pack(anchor="w",padx=8,pady=(8,4)); self.lineage=tk.Canvas(lineage_tab,height=260,bg=PANEL2,highlightthickness=0); self.lineage.pack(fill="x",padx=8,pady=4); self.lineage_text=tk.Text(lineage_tab,height=12,bg=PANEL2,fg=TEXT,relief="flat",state="disabled",font=("Consolas",8),padx=8,pady=8); self.lineage_text.pack(fill="both",expand=True,padx=8,pady=6)
        ttk.Label(analytics_tab,text="MACRO ECOSYSTEM",background=PANEL,foreground="#fff",font=("Segoe UI",11,"bold")).pack(anchor="w",padx=8,pady=(8,4)); self.graph=tk.Canvas(analytics_tab,height=260,bg=PANEL2,highlightthickness=0); self.graph.pack(fill="x",padx=8,pady=4); self.metrics=tk.Text(analytics_tab,height=14,bg=PANEL2,fg=TEXT,relief="flat",state="disabled",font=("Consolas",8),padx=8,pady=8); self.metrics.pack(fill="both",expand=True,padx=8,pady=6)

    def bind_keys(self)->None:
        self.root.bind("<space>",lambda _e:self.toggle()); self.root.bind("<f>",lambda _e:self.toggle_fast()); self.root.bind("<n>",lambda _e:self.next_generation()); self.root.bind("<r>",lambda _e:self.reset()); self.root.bind("<Escape>",lambda _e:self.root.destroy())
    def sync(self)->None:self.show_rays=self.rays.get();self.show_labels=self.labels.get();self.show_scents=self.scents.get()
    def toggle(self)->None:self.running=not self.running;self.status.configure(text="● RUNNING" if self.running else "● PAUSED",foreground=ACCENT if self.running else WARN)
    def toggle_fast(self)->None:self.fast=not self.fast
    def reset(self)->None:self.world.reset();self.lineage_archive.clear();self.selected_id=None;self.running=True;self.status.configure(text="● RUNNING",foreground=ACCENT)
    def apply(self)->None:
        try:self.world.configure(**{k:(int(v) if k!="mutation" else float(v)) for k,v in ((key,self.vars[key].get()) for key in self.vars)});self.reset()
        except ValueError:messagebox.showerror("Invalid settings","Enter valid numeric settings.")
    def next_generation(self)->None:
        self.running=False;start=self.world.generation
        self.archive_population()
        for _ in range(self.world.experiment["episode"]//10+3):
            self.world.step(10)
            if self.world.generation!=start:break
        self.running=True
    def cursor(self)->tuple[float,float]:
        cx=self.root.winfo_pointerx()-self.canvas.winfo_rootx();cy=self.root.winfo_pointery()-self.canvas.winfo_rooty();return self.canvas_to_world(cx,cy)
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
    def export_genome(self)->None:
        r=self.selected();
        if not r:return
        path=filedialog.asksaveasfilename(defaultextension=".genome.json",filetypes=[("Genome JSON","*.genome.json")])
        if path:World.save_genome(r,path)
    def save_snapshot(self)->None:
        path=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("JSON","*.json")])
        if path:self.world.save_snapshot(path)
    def canvas_to_world(self,x:float,y:float)->tuple[float,float]:return x/max(1,self.canvas.winfo_width())*self.world.width,y/max(1,self.canvas.winfo_height())*self.world.height
    def world_to_canvas(self,x:float,y:float)->tuple[float,float]:return x/self.world.width*max(1,self.canvas.winfo_width()),y/self.world.height*max(1,self.canvas.winfo_height())
    def select_robot(self,event:tk.Event)->None:
        x,y=self.canvas_to_world(event.x,event.y);r=min(self.world.population,key=lambda q:(q.x-x)**2+(q.y-y)**2,default=None)
        if r and math.hypot(r.x-x,r.y-y)<35:self.selected_id=r.id
    def draw(self)->None:
        c=self.canvas;c.delete("all");cw,ch=max(1,c.winfo_width()),max(1,c.winfo_height())
        for gx in range(0,self.world.width+1,50):x,_=self.world_to_canvas(gx,0);c.create_line(x,0,x,ch,fill="#10232e")
        for gy in range(0,self.world.height+1,50):_,y=self.world_to_canvas(0,gy);c.create_line(0,y,cw,y,fill="#10232e")
        if self.show_scents:
            for s in self.world.scents[::3]:
                x,y=self.world_to_canvas(s.x,s.y);r=max(2,7*s.strength);c.create_oval(x-r,y-r,x+r,y+r,outline=FOOD if s.kind=="food" else DANGER)
        for s in self.world.shelters:
            x,y=self.world_to_canvas(s.x,s.y);rr=s.radius/self.world.width*cw;c.create_oval(x-rr,y-rr,x+rr,y+rr,outline="#355466",dash=(3,3));c.create_text(x,y,text="S",fill="#57798a")
        for h in self.world.hazards:
            x,y=self.world_to_canvas(h.x,h.y);rr=h.radius/self.world.width*cw;c.create_oval(x-rr,y-rr,x+rr,y+rr,fill="#351821",outline=DANGER,width=2);c.create_text(x,y,text="!",fill=DANGER)
        for f in self.world.food:
            x,y=self.world_to_canvas(f.x,f.y);c.create_oval(x-4,y-4,x+4,y+4,fill=FOOD,outline="")
        for w in self.world.water:
            x,y=self.world_to_canvas(w.x,w.y);c.create_oval(x-5,y-5,x+5,y+5,fill=BLUE,outline="")
        for p in self.world.predators:
            x,y=self.world_to_canvas(p.x,p.y);c.create_polygon(x-10,y+8,x,y-10,x+10,y+8,fill=DANGER,outline="#ff98a5")
        for r in self.world.population:
            x,y=self.world_to_canvas(r.x,r.y);sel=r.id==self.selected_id;rr=9*r.genome.body_size;body="#e5fff4" if sel else ("#7bbcf2" if r.sex=="male" else "#e78bb7")
            if sel:c.create_oval(x-rr-10,y-rr-10,x+rr+10,y+rr+10,outline=ACCENT,width=2)
            hx,hy=x+(rr+5)*math.cos(r.angle),y+(rr+5)*math.sin(r.angle);c.create_line(x,y,hx,hy,fill=TEXT,width=2);c.create_oval(x-rr,y-rr,x+rr,y+rr,fill=body,outline="#061018")
            if self.show_labels:c.create_text(x,y-rr-9,text=f"#{r.id} {r.sex[0].upper()} G{r.generation}",fill=MUTED,font=("Segoe UI",7))
            if sel and self.show_rays:
                for ray in r.genome.rays:
                    ex,ey=self.world_to_canvas(r.x+math.cos(r.angle+ray.angle)*ray.length,r.y+math.sin(r.angle+ray.angle)*ray.length);c.create_line(x,y,ex,ey,fill="#2b6678",dash=(3,5))
    def bars(self,canvas:tk.Canvas,values:list[float],labels:list[str])->None:
        canvas.delete("all");w=max(1,canvas.winfo_width());h=max(1,canvas.winfo_height());n=len(values);gap=8;bw=max(18,(w-gap*(n+1))/n)
        for i,(v,label) in enumerate(zip(values,labels)):
            x=gap+i*(bw+gap);barh=max(2,(h-55)*max(0,min(1,v)));canvas.create_rectangle(x,h-25-barh,x+bw,h-25,fill=ACCENT,outline="");canvas.create_text(x+bw/2,h-14,text=label,fill=MUTED,font=("Segoe UI",8));canvas.create_text(x+bw/2,h-31-barh,text=f"{v:.2f}",fill=TEXT,font=("Consolas",8))
    def update_brain(self)->None:
        r=self.selected();
        if not r:self.brain_canvas.delete("all");self.inspector.configure(state="normal");self.inspector.delete("1.0","end");self.inspector.insert("1.0","Select a robot to map its live brain.");self.inspector.configure(state="disabled");return
        state,codes,cue,_=r.observe(self.world);h,t,fa,fe,cu,so,sl=r.drives(self.world);self.bars(self.brain_canvas,[h,t,fa,fe,cu,so,sl],["HUN","THI","FAT","FEAR","CUR","SOC","SLEEP"]);b=r.brain;vals=b.values(state);preferred=ACTIONS[max(range(len(vals)),key=vals.__getitem__)];lines=[f"ROBOT #{r.id} • {r.sex.upper()} • GEN {r.generation}",f"age={r.age} health={r.health:.1f} energy={r.energy:.1f}/{r.genome.effective_max_energy():.1f}",f"hydration={r.hydration:.1f}/{r.genome.effective_max_hydration():.1f}",f"fitness={r.fitness:.2f} food={r.food_eaten} water={r.water_found} damage={r.damage_taken:.1f}","","SENSORY ATTENTION",f"cue={cue} codes={codes}","","BRAIN / MEMORY",f"states={len(b.q)} associations={len(b.associations)}",f"working={len(b.working)} episodic={len(b.episodic)}",f"confidence={b.confidence:.2f} stress={b.stress:.2f} arousal={b.arousal:.2f}",f"valence={b.valence:.2f} exploration={b.epsilon:.2f}",f"preferred action={preferred}","","EVOLVABLE BODY",f"size={r.genome.body_size:.2f} speed={r.genome.speed:.2f} efficiency={r.genome.efficiency:.2f}",f"learning α={r.genome.learning_rate:.3f} discount γ={r.genome.discount:.3f} memory={r.genome.memory_capacity}",f"rays={[(round(x.angle,2),round(x.length)) for x in r.genome.rays]}"]
        self.inspector.configure(state="normal");self.inspector.delete("1.0","end");self.inspector.insert("1.0","\n".join(lines));self.inspector.configure(state="disabled")
    def lineage_lookup(self,robot_id:int)->dict|None:
        current=next((r for r in self.world.population if r.id==robot_id),None)
        if current:return {"id":current.id,"sex":current.sex,"generation":current.generation,"parent_ids":current.parent_ids,"fitness":current.fitness,"offspring":current.offspring}
        return self.lineage_archive.get(robot_id)
    def update_lineage(self)->None:
        r=self.selected();self.lineage.delete("all");self.lineage_text.configure(state="normal");self.lineage_text.delete("1.0","end")
        if not r:self.lineage_text.insert("1.0","Select an evolved robot to inspect its lineage.");self.lineage_text.configure(state="disabled");return
        chain=[r];seen={r.id}
        while len(chain)<6:
            pid=next((p for p in chain[-1].parent_ids if p),0)
            parent=self.lineage_lookup(pid) if pid else None
            if not parent or parent["id"] in seen:break
            chain.append(parent);seen.add(parent["id"])
        w=max(1,self.lineage.winfo_width());y=48;gap=min(105,max(65,(w-80)/max(1,len(chain)-1)))
        for i,node in enumerate(chain):
            x=35+i*gap;fill="#7bbcf2" if node["sex"]=="male" else "#e78bb7";self.lineage.create_oval(x-18,y-18,x+18,y+18,fill=fill,outline=ACCENT if i==0 else "#2a4351",width=2);self.lineage.create_text(x,y+34,text=f"#{node['id']}\nG{node['generation']}",fill=TEXT,font=("Segoe UI",8));
            if i+1<len(chain):self.lineage.create_line(x+18,y,x+gap-18,y,fill="#3f6878",arrow="last")
        lines=[f"SELECTED #{r.id}",f"parents={r.parent_ids}",f"generation={r.generation}",f"offspring={r.offspring}","","ANCESTRAL PATH"]+[f"#{n['id']}  G{n['generation']}  {n['sex']}  fitness={n.get('fitness',0):.2f}" for n in chain];self.lineage_text.insert("1.0","\n".join(lines));self.lineage_text.configure(state="disabled")
    def update_graph(self)->None:
        c=self.graph;c.delete("all");w=max(1,c.winfo_width());h=max(1,c.winfo_height());hist=self.world.history[-50:]
        if not hist:return
        series=[("fitness",lambda x:x.get("best_fitness",0)),("food",lambda x:x.get("food",0)),("predators",lambda x:x.get("predators",0))];mx=max(1,max(max(abs(fn(row)) for row in hist) for _,fn in series));step=(w-45)/max(1,len(hist)-1)
        for idx,(name,fn) in enumerate(series):
            points=[]
            for i,row in enumerate(hist):points += [45+i*step,h-20-(fn(row)/mx)*(h-45)]
            c.create_line(*points,fill=[ACCENT,FOOD,DANGER][idx],width=2);c.create_text(8,20+idx*20,text=name,anchor="w",fill=[ACCENT,FOOD,DANGER][idx],font=("Segoe UI",8))
        c.create_line(40,10,40,h-20,fill="#36515e");c.create_line(40,h-20,w,h-20,fill="#36515e")
    def update_metrics(self)->None:
        s=self.world.summary();lines=[f"GENERATION       {s['generation']}",f"ALIVE            {s['alive']:>3}/{s['population']}",f"BEST FITNESS     {s['best_fitness']:>8.2f}",f"AVG FITNESS      {s['avg_fitness']:>8.2f}",f"LEARNED STATES   {s['known_states']:>8}",f"FOUNDERS BRED    {'YES' if s['founders_established'] else 'NO'}",f"NIGHT FACTOR     {self.world.night_factor():>8.2f}",f"SCENT MARKERS    {len(self.world.scents):>8}",f"ARCHIVED LINEAGE {len(self.lineage_archive):>8}",f"FPS              {self.fps:>8.1f}","","Controls: SPACE pause • F fast • N generation • R reset"]
        self.metrics.configure(state="normal");self.metrics.delete("1.0","end");self.metrics.insert("1.0","\n".join(lines));self.metrics.configure(state="disabled")
    def loop(self)->None:
        now=time.perf_counter();self.fps=1/max(1e-6,now-self.last);self.last=now
        if self.running:
            self.archive_population()
            self.world.step(20 if self.fast else 3)
        self.draw();self.update_brain();self.update_lineage();self.update_graph();self.update_metrics();self.root.after(25 if self.fast else 45,self.loop)


def run_headless(generations:int,population:int,seed:int)->int:
    world=World(seed=seed);world.configure(population=max(2,population));world.reset();world.run_generations(max(1,generations));print("EVOLVE HEADLESS RESULT");
    for row in world.history[-generations:]:print(row)
    return 0


def main()->int:
    p=argparse.ArgumentParser(description="EVOLVE — self-contained 2D artificial-life laboratory");p.add_argument("--headless",action="store_true");p.add_argument("--generations",type=int,default=5);p.add_argument("--population",type=int,default=20);p.add_argument("--seed",type=int,default=7);a=p.parse_args()
    if a.headless:return run_headless(a.generations,a.population,a.seed)
    root=tk.Tk();EvolveApp(root);root.mainloop();return 0

if __name__=="__main__":raise SystemExit(main())
