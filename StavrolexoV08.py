import math
import random
import threading
import time
import tkinter as tk
import unicodedata
from tkinter import ttk, messagebox, filedialog
from collections import deque, defaultdict

# ==========================================
# 1. ΚΛΑΣΕΙΣ ΠΥΡΗΝΑ (Λεξικό, Πλέγμα, Επίλυση)
# ==========================================
class DictionaryManager:
    def __init__(self, words_list):
        self.by_length = defaultdict(set)
        # Inverted Index για αστραπιαία αναζήτηση (Χωρίς Regex!)
        self.index = defaultdict(lambda: defaultdict(set))
        self.stats = defaultdict(lambda: defaultdict(int))
        self.totals = defaultdict(int)
        self.total_words = 0
        
        for word in words_list:
            # 1. Αφαιρούμε κενά και τα κάνουμε όλα κεφαλαία
            word = word.strip().upper()
            
            # 2. ΑΦΑΙΡΕΣΗ ΤΟΝΩΝ ΚΑΙ ΔΙΑΛΥΤΙΚΩΝ
            # Το NFD χωρίζει τους χαρακτήρες από τους τόνους τους. 
            # Το 'Mn' (Mark, Nonspacing) είναι η κατηγορία των τόνων, οπότε τους αγνοούμε!
            word = ''.join(c for c in unicodedata.normalize('NFD', word) if unicodedata.category(c) != 'Mn')
            
            # 3. Αγνοούμε λέξεις μικρότερες των 3 γραμμάτων ή κενές
            if len(word) < 3: continue
            
            length = len(word)
            self.by_length[length].add(word)
            self.totals[length] += 1
            self.total_words += 1
            
            for i, char in enumerate(word):
                self.index[length][(i, char)].add(word)
                self.stats[length][(i, char)] += 1

    def get_matches(self, pattern, length):
        possible_words = self.by_length[length]
        for i, char in enumerate(pattern):
            if char != '.':
                possible_words = possible_words.intersection(self.index[length][(i, char)])
                if not possible_words: 
                    break 
        return list(possible_words)

    def get_log_prob(self, char, index, length):
        count = self.stats[length].get((index, char), 0)
        total = self.totals[length]
        if total == 0: return -float('inf')
        prob = (count + 1) / (total + 24) 
        return math.log(prob)

class Variable:
    def __init__(self, vid, direction, cells):
        self.id = vid
        self.direction = direction
        self.cells = cells
        self.length = len(cells)

    def get_index_of(self, r, c):
        return self.cells.index((r, c))

