import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import os
import cv2
import numpy as np
import csv
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ---------------- CONFIG OSCILOSCOPIO ----------------
GRID_X1, GRID_Y1 = 10, 20
GRID_X2, GRID_Y2 = 310, 220
DIV_PX = 25

V_DIV_VALUES = ["100mV", "200mV", "500mV", "1V", "2V", "5V"]
T_DIV_VALUES = ["5us", "10us", "20us", "50us", "100us", "200us", "500us", "1ms", "2ms", "5ms"]

# ----------------------------------------------------

def parse_vdiv(text):
    return float(text.replace("mV", "")) * 1e-3 if "mV" in text else float(text.replace("V", ""))

def parse_tdiv(text):
    if "us" in text:
        return float(text.replace("us", "")) * 1e-6
    if "ms" in text:
        return float(text.replace("ms", "")) * 1e-3
    return float(text.replace("s", ""))

# ----------------------------------------------------

class OscilloscopeApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Oscilloscope BMP Reader for fnirsi DPOX180H")
        self.geometry("1200x700")

        self.current_folder = None
        self.current_data = None
        self.current_bmp_path = None

        # -------- MENU --------
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        filemenu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=filemenu)
        filemenu.add_command(label="Seleccionar carpeta", command=self.select_folder)
        filemenu.add_separator()
        filemenu.add_command(label="Salir", command=self.quit)

        # -------- LAYOUT --------
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # -------- PANEL IZQUIERDO --------
        left = tk.Frame(self, width=200)
        left.grid(row=0, column=0, sticky="ns")

        self.file_list = tk.Listbox(left)
        self.file_list.pack(fill="both", expand=True, padx=10, pady=10)
        self.file_list.bind("<<ListboxSelect>>", self.on_select_bmp)

        # -------- PANEL DERECHO --------
        right = tk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(1, weight=1)

        # -------- CONTROLES --------
        controls = tk.Frame(right)
        controls.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        self.vdiv_var = tk.StringVar(value="500mV")
        self.tdiv_var = tk.StringVar(value="200us")

        tk.Label(controls, text="V/div").pack(side="left")
        tk.OptionMenu(controls, self.vdiv_var, *V_DIV_VALUES).pack(side="left", padx=5)

        tk.Label(controls, text="s/div").pack(side="left", padx=10)
        tk.OptionMenu(controls, self.tdiv_var, *T_DIV_VALUES).pack(side="left")

        tk.Button(controls, text="Generar CSV", command=self.export_csv)\
            .pack(side="left", padx=15)

        # -------- IMAGEN --------
        self.img_label = tk.Label(right)
        self.img_label.grid(row=1, column=0, padx=10, pady=10)

        # -------- GRAFICA --------
        self.fig, self.ax = plt.subplots(figsize=(5, 4))
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().grid(row=1, column=1, sticky="nsew")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    # ------------------------------------------------
    def select_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return

        self.current_folder = folder
        self.file_list.delete(0, tk.END)

        for f in os.listdir(folder):
            if f.lower().endswith(".bmp"):
                self.file_list.insert(tk.END, f)

    # ------------------------------------------------
    def on_select_bmp(self, event):
        if not self.current_folder:
            return

        sel = self.file_list.curselection()
        if not sel:
            return

        bmp = self.file_list.get(sel[0])
        self.process_image(os.path.join(self.current_folder, bmp))

    # ------------------------------------------------
    def process_image(self, path):
        self.current_bmp_path = path

        img = cv2.imread(path)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        lower_yellow = np.array([20, 80, 80])
        upper_yellow = np.array([40, 255, 255])
        mask = cv2.inRange(hsv, lower_yellow, upper_yellow)

        points = []
        for x in range(GRID_X1, GRID_X2):
            ys = np.where(mask[GRID_Y1:GRID_Y2, x] > 0)[0]
            if len(ys):
                points.append((x, GRID_Y1 + int(np.mean(ys))))

        ARROW_X = 8
        ARROW_Y1 = 20
        ARROW_Y2 = 220

        col = mask[ARROW_Y1:ARROW_Y2, ARROW_X]
        ys = np.where(col > 0)[0]

        if len(ys) == 0:
            raise RuntimeError("No se detectó la flecha de 0V")

        # referencia d 0v
        y0 = ARROW_Y1 + int(np.mean(ys))

        print("0V detectado en Y =", y0)

        V_PER_DIV = parse_vdiv(self.vdiv_var.get())
        T_PER_DIV = parse_tdiv(self.tdiv_var.get())

        x0 = points[0][0]
        self.current_data = [
            (((x - x0) / DIV_PX) * T_PER_DIV,
             ((y0 - y) / DIV_PX) * V_PER_DIV)
            for x, y in points
        ]

        # imagen
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb).resize((360, 260))
        self.tk_img = ImageTk.PhotoImage(img_pil)
        self.img_label.config(image=self.tk_img)

        # grafica
        self.ax.clear()
        self.ax.plot(
            [t for t, _ in self.current_data],
            [v for _, v in self.current_data]
        )
        self.ax.set_xlabel("Tiempo (s)")
        self.ax.set_ylabel("Voltaje (V)")
        self.ax.grid(True)
        self.canvas.draw()

    # ------------------------------------------------
    def export_csv(self):
        if not self.current_data or not self.current_bmp_path:
            messagebox.showwarning("Aviso", "No hay señal cargada")
            return

        csv_path = os.path.join(
            self.current_folder,
            os.path.splitext(os.path.basename(self.current_bmp_path))[0] + ".csv"
        )

        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Tiempo (s)", "Voltaje (V)"])
            writer.writerows(self.current_data)

        messagebox.showinfo("OK", f"CSV generado:\n{csv_path}")
    def on_close(self):
        try:
            plt.close("all")
        except:
            pass
        self.destroy()
        self.quit()
# ----------------------------------------------------
if __name__ == "__main__":
    OscilloscopeApp().mainloop()
