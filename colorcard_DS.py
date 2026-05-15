import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageDraw, ImageTk
import math
import random
import pyautogui
from ttkthemes import ThemedTk

# 常量定义
CANVAS_SIZE = 512
COLOR_PICKER_SIZE = 200
BRIGHTNESS_GRADIENT_HEIGHT = 20
MAX_HISTORY_SIZE = 10

# HSL 到 RGB 转换
def hsl_to_rgb(h, s, l):
    if s == 0:
        r = g = b = l
    else:
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        h *= 6
        i = int(h)
        f = h - i
        if i == 0:
            r, g, b = q, p + (q - p) * f, p
        elif i == 1:
            r, g, b = p + (q - p) * (1 - f), q, p
        elif i == 2:
            r, g, b = p, q, p + (q - p) * f
        elif i == 3:
            r, g, b = p, p + (q - p) * (1 - f), q
        elif i == 4:
            r, g, b = p + (q - p) * f, p, q
        elif i == 5:
            r, g, b = q, p, p + (q - p) * f
    return (int(r * 255), int(g * 255), int(b * 255))

# RGB 到 HSL 转换
def rgb_to_hsl(r, g, b):
    r, g, b = r / 255, g / 255, b / 255
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    l = (max_val + min_val) / 2
    if max_val == min_val:
        h = s = 0
    else:
        d = max_val - min_val
        s = d / (2 - max_val - min_val) if l > 0.5 else d / (max_val + min_val)
        if max_val == r:
            h = (g - b) / d + (6 if g < b else 0)
        elif max_val == g:
            h = (b - r) / d + 2
        else:
            h = (r - g) / d + 4
        h /= 6
    return (h, s, l)

# 计算颜色的灰度值
def calculate_grayscale(color):
    r, g, b = color
    return 0.299 * r + 0.587 * g + 0.114 * b