class CrosswordGrid:
    def __init__(self, size, black_ratio):
        self.size = size
        self.black_ratio = black_ratio
        self.grid = [[0 for _ in range(size)] for _ in range(size)]
        self.variables = {}
        self.intersections = defaultdict(dict)
            
    def generate_topology(self):
        target_blacks = int((self.size * self.size) * self.black_ratio)
        max_attempts = 200
        
        for attempt in range(max_attempts):
            self.grid = [[0 for _ in range(self.size)] for _ in range(self.size)]
            candidates = [(r, c) for r in range(self.size) for c in range(self.size)]
            center = self.size / 2.0
            candidates.sort(key=lambda pos: (math.hypot(pos[0] - center, pos[1] - center)) + random.uniform(-self.size/2, self.size/2))
            
            for r, c in candidates:
                if self._count_blacks() >= target_blacks: break
                if self.grid[r][c] == 1: continue
                    
                backup = [row[:] for row in self.grid]
                self.grid[r][c] = 1
                self.grid[self.size - 1 - r][self.size - 1 - c] = 1
                self._enforce_word_lengths()
                
                if not self._is_connected() or self._has_2x2_blocks():
                    self.grid = backup
                    
            if self._has_valid_word_lengths() and self._is_connected() and not self._has_2x2_blocks():
                self._extract_variables()
                return True
        return False

    def _count_blacks(self): return sum(row.count(1) for row in self.grid)

    def _has_2x2_blocks(self):
        for r in range(self.size - 1):
            for c in range(self.size - 1):
                if (self.grid[r][c] == 1 and self.grid[r+1][c] == 1 and 
                    self.grid[r][c+1] == 1 and self.grid[r+1][c+1] == 1): return True
        return False

    def _enforce_word_lengths(self):
        changed = True
        while changed:
            changed = False
            for r in range(self.size):
                length, start_c = 0, 0
                for c in range(self.size):
                    if self.grid[r][c] == 0:
                        if length == 0: start_c = c
                        length += 1
                    else:
                        if 0 < length < 3:
                            for i in range(start_c, c):
                                if self.grid[r][i] == 0:
                                    self.grid[r][i] = 1
                                    self.grid[self.size - 1 - r][self.size - 1 - i] = 1
                                    changed = True
                        length = 0
                if 0 < length < 3:
                    for i in range(start_c, self.size):
                        if self.grid[r][i] == 0:
                            self.grid[r][i] = 1
                            self.grid[self.size - 1 - r][self.size - 1 - i] = 1
                            changed = True
            for c in range(self.size):
                length, start_r = 0, 0
                for r in range(self.size):
                    if self.grid[r][c] == 0:
                        if length == 0: start_r = r
                        length += 1
                    else:
                        if 0 < length < 3:
                            for i in range(start_r, r):
                                if self.grid[i][c] == 0:
                                    self.grid[i][c] = 1
                                    self.grid[self.size - 1 - i][self.size - 1 - c] = 1
                                    changed = True
                        length = 0
                if 0 < length < 3:
                    for i in range(start_r, self.size):
                        if self.grid[i][c] == 0:
                            self.grid[i][c] = 1
                            self.grid[self.size - 1 - i][self.size - 1 - c] = 1
                            changed = True

    def _is_connected(self):
        start_cell = None
        white_count = 0
        for r in range(self.size):
            for c in range(self.size):
                if self.grid[r][c] == 0:
                    white_count += 1
                    if not start_cell: start_cell = (r, c)
        if not start_cell: return False
        
        visited = set([start_cell])
        queue = deque([start_cell])
        directions = [(-1,0), (1,0), (0,-1), (0,1)]
        
        while queue:
            r, c = queue.popleft()
            for dr, dc in directions:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.size and 0 <= nc < self.size and self.grid[nr][nc] == 0:
                    if (nr, nc) not in visited:
                        visited.add((nr, nc))
                        queue.append((nr, nc))
        return len(visited) == white_count

    def _has_valid_word_lengths(self):
        for r in range(self.size):
            length = 0
            for c in range(self.size):
                if self.grid[r][c] == 0: length += 1
                else:
                    if 0 < length < 3: return False
                    length = 0
            if 0 < length < 3: return False
        for c in range(self.size):
            length = 0
            for r in range(self.size):
                if self.grid[r][c] == 0: length += 1
                else:
                    if 0 < length < 3: return False
                    length = 0
            if 0 < length < 3: return False
        return True

    def _extract_variables(self):
        self.variables.clear()
        self.intersections.clear()
        vid = 0
        cell_to_vars = defaultdict(list)
        
        for r in range(self.size):
            cells = []
            for c in range(self.size):
                if self.grid[r][c] == 0: cells.append((r, c))
                else:
                    if len(cells) >= 3:
                        var = Variable(vid, 'H', cells)
                        self.variables[vid] = var
                        for cell in cells: cell_to_vars[cell].append(vid)
                        vid += 1
                    cells = []
            if len(cells) >= 3:
                var = Variable(vid, 'H', cells)
                self.variables[vid] = var
                for cell in cells: cell_to_vars[cell].append(vid)
                vid += 1
                
        for c in range(self.size):
            cells = []
            for r in range(self.size):
                if self.grid[r][c] == 0: cells.append((r, c))
                else:
                    if len(cells) >= 3:
                        var = Variable(vid, 'V', cells)
                        self.variables[vid] = var
                        for cell in cells: cell_to_vars[cell].append(vid)
                        vid += 1
                    cells = []
            if len(cells) >= 3:
                var = Variable(vid, 'V', cells)
                self.variables[vid] = var
                for cell in cells: cell_to_vars[cell].append(vid)
                vid += 1

        for cell, vids in cell_to_vars.items():
            if len(vids) == 2:
                v1, v2 = vids[0], vids[1]
                idx1 = self.variables[v1].get_index_of(*cell)
                idx2 = self.variables[v2].get_index_of(*cell)
                self.intersections[v1][v2] = (idx1, idx2)
                self.intersections[v2][v1] = (idx2, idx1)