# 主应用程序类
class ColorCardEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("色卡编辑器")
        self.current_color = None
        self.current_color_hsl = (0.0, 0.0, 0.5)
        self.color_history = []
        self.card_image = Image.new('RGB', (CANVAS_SIZE, CANVAS_SIZE), color='white')
        self.card_photo = ImageTk.PhotoImage(self.card_image)
        self.photo = None

        # 初始化界面
        self.init_ui()

    def init_ui(self):
        # 主框架
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 色卡尺寸选择
        self.size_var = tk.IntVar(value=8)
        self.sizes = [2**i for i in range(1, 10)]
        self.size_label = ttk.Label(self.main_frame, text="选择色卡尺寸:")
        self.size_label.pack()
        self.size_menu = ttk.OptionMenu(self.main_frame, self.size_var, 8, *self.sizes, command=self.update_size)
        self.size_menu.pack()

        # 色卡画布
        self.card_frame = ttk.Frame(self.main_frame)
        self.card_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(self.card_frame, width=CANVAS_SIZE, height=CANVAS_SIZE)
        self.canvas.pack()
        self.canvas.create_image(0, 0, image=self.card_photo, anchor=tk.NW)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Button-3>", self.fill_cell_with_random_hue)

        # 控制面板
        self.control_frame = ttk.Frame(self.main_frame)
        self.control_frame.pack(side=tk.RIGHT, fill=tk.Y)

        # 颜色选择器
        self.init_color_picker()
        # 亮度梯度
        self.init_brightness_gradient()
        # 历史记录
        self.init_history()
        # 配色方案
        self.init_color_scheme()
        # 工具按钮
        self.init_tools()

        # 初始化颜色选择器
        self.update_color_picker()

    def init_color_picker(self):
        self.color_picker_frame = ttk.LabelFrame(self.control_frame, text="颜色选择器")
        self.color_picker_frame.pack(pady=10)
        self.color_picker_canvas = tk.Canvas(self.color_picker_frame, width=COLOR_PICKER_SIZE, height=COLOR_PICKER_SIZE)
        self.color_picker_canvas.pack()
        self.dot = self.color_picker_canvas.create_oval(0, 0, 0, 0, outline="white", width=2, state="hidden")
        self.color_picker_canvas.bind("<Button-1>", self.choose_color)

        self.brightness_var = tk.DoubleVar(value=0.5)
        self.brightness_scale = ttk.Scale(self.color_picker_frame, from_=0, to=1, variable=self.brightness_var, orient=tk.VERTICAL, length=200, command=self.update_color_picker)
        self.brightness_scale.pack()
        self.brightness_label = ttk.Label(self.color_picker_frame, text="亮度")
        self.brightness_label.pack()

    def init_brightness_gradient(self):
        self.brightness_gradient_frame = ttk.Frame(self.control_frame)
        self.brightness_gradient_frame.pack(pady=10)
        self.brightness_gradient_canvas = tk.Canvas(self.brightness_gradient_frame, width=COLOR_PICKER_SIZE, height=BRIGHTNESS_GRADIENT_HEIGHT)
        self.brightness_gradient_canvas.pack()
        self.brightness_gradient_canvas.bind("<Button-1>", self.choose_brightness_color)

    def init_history(self):
        self.history_frame = ttk.LabelFrame(self.control_frame, text="色彩历史")
        self.history_frame.pack(pady=10)
        self.history_list = tk.Listbox(self.history_frame, width=15, height=10)
        self.history_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.history_list.bind("<Button-1>", self.on_history_click)
        self.clear_button = ttk.Button(self.history_frame, text="清除", command=lambda: self.history_list.delete(0, tk.END))
        self.clear_button.pack(side=tk.RIGHT)

    def init_color_scheme(self):
        self.color_scheme_frame = ttk.LabelFrame(self.control_frame, text="配色方案")
        self.color_scheme_frame.pack(pady=10)
        self.undo_button = ttk.Button(self.color_scheme_frame, text="回撤", command=self.undo_color)
        self.undo_button.pack(pady=5)
        self.color_scheme_canvas = tk.Canvas(self.color_scheme_frame, width=COLOR_PICKER_SIZE, height=60)
        self.color_scheme_canvas.pack()
        self.color_scheme_canvas.bind("<Button-1>", self.on_color_scheme_click)
        self.color_scheme_label = ttk.Label(self.color_scheme_frame, text="", font=("Arial", 10))
        self.color_scheme_label.pack()

    def init_tools(self):
        self.eyedropper_button = ttk.Button(self.control_frame, text="吸管工具", command=self.activate_eyedropper)
        self.eyedropper_button.pack()
        self.global_hue_fill_button = ttk.Button(self.control_frame, text="全局色调填充", command=self.fill_card_with_random_hues)
        self.global_hue_fill_button.pack()
        self.sort_button = ttk.Button(self.control_frame, text="按色阶排序", command=self.sort_colors_by_grayscale)
        self.sort_button.pack()
        self.save_button = ttk.Button(self.control_frame, text="导出色卡", command=self.save_image)
        self.save_button.pack()
        self.import_button = ttk.Button(self.control_frame, text="导入图片", command=self.import_image)
        self.import_button.pack()

    def update_size(self, *args):
        size = self.size_var.get()
        cell_size = CANVAS_SIZE // size
        self.card_image = Image.new('RGB', (CANVAS_SIZE, CANVAS_SIZE), color='white')
        self.card_photo = ImageTk.PhotoImage(self.card_image)
        self.canvas.create_image(0, 0, image=self.card_photo, anchor=tk.NW)

    def on_canvas_click(self, event):
        cell_size = CANVAS_SIZE // self.size_var.get()
        x = event.x // cell_size
        y = event.y // cell_size
        if self.current_color:
            self.draw_cell(x, y, self.current_color)

    def draw_cell(self, x, y, color):
        cell_size = CANVAS_SIZE // self.size_var.get()
        draw = ImageDraw.Draw(self.card_image)
        draw.rectangle([x*cell_size, y*cell_size, (x+1)*cell_size, (y+1)*cell_size], fill=color)
        self.card_photo = ImageTk.PhotoImage(self.card_image)
        self.canvas.create_image(0, 0, image=self.card_photo, anchor=tk.NW)

    def fill_cell_with_random_hue(self, event):
        cell_size = CANVAS_SIZE // self.size_var.get()
        x = event.x // cell_size
        y = event.y // cell_size
        hue = random.random()
        saturation = 1.0
        lightness = self.brightness_var.get()
        color = hsl_to_rgb(hue, saturation, lightness)
        self.draw_cell(x, y, color)
        self.add_to_history(color)
        self.history_list.insert(tk.END, f"随机填充: #{color[0]:02x}{color[1]:02x}{color[2]:02x}")
        self.history_list.yview(tk.END)

    def fill_card_with_random_hues(self):
        size = self.size_var.get()
        lightness = self.brightness_var.get()
        saturation = 1.0
        for i in range(size):
            for j in range(size):
                hue = random.random()
                color = hsl_to_rgb(hue, saturation, lightness)
                self.draw_cell(i, j, color)
        self.history_list.insert(tk.END, f"全局色调填充 ({size}x{size})")
        self.history_list.yview(tk.END)

    def update_color_picker(self, *args):
        image = Image.new('RGB', (COLOR_PICKER_SIZE, COLOR_PICKER_SIZE))
        center = (COLOR_PICKER_SIZE // 2, COLOR_PICKER_SIZE // 2)
        max_radius = COLOR_PICKER_SIZE // 2
        lightness = self.brightness_var.get()
        draw = ImageDraw.Draw(image)
        for y in range(COLOR_PICKER_SIZE):
            for x in range(COLOR_PICKER_SIZE):
                dx = x - center[0]
                dy = y - center[1]
                distance = (dx**2 + dy**2)**0.5
                if distance > max_radius:
                    color = (255, 255, 255)  # 超出色环范围填充白色
                else:
                    saturation = distance / max_radius
                    angle = math.degrees(math.atan2(dy, dx))
                    if angle < 0:
                        angle += 360
                    hue = angle / 360.0
                    color = hsl_to_rgb(hue, saturation, lightness)
                image.putpixel((x, y), color)
        self.photo = ImageTk.PhotoImage(image)
        self.color_picker_canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

    def choose_color(self, event):
        x = event.x
        y = event.y
        dx = x - COLOR_PICKER_SIZE // 2
        dy = y - COLOR_PICKER_SIZE // 2
        distance = (dx**2 + dy**2)**0.5
        if distance > COLOR_PICKER_SIZE // 2:
            return
        saturation = distance / (COLOR_PICKER_SIZE // 2)
        angle = math.degrees(math.atan2(dy, dx))
        if angle < 0:
            angle += 360
        hue = angle / 360.0
        lightness = self.brightness_var.get()
        self.current_color_hsl = (hue, saturation, lightness)
        self.current_color = hsl_to_rgb(hue, saturation, lightness)
        self.add_to_history(self.current_color)
        self.history_list.insert(tk.END, f"#{self.current_color[0]:02x}{self.current_color[1]:02x}{self.current_color[2]:02x}")
        self.history_list.yview(tk.END)
        self.generate_brightness_gradient()
        self.update_color_scheme()
        self.color_picker_canvas.coords(self.dot, x - 5, y - 5, x + 5, y + 5)
        self.color_picker_canvas.itemconfig(self.dot, state="normal")
        self.color_picker_canvas.tag_raise(self.dot)

    def generate_brightness_gradient(self):
        if self.current_color_hsl is None:
            return
        hue, saturation, _ = self.current_color_hsl
        for i in range(COLOR_PICKER_SIZE):
            lightness = i / COLOR_PICKER_SIZE
            color = hsl_to_rgb(hue, saturation, lightness)
            self.brightness_gradient_canvas.create_rectangle(i, 0, i + 1, BRIGHTNESS_GRADIENT_HEIGHT, fill=f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}", outline="")
        self.brightness_gradient_canvas.bind("<Button-1>", self.choose_brightness_color)

    def choose_brightness_color(self, event):
        x = event.x
        lightness = x / COLOR_PICKER_SIZE
        hue, saturation, _ = self.current_color_hsl
        self.current_color_hsl = (hue, saturation, lightness)
        self.current_color = hsl_to_rgb(hue, saturation, lightness)
        self.add_to_history(self.current_color)
        self.history_list.insert(tk.END, f"#{self.current_color[0]:02x}{self.current_color[1]:02x}{self.current_color[2]:02x}")
        self.history_list.yview(tk.END)
        self.update_color_scheme()

    def add_to_history(self, color):
        if len(self.color_history) >= MAX_HISTORY_SIZE:
            self.color_history.pop(0)
        self.color_history.append(color)

    def undo_color(self):
        if len(self.color_history) > 1:
            self.color_history.pop()
            previous_color = self.color_history[-1]
            self.set_current_color(previous_color)

    def set_current_color(self, color):
        self.current_color = color
        self.current_color_hsl = rgb_to_hsl(*color)
        self.brightness_var.set(self.current_color_hsl[2])
        self.add_to_history(color)
        self.history_list.insert(tk.END, f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}")
        self.history_list.yview(tk.END)
        self.generate_brightness_gradient()
        self.update_color_scheme()

    def update_color_scheme(self):
        if self.current_color_hsl is None:
            return
        self.color_scheme_canvas.delete("all")
        hue, saturation, lightness = self.current_color_hsl
        complementary_color = hsl_to_rgb((hue + 0.5) % 1.0, saturation, lightness)
        analogous_color = hsl_to_rgb((hue - 30 / 360) % 1.0, saturation, lightness)
        triadic_color = hsl_to_rgb((hue + 120 / 360) % 1.0, saturation, lightness)
        colors = [complementary_color, analogous_color, triadic_color]
        color_width = COLOR_PICKER_SIZE // len(colors)
        for i, color in enumerate(colors):
            x1 = i * color_width
            x2 = (i + 1) * color_width
            self.color_scheme_canvas.create_rectangle(x1, 0, x2, 50, fill=f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}", outline="")
            self.color_scheme_canvas.create_text((x1 + x2) // 2, 25, text=f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}", fill="white" if lightness < 0.5 else "black")
        self.color_scheme_label.config(text="互补色 | 相似色 | 三色配色")

    def on_color_scheme_click(self, event):
        x = event.x
        color_width = COLOR_PICKER_SIZE // 3
        index = x // color_width
        if index >= 3:
            return
        hue, saturation, lightness = self.current_color_hsl
        if index == 0:
            new_hue = (hue + 0.5) % 1.0
        elif index == 1:
            new_hue = (hue - 30 / 360) % 1.0
        else:
            new_hue = (hue + 120 / 360) % 1.0
        new_color = hsl_to_rgb(new_hue, saturation, lightness)
        self.set_current_color(new_color)

    def on_history_click(self, event):
        selected_item = self.history_list.get(tk.ACTIVE)
        if selected_item:
            color_value = selected_item.split("#")[-1]
            self.root.clipboard_clear()
            self.root.clipboard_append(color_value)
            print(f"已复制: #{color_value}")

    def activate_eyedropper(self):
        self.root.withdraw()
        overlay = tk.Toplevel()
        overlay.attributes("-fullscreen", True)
        overlay.attributes("-alpha", 0.3)
        overlay.attributes("-topmost", True)
        crosshair_canvas = tk.Canvas(overlay, width=overlay.winfo_screenwidth(), height=overlay.winfo_screenheight(), highlightthickness=0)
        crosshair_canvas.pack()
        crosshair_vertical = crosshair_canvas.create_line(0, 0, 0, overlay.winfo_screenheight(), fill="red", tags="crosshair")
        crosshair_horizontal = crosshair_canvas.create_line(0, 0, overlay.winfo_screenwidth(), 0, fill="red", tags="crosshair")

        def update_crosshair():
            x, y = pyautogui.position()
            crosshair_canvas.coords(crosshair_vertical, x, 0, x, overlay.winfo_screenheight())
            crosshair_canvas.coords(crosshair_horizontal, 0, y, overlay.winfo_screenwidth(), y)
            overlay.after(50, update_crosshair)

        def on_mouse_click(event):
            crosshair_canvas.itemconfig(crosshair_vertical, state="hidden")
            crosshair_canvas.itemconfig(crosshair_horizontal, state="hidden")
            overlay.update()
            x, y = pyautogui.position()
            screenshot = pyautogui.screenshot()
            color = screenshot.getpixel((x, y))
            crosshair_canvas.itemconfig(crosshair_vertical, state="normal")
            crosshair_canvas.itemconfig(crosshair_horizontal, state="normal")
            overlay.update()
            self.current_color = color
            self.current_color_hsl = rgb_to_hsl(*color)
            self.add_to_history(self.current_color)
            self.history_list.insert(tk.END, f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}")
            self.history_list.yview(tk.END)
            overlay.destroy()
            self.root.deiconify()

        overlay.bind("<Button-1>", on_mouse_click)
        update_crosshair()

    def save_image(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png"), ("All files", "*.*")])
        if file_path:
            self.card_image.save(file_path)

    def sort_colors_by_grayscale(self):
        size = self.size_var.get()
        cell_size = CANVAS_SIZE // size
        colors = []

        # 提取色卡中的所有颜色
        for i in range(size):
            for j in range(size):
                x = i * cell_size + cell_size // 2
                y = j * cell_size + cell_size // 2
                color = self.card_image.getpixel((x, y))
                colors.append(color)  # 只保存颜色

        # 将颜色按色相（Hue）分组
        color_groups = {}
        for color in colors:
            h, s, l = rgb_to_hsl(*color)
            hue_group = int(h * 12)  # 将色相分为12组（可以根据需要调整）
            if hue_group not in color_groups:
                color_groups[hue_group] = []
            color_groups[hue_group].append((color, l))  # 保存颜色和亮度

        # 对每组颜色按亮度（Lightness）排序
        sorted_colors = []
        for group in sorted(color_groups.keys()):
            group_colors = color_groups[group]
            group_colors.sort(key=lambda x: x[1])  # 按亮度排序
            sorted_colors.extend([color[0] for color in group_colors])  # 只保存颜色

        # 将排序后的颜色填充到色卡中
        index = 0
        for i in range(size):
            for j in range(size):
                if index < len(sorted_colors):
                    self.draw_cell(j, i, sorted_colors[index])  # 按列填充，实现从左到右
                    index += 1

    def import_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg;*.jpeg;*.png;*.bmp")])
        if file_path:
            try:
                image = Image.open(file_path)
                image = image.resize((CANVAS_SIZE, CANVAS_SIZE))  # 缩放图片到色卡尺寸
                size = self.size_var.get()
                cell_size = CANVAS_SIZE // size
                for i in range(size):
                    for j in range(size):
                        x = i * cell_size
                        y = j * cell_size
                        color = image.getpixel((x + cell_size // 2, y + cell_size // 2))  # 取单元格中心颜色
                        self.draw_cell(i, j, color)
                self.history_list.insert(tk.END, f"导入图片: {file_path}")
                self.history_list.yview(tk.END)
            except Exception as e:
                print(f"导入图片失败: {e}")

# 主程序入口
if __name__ == "__main__":
    root = ThemedTk(theme="arc")
    app = ColorCardEditor(root)
    root.mainloop()