class CSPSolver:
    def __init__(self, grid, dict_mgr):
        self.grid = grid
        self.dict = dict_mgr
        self.nodes_visited = 0
        self.stop_flag = False

    def get_current_pattern(self, var, assignment):
        pattern = ["."] * var.length
        for neighbor_id, (my_idx, neigh_idx) in self.grid.intersections[var.id].items():
            if neighbor_id in assignment:
                pattern[my_idx] = assignment[neighbor_id][neigh_idx]
        return pattern

    def select_unassigned_variable(self, assignment):
        unassigned = [v for k, v in self.grid.variables.items() if k not in assignment]
        best_var = None
        min_score = float('inf')
        
        for var in unassigned:
            pattern = self.get_current_pattern(var, assignment)
            domain_size = len(self.dict.get_matches(pattern, var.length))
            degree = sum(1 for n_id in self.grid.intersections[var.id] if n_id not in assignment)
            score = domain_size - (degree * 0.1) 
            
            if score < min_score:
                min_score = score
                best_var = var
        return best_var

    def order_domain_values(self, var, domain, assignment):
        neighbors_info = []
        for neighbor_id, (my_idx, neigh_idx) in self.grid.intersections[var.id].items():
            if neighbor_id not in assignment:
                neigh_len = self.grid.variables[neighbor_id].length
                neighbors_info.append((my_idx, neigh_idx, neigh_len))

        scored_words = []
        for word in domain:
            score = 0.0
            for my_idx, neigh_idx, neigh_len in neighbors_info:
                char = word[my_idx]
                score += self.dict.get_log_prob(char, neigh_idx, neigh_len)
            scored_words.append((score, word))
            
        scored_words.sort(key=lambda x: x[0], reverse=True)
        return [w for score, w in scored_words]

    def forward_check(self, var, assignment, used_words):
        for neighbor_id in self.grid.intersections[var.id]:
            if neighbor_id not in assignment:
                neighbor = self.grid.variables[neighbor_id]
                pattern = self.get_current_pattern(neighbor, assignment)
                matches = self.dict.get_matches(pattern, neighbor.length)
                
                if not any(m not in used_words for m in matches):
                    return False
        return True

    def solve(self, assignment=None, used_words=None):
        if assignment is None: 
            assignment = {}
            used_words = set()
            
        if self.stop_flag: return None
        
        if len(assignment) == len(self.grid.variables):
            return assignment
            
        var = self.select_unassigned_variable(assignment)
        if not var: return None
        
        pattern = self.get_current_pattern(var, assignment)
        domain = self.dict.get_matches(pattern, var.length)
        ordered_domain = self.order_domain_values(var, domain, assignment)
        
        for word in ordered_domain:
            if word in used_words:
                continue
                
            self.nodes_visited += 1
            assignment[var.id] = word
            used_words.add(word)
            
            if self.forward_check(var, assignment, used_words):
                result = self.solve(assignment, used_words)
                if result: return result
                    
            del assignment[var.id]
            used_words.remove(word)
            
        return None

# ==========================================
# 2. ΓΡΑΦΙΚΟ ΠΕΡΙΒΑΛΛΟΝ (GUI) με Tkinter
# ==========================================
class CrosswordApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Αυτόματη Παραγωγή Σταυρολέξων (AI) - Σταθερή Έκδοση")
        self.root.geometry("850x650")
        sample_words = ["ΑΕΡΑΣ", "ΑΛΟΓΟ", "ΒΟΥΝΟ", "ΓΑΤΑ", "ΔΕΝΤΡΟ", "ΕΛΙΕΣ", "ΗΛΙΟΣ", "ΝΕΡΟ"]
        self.dict_mgr = DictionaryManager(sample_words)
        self.grid = None
        self.solver = None
        self.create_widgets()

    def create_widgets(self):
        control_frame = ttk.Frame(self.root, padding="10", width=250)
        control_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        ttk.Label(control_frame, text="1. Δεδομένα", font=("Helvetica", 12, "bold")).pack(pady=(10, 5))
        self.btn_load = ttk.Button(control_frame, text="Φόρτωση Λεξικού (.txt)", command=self.load_dictionary)
        self.btn_load.pack(fill=tk.X, pady=5)
        self.lbl_dict_info = ttk.Label(control_frame, text=f"Λέξεις: {self.dict_mgr.total_words} (Εικονικό)")
        self.lbl_dict_info.pack(pady=5)
        
        ttk.Separator(control_frame, orient='horizontal').pack(fill=tk.X, pady=15)
        
        ttk.Label(control_frame, text="2. Ρυθμίσεις Πλέγματος", font=("Helvetica", 12, "bold")).pack(pady=5)
        ttk.Label(control_frame, text="Διάσταση (π.χ. 8 για 8x8):").pack(anchor=tk.W)
        self.size_var = tk.IntVar(value=8)
        ttk.Entry(control_frame, textvariable=self.size_var).pack(fill=tk.X, pady=5)
        
        ttk.Label(control_frame, text="Ποσοστό Μαύρων (0.1 - 0.3):").pack(anchor=tk.W)
        self.ratio_var = tk.DoubleVar(value=0.15)
        ttk.Entry(control_frame, textvariable=self.ratio_var).pack(fill=tk.X, pady=5)
        
        self.btn_generate = ttk.Button(control_frame, text="Παραγωγή Τοπολογίας", command=self.generate_grid)
        self.btn_generate.pack(fill=tk.X, pady=15)
        
        ttk.Separator(control_frame, orient='horizontal').pack(fill=tk.X, pady=15)
        
        self.btn_solve = ttk.Button(control_frame, text="3. Επίλυση (AI)", command=self.start_solving, state=tk.DISABLED)
        self.btn_solve.pack(fill=tk.X, pady=5)
        
        self.status_var = tk.StringVar(value="Κατάσταση: Αναμονή")
        ttk.Label(control_frame, textvariable=self.status_var, foreground="blue", wraplength=200).pack(pady=20)
        
        canvas_frame = ttk.Frame(self.root, padding="10")
        canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(canvas_frame, bg="white", borderwidth=2, relief="sunken")
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def load_dictionary(self):
        filepath = filedialog.askopenfilename(title="Επιλογή Λεξικού", filetypes=(("Text files", "*.txt"), ("All files", "*.*")))
        if not filepath: return
        self.status_var.set("Κατάσταση: Φόρτωση λεξικού (Δημιουργία Ευρετηρίου)...")
        self.root.update()
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                words = f.readlines()
            self.dict_mgr = DictionaryManager(words)
            self.lbl_dict_info.config(text=f"Λέξεις: {self.dict_mgr.total_words}")
            self.status_var.set("Κατάσταση: Το λεξικό φορτώθηκε!")
            messagebox.showinfo("Επιτυχία", f"Φορτώθηκαν {self.dict_mgr.total_words} λέξεις επιτυχώς!")
        except Exception as e:
            messagebox.showerror("Σφάλμα", f"Αποτυχία ανάγνωσης αρχείου:\n{str(e)}")
            self.status_var.set("Κατάσταση: Σφάλμα φόρτωσης.")

    def generate_grid(self):
        size = self.size_var.get()
        ratio = self.ratio_var.get()
        if size < 4 or size > 25:
            messagebox.showerror("Σφάλμα", "Η διάσταση πρέπει να είναι μεταξύ 4 και 25.")
            return
        self.status_var.set("Κατάσταση: Παραγωγή τοπολογίας...")
        self.root.update()
        self.grid = CrosswordGrid(size, ratio)
        success = self.grid.generate_topology()
        if success:
            self.draw_grid()
            self.btn_solve.config(state=tk.NORMAL)
            self.status_var.set(f"Κατάσταση: Έτοιμο! Βρέθηκαν {len(self.grid.variables)} λέξεις.")
        else:
            messagebox.showwarning("Αποτυχία", "Δεν ήταν δυνατή η δημιουργία έγκυρου πλέγματος.\nΔοκιμάστε μικρότερο ποσοστό μαύρων κελιών (π.χ. 0.15).")
            self.status_var.set("Κατάσταση: Αποτυχία παραγωγής.")

    def draw_grid(self, assignment=None):
        self.canvas.delete("all")
        if not self.grid: return
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        cell_size = min(canvas_width, canvas_height) // self.grid.size
        offset_x = (canvas_width - (cell_size * self.grid.size)) // 2
        offset_y = (canvas_height - (cell_size * self.grid.size)) // 2
        
        letters = [["" for _ in range(self.grid.size)] for _ in range(self.grid.size)]
        if assignment:
            for vid, word in assignment.items():
                var = self.grid.variables[vid]
                for i, (r, c) in enumerate(var.cells):
                    letters[r][c] = word[i]

        for r in range(self.grid.size):
            for c in range(self.grid.size):
                x1 = offset_x + c * cell_size
                y1 = offset_y + r * cell_size
                x2 = x1 + cell_size
                y2 = y1 + cell_size
                if self.grid.grid[r][c] == 1:
                    self.canvas.create_rectangle(x1, y1, x2, y2, fill="black", outline="gray")
                else:
                    self.canvas.create_rectangle(x1, y1, x2, y2, fill="white", outline="black")
                    if assignment and letters[r][c]:
                        self.canvas.create_text(x1 + cell_size//2, y1 + cell_size//2, text=letters[r][c], font=("Helvetica", cell_size//2, "bold"))

    def start_solving(self):
        if self.dict_mgr.total_words < 1000:
            ans = messagebox.askyesno("Προσοχή", "Χρησιμοποιείτε το εικονικό λεξικό. Η επίλυση πιθανότατα θα αποτύχει. Συνέχεια;")
            if not ans: return
        self.btn_generate.config(state=tk.DISABLED)
        self.btn_solve.config(state=tk.DISABLED)
        self.btn_load.config(state=tk.DISABLED)
        self.status_var.set("Κατάσταση: Αναζήτηση λύσης (AI)...")
        self.solver = CSPSolver(self.grid, self.dict_mgr)
        thread = threading.Thread(target=self.solve_thread)
        thread.daemon = True
        thread.start()

    def solve_thread(self):
        start_time = time.time()
        solution = self.solver.solve()
        end_time = time.time()
        self.root.after(0, self.on_solve_complete, solution, end_time - start_time)

    def on_solve_complete(self, solution, duration):
        self.btn_generate.config(state=tk.NORMAL)
        self.btn_solve.config(state=tk.NORMAL)
        self.btn_load.config(state=tk.NORMAL)
        if solution:
            self.draw_grid(solution)
            self.status_var.set(f"Κατάσταση: Επιτυχία!\nΧρόνος: {duration:.2f}s\nΚόμβοι: {self.solver.nodes_visited}")
        else:
            self.status_var.set(f"Κατάσταση: Αποτυχία. (Χρόνος: {duration:.2f}s)")
            messagebox.showinfo("Αποτέλεσμα", "Δεν βρέθηκε λύση. Το λεξικό δεν περιέχει τις κατάλληλες λέξεις για αυτές τις διασταυρώσεις.")

if __name__ == "__main__":
    root = tk.Tk()
    app = CrosswordApp(root)
    root.update() 
    root.mainloop()
