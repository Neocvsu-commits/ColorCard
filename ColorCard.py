import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageDraw, ImageTk, ImageGrab, ImageFont
import math
import random
import colorsys
import ctypes 

# --- 全局视觉配置 ---
BG_COLOR = "#FFFFFF"       
PANEL_BG = "#F8F8F8"       
TEXT_COLOR = "#333333"     
SUB_TEXT_COLOR = "#666666" 
HIGHLIGHT_COLOR = "#2196F3" 

WHEEL_SIZE = 240
CANVAS_SIZE = 512
TOAST_DURATION = 1800     # ms
UNDO_MAX = 50             # image snapshots are memory-heavy

# --- 集中式排版引擎 (Centralized Typography Engine) ---
FONTS = {
    "h1": ("Microsoft YaHei", 12, "bold"),      # 顶层应用名称
    "h2": ("Microsoft YaHei", 10, "bold"),      # 模块标题 (字号近似正文，仅靠加粗区分)
    "body": ("Microsoft YaHei", 9),             # 桌面级基准正文与交互控件
    "data": ("Consolas", 9),                    # 极客数据表达 (无加粗等宽)
    "data_small": ("Consolas", 8)               # 辅助极客数据 (如坐标)
}

class UIStyles:
    @staticmethod
    def apply(root):
        style = ttk.Style()
        style.theme_use('clam')
        # 全局控件接入集中式字体引擎的 body 基准
        style.configure(".", background=BG_COLOR, foreground=TEXT_COLOR, font=FONTS["body"])
        style.configure("TFrame", background=BG_COLOR)
        
        style.configure("Accent.TButton", background=HIGHLIGHT_COLOR, foreground="white", borderwidth=0, padding=6)
        style.map("Accent.TButton", background=[('active', '#1976D2')])
        
        style.configure("Tool.TButton", background="#EEEEEE", foreground=TEXT_COLOR, borderwidth=0, padding=5)
        style.map("Tool.TButton", background=[('active', '#DDDDDD')])
        
        style.map("TCombobox", fieldbackground=[("readonly", "#FFFFFF")], selectbackground=[("readonly", "#FFFFFF")], selectforeground=[("readonly", TEXT_COLOR)])
        style.configure("Horizontal.TScale", background=BG_COLOR, troughcolor="#E0E0E0", borderwidth=0)

class ColorHarmony:
    @staticmethod
    def hsl_to_rgb(h, s, l):
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return int(r * 255), int(g * 255), int(b * 255)

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

class MONITORINFOEX(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", ctypes.c_ulong), ("szDevice", ctypes.c_char * 32)]

class GridCanvasEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Color Grid - 像素级色卡提取与生成工具")
        self.root.configure(bg=BG_COLOR)
        
        UIStyles.apply(self.root)
        
        try:
            self.root.tk.call('tk', 'scaling', self.root.winfo_fpixels('1i')/72.0)
        except: pass

        self.current_hsl = (0.0, 1.0, 0.5) 
        self.brush_mode = tk.StringVar(value="random_hue") 
        self.grid_size_var = tk.IntVar(value=8) 
        self.is_rgb_mode = False 
        
        self.image = Image.new('RGB', (CANVAS_SIZE, CANVAS_SIZE), color='white')
        self.tk_image = None
        self.canvas_image_id = None
        self.wheel_img = None
        self.has_content = False
        self._canvas_grid_size = self.grid_size_var.get()
        self._stroke_active = False
        self._last_draw_cell = None
        self._toast_after_id = None
        
        self.picking_active = False
        self.loupe_win = None
        self.overlays = []
        self.monitors = []
        self.is_topmost = False

        # --- Undo / Redo ---
        self.undo_stack = []       # list of (Image copy, grid size, has content)
        self.redo_stack = []

        self.last_monitor_idx = -1
        self.v_min_x = 0
        self.v_min_y = 0
        self.cached_screen = None
        self.use_all_screens = True
        
        self.wheel_pixels = []
        self.wheel_mask = None
        self.wheel_shadow = None
        self.build_wheel_caches()
        
        self.setup_ui()
        self.update_ui_from_hsl() 
        self.init_empty_grid() 
        
        # 等宽边距美学与反推布局
        self.root.update_idletasks()
        
        left_h = self.left_panel.winfo_reqheight()
        win_h = left_h + 30 
        top_bar_h = self.top_bar.winfo_reqheight()
        outer_pad_h = win_h - top_bar_h - 2
        
        border_frame_h = outer_pad_h - 40
        border_frame_w = border_frame_h 
        outer_pad_w = border_frame_w + 40
        
        left_w = self.left_panel.winfo_reqwidth()
        left_structure_w = 25 + left_w + 25 
        win_w = left_structure_w + outer_pad_w + 2
        
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        
        if win_h > screen_h - 80:
            win_h = screen_h - 80
            outer_pad_h = win_h - top_bar_h - 2
            border_frame_h = outer_pad_h - 40
            border_frame_w = border_frame_h 
            outer_pad_w = border_frame_w + 40
            win_w = left_structure_w + outer_pad_w + 2
            
        x = max(0, (screen_w - win_w) // 2)
        y = max(0, (screen_h - win_h) // 2)
        
        self.root.geometry(f"{int(win_w)}x{int(win_h)}+{int(x)}+{int(y)}")
        min_w = min(int(win_w), max(640, screen_w - 40))
        min_h = min(int(win_h), max(560, screen_h - 80))
        self.root.minsize(min_w, min_h)

    def build_wheel_caches(self):
        render_size = WHEEL_SIZE
        cx, cy = render_size // 2, render_size // 2
        radius = render_size // 2 - 4
        inner_r = radius * 0.5 
        
        for x in range(render_size):
            for y in range(render_size):
                dx, dy = x - cx, y - cy
                dist = math.sqrt(dx*dx + dy*dy)
                if inner_r <= dist <= radius:
                    angle = math.atan2(dy, dx)
                    hue = (angle / (2 * math.pi)) % 1.0
                    self.wheel_pixels.append((x, y, hue))

        self.wheel_mask = Image.new('RGBA', (render_size, render_size), (0,0,0,0))
        mask_draw = ImageDraw.Draw(self.wheel_mask)
        line_color = (200, 200, 200, 100) 
        for x, y, hue in self.wheel_pixels:
            deg = hue * 360
            dx, dy = x - cx, y - cy
            dist = math.sqrt(dx*dx + dy*dy)
            norm_dist = dist / radius
            if (deg % 15) < 1.0: mask_draw.point((x, y), fill=line_color)
            if 0.64 < norm_dist < 0.65 or 0.79 < norm_dist < 0.8: mask_draw.point((x, y), fill=line_color)

        self.wheel_shadow = Image.new('RGBA', (render_size, render_size), (0,0,0,0))
        shadow_draw = ImageDraw.Draw(self.wheel_shadow)
        for x, y, _ in self.wheel_pixels:
            dx, dy = x - cx, y - cy
            dist = math.sqrt(dx*dx + dy*dy)
            if dist < inner_r + 5:
                alpha = int(150 * (1 - (dist - inner_r) / 5))
                shadow_draw.point((x, y), fill=(0, 0, 0, alpha))
            elif dist > radius - 5:
                alpha = int(150 * (1 - (radius - dist) / 5))
                shadow_draw.point((x, y), fill=(0, 0, 0, alpha))

    def setup_ui(self):
        main_container = tk.Frame(self.root, bg=BG_COLOR)
        main_container.pack(fill=tk.BOTH, expand=True, padx=25, pady=(5, 25), anchor="nw")

        left_panel = tk.Frame(main_container, bg=BG_COLOR, width=320)
        self.left_panel = left_panel 
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 25))

        tk.Label(left_panel, text="Color Grid", font=FONTS["h1"], bg=BG_COLOR, fg=TEXT_COLOR).pack(anchor="w", pady=(0, 10))

        slider_frame = tk.Frame(left_panel, bg=BG_COLOR)
        slider_frame.pack(fill=tk.X, pady=(0, 8))

        tk.Label(slider_frame, text="饱和度", bg=BG_COLOR, fg=SUB_TEXT_COLOR, font=FONTS["body"]).pack(anchor="w")
        self.sat_scale = ttk.Scale(slider_frame, from_=0.0, to=1.0, orient=tk.HORIZONTAL)
        self.sat_scale.pack(fill=tk.X, pady=(0, 5))
        self.sat_scale.set(1.0)
        
        tk.Label(slider_frame, text="亮度", bg=BG_COLOR, fg=SUB_TEXT_COLOR, font=FONTS["body"]).pack(anchor="w")
        self.light_scale = ttk.Scale(slider_frame, from_=0.0, to=1.0, orient=tk.HORIZONTAL)
        self.light_scale.pack(fill=tk.X, pady=(0, 0))
        self.light_scale.set(0.5)

        wheel_container = tk.Frame(left_panel, bg=BG_COLOR)
        wheel_container.pack(pady=5, anchor="center")
        self.wheel_canvas = tk.Canvas(wheel_container, width=WHEEL_SIZE, height=WHEEL_SIZE, bg=BG_COLOR, highlightthickness=0)
        self.wheel_canvas.pack()
        self.wheel_canvas.bind("<B1-Motion>", self.on_wheel_interact)
        self.wheel_canvas.bind("<Button-1>", self.on_wheel_interact)

        # 核心数据剥离加粗，使用等宽英文，体现极客质感
        self.info_label = tk.Label(left_panel, text="基色: #FF0000", bg=PANEL_BG, fg=TEXT_COLOR, font=FONTS["data"], pady=6, cursor="hand2")
        self.info_label.pack(fill=tk.X, pady=(5, 8))
        self.info_label.bind("<Button-1>", self.copy_base_color)

        self.sat_scale.config(command=self.on_slider_change)
        self.light_scale.config(command=self.on_slider_change)

        settings_frame = tk.Frame(left_panel, bg=BG_COLOR)
        settings_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(settings_frame, text="笔刷与网格", bg=BG_COLOR, fg=SUB_TEXT_COLOR, font=FONTS["h2"]).pack(anchor="w", pady=(0, 2))
        ttk.Radiobutton(settings_frame, text="纯色绘制", variable=self.brush_mode, value="solid").pack(anchor="w", pady=1)
        ttk.Radiobutton(settings_frame, text="随机色相", variable=self.brush_mode, value="random_hue").pack(anchor="w", pady=1)
        
        size_frame = tk.Frame(settings_frame, bg=BG_COLOR)
        size_frame.pack(fill=tk.X, pady=(8, 0))
        tk.Label(size_frame, text="网格尺寸:", bg=BG_COLOR, font=FONTS["body"]).pack(side=tk.LEFT)
        size_cb = ttk.Combobox(size_frame, textvariable=self.grid_size_var, values=[2, 4, 8, 16, 32, 64], state="readonly", width=8)
        size_cb.pack(side=tk.RIGHT)
        size_cb.bind("<<ComboboxSelected>>", self.on_grid_size_change)

        btn_frame = tk.Frame(left_panel, bg=BG_COLOR)
        btn_frame.pack(fill=tk.X, pady=(15, 0)) 
        
        ttk.Button(btn_frame, text="全屏填充", style="Tool.TButton", command=self.action_fill_all).pack(fill=tk.X, pady=3)
        ttk.Button(btn_frame, text="打乱颜色", style="Tool.TButton", command=self.action_randomize).pack(fill=tk.X, pady=3)
        ttk.Button(btn_frame, text="按色阶排序", style="Tool.TButton", command=self.action_sort).pack(fill=tk.X, pady=3)
        ttk.Button(btn_frame, text="从图片导入", style="Tool.TButton", command=self.import_images).pack(fill=tk.X, pady=3)
        ttk.Button(btn_frame, text="导出 PNG", style="Accent.TButton", command=self.save_image).pack(fill=tk.X, pady=3)

        # --- 弹性右侧面板 ---
        right_panel = tk.Frame(main_container, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        right_panel.configure(highlightbackground="#E0E0E0", highlightcolor="#E0E0E0", highlightthickness=1)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        top_bar = tk.Frame(right_panel, bg=BG_COLOR, height=45)
        self.top_bar = top_bar 
        top_bar.pack(fill=tk.X)
        tk.Label(top_bar, text="色卡预览", bg=BG_COLOR, fg=TEXT_COLOR, font=FONTS["h2"]).pack(side=tk.LEFT, padx=15, pady=10)
        
        tools_frame = tk.Frame(top_bar, bg=BG_COLOR)
        tools_frame.pack(side=tk.RIGHT, pady=8, padx=15)

        self.rgb_btn = tk.Button(tools_frame, text="⇆ HEX/RGB", font=FONTS["body"], 
                                 bg=BG_COLOR, fg=SUB_TEXT_COLOR, bd=0, activebackground=BG_COLOR, 
                                 cursor="hand2", command=self.toggle_rgb_mode)
        self.rgb_btn.pack(side=tk.LEFT, padx=(0, 15))

        self.pick_btn = tk.Button(tools_frame, text="✀ 屏幕取色", font=FONTS["body"], 
                                  bg=BG_COLOR, fg=HIGHLIGHT_COLOR, bd=0, activebackground=BG_COLOR, 
                                  cursor="hand2", command=self.start_screen_pick)
        self.pick_btn.pack(side=tk.LEFT, padx=(0, 15))

        self.top_btn = tk.Button(tools_frame, text="📌 置顶窗口", font=FONTS["body"], 
                                 bg=BG_COLOR, fg=SUB_TEXT_COLOR, bd=0, activebackground=BG_COLOR, 
                                 cursor="hand2", command=self.toggle_topmost)
        self.top_btn.pack(side=tk.LEFT)

        outer_pad = tk.Frame(right_panel, bg=PANEL_BG, padx=20, pady=20)
        outer_pad.pack(fill=tk.BOTH, expand=True)
        
        border_frame = tk.Frame(outer_pad, bg=BG_COLOR, highlightbackground="#DDDDDD", highlightthickness=1)
        border_frame.pack(fill=tk.BOTH, expand=True)
        
        inner_pad = tk.Frame(border_frame, bg=BG_COLOR, padx=10, pady=10)
        inner_pad.pack(fill=tk.BOTH, expand=True)

        center_helper = tk.Frame(inner_pad, bg=BG_COLOR)
        center_helper.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        self.canvas = tk.Canvas(center_helper, width=CANVAS_SIZE, height=CANVAS_SIZE, bg="white", highlightthickness=0)
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Motion>", self.on_canvas_hover)
        self.canvas.bind("<Leave>", self.on_canvas_leave)

        self.toast_label = tk.Label(self.root, text="", bg="#333333", fg="#FFFFFF", padx=12, pady=6, font=FONTS["body"])

        # --- Keyboard shortcuts ---
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<Control-s>", lambda e: self.save_image())
        self.root.bind("<Control-o>", lambda e: self.import_images())

    def _current_state(self):
        return (
            self.image.copy(),
            self._canvas_grid_size,
            self.has_content,
        )

    def _push_undo(self):
        """Record one complete user operation for undo."""
        self.undo_stack.append(self._current_state())
        if len(self.undo_stack) > UNDO_MAX:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def _restore_state(self, state):
        image, grid_size, has_content = state
        self.image = image.copy()
        self._canvas_grid_size = grid_size
        self.grid_size_var.set(grid_size)
        self.has_content = has_content
        self.update_canvas_display()

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append(self._current_state())
        self._restore_state(self.undo_stack.pop())
        self.show_toast(f"撤销 (剩余 {len(self.undo_stack)} 步)")

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append(self._current_state())
        self._restore_state(self.redo_stack.pop())
        self.show_toast(f"重做 (剩余 {len(self.redo_stack)} 步)")

    def toggle_rgb_mode(self):
        self.is_rgb_mode = not self.is_rgb_mode
        if self.is_rgb_mode:
            self.rgb_btn.config(fg=HIGHLIGHT_COLOR)
        else:
            self.rgb_btn.config(fg=SUB_TEXT_COLOR)
        self.update_ui_from_hsl(update_wheel=False)
        self.show_toast("已切换为 " + ("RGB" if self.is_rgb_mode else "HEX") + " 格式")

    def copy_base_color(self, event):
        h, s, l = self.current_hsl
        rgb = ColorHarmony.hsl_to_rgb(h, s, l)
        if self.is_rgb_mode:
            copy_text = f"{rgb[0]}, {rgb[1]}, {rgb[2]}"
        else:
            copy_text = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
        self.root.clipboard_clear()
        self.root.clipboard_append(copy_text)
        self.root.update()
        self.show_toast(f"已复制色值: {copy_text}")

    def init_empty_grid(self):
        self.image = Image.new('RGB', (CANVAS_SIZE, CANVAS_SIZE), color='white')
        draw = ImageDraw.Draw(self.image)
        size = self.grid_size_var.get()
        step = CANVAS_SIZE / size
        
        for i in range(1, size):
            pos = int(i * step)
            draw.line([(pos, 0), (pos, CANVAS_SIZE)], fill="#E6E6E6", width=1)
            draw.line([(0, pos), (CANVAS_SIZE, pos)], fill="#E6E6E6", width=1)

        draw.rectangle([0, 0, CANVAS_SIZE-1, CANVAS_SIZE-1], outline="#CCCCCC", width=1)
        self._canvas_grid_size = size
        self.has_content = False
        self.update_canvas_display()

    def toggle_topmost(self):
        self.is_topmost = not self.is_topmost
        self.root.attributes("-topmost", self.is_topmost)
        if self.is_topmost:
            self.top_btn.config(text="📌 取消置顶", fg=HIGHLIGHT_COLOR)
        else:
            self.top_btn.config(text="📌 置顶窗口", fg=SUB_TEXT_COLOR)

    def get_pixel_color_ctypes(self, x, y):
        hdc = ctypes.windll.user32.GetDC(0)
        color = ctypes.windll.gdi32.GetPixel(hdc, int(x), int(y))
        ctypes.windll.user32.ReleaseDC(0, hdc)
        if color == 0xFFFFFFFF: return (0, 0, 0)
        r = color & 0xFF
        g = (color >> 8) & 0xFF
        b = (color >> 16) & 0xFF
        return (r, g, b)

    def get_monitors(self):
        monitors = []
        try:
            def monitor_enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
                mon_info = MONITORINFOEX()
                mon_info.cbSize = ctypes.sizeof(MONITORINFOEX)
                if ctypes.windll.user32.GetMonitorInfoA(hMonitor, ctypes.byref(mon_info)):
                    r = mon_info.rcMonitor
                    monitors.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
                return True
            MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(RECT), ctypes.c_double)
            ctypes.windll.user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(monitor_enum_proc), 0)
        except: pass
        return monitors

    def start_screen_pick(self):
        self.root.withdraw()
        self.root.update()
        self.root.after(100, self._init_screen_grab)

    def _capture_screen(self):
        if self.use_all_screens:
            try:
                return ImageGrab.grab(all_screens=True)
            except (TypeError, OSError):
                self.use_all_screens = False
        return ImageGrab.grab()

    def _init_screen_grab(self):
        self.picking_active = True
        self.monitors = self.get_monitors()
        if not self.monitors:
            self.monitors = [(0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())]

        self.v_min_x = min(m[0] for m in self.monitors)
        self.v_min_y = min(m[1] for m in self.monitors)

        try:
            self.cached_screen = self._capture_screen()
        except Exception as exc:
            self.picking_active = False
            self.cached_screen = None
            self.root.deiconify()
            self.root.lift()
            messagebox.showerror("屏幕取色不可用", f"当前环境无法读取屏幕画面。\n\n{exc}")
            return

        self.last_monitor_idx = -1 

        for i, (x, y, w, h) in enumerate(self.monitors):
            overlay = tk.Toplevel(self.root, bg="#000000")
            overlay.overrideredirect(True) 
            overlay.geometry(f"{w}x{h}+{x}+{y}")
            overlay.attributes("-topmost", True)
            overlay.attributes("-alpha", 0.4) 
            overlay.config(cursor="crosshair")
            
            overlay.bind("<Motion>", self._update_loupe_multi_monitor)
            overlay.bind("<Button-1>", self._pick_color)
            overlay.bind("<Button-3>", lambda e: self._cancel_pick()) 
            overlay.bind("<KeyPress-Escape>", lambda e: self._cancel_pick()) 
            
            self.overlays.append(overlay)
            
        self.loupe_win = tk.Toplevel(self.root)
        self.loupe_win.overrideredirect(True)
        self.loupe_win.attributes("-topmost", True)
        self.loupe_win.geometry("160x160+0+0")
        self.loupe_canvas = tk.Canvas(self.loupe_win, width=160, height=160, bg="black", highlightthickness=1, highlightbackground="white")
        self.loupe_canvas.pack()
        self.loupe_win.bind("<KeyPress-Escape>", lambda e: self._cancel_pick())

        self.loupe_img_id = self.loupe_canvas.create_image(80, 80, image=None)
        self.loupe_canvas.create_line(0, 80, 160, 80, fill="#00FF00", width=1) 
        self.loupe_canvas.create_line(80, 0, 80, 160, fill="#00FF00", width=1) 
        self.loupe_canvas.create_rectangle(76, 76, 84, 84, outline="#00FF00", width=1)
        
        self.loupe_canvas.create_rectangle(0, 120, 160, 160, fill="black", outline="") 
        self.loupe_pos_text_id = self.loupe_canvas.create_text(80, 130, text="", fill="#AAA", font=FONTS["data_small"])
        self.loupe_hex_text_id = self.loupe_canvas.create_text(80, 148, text="", fill="white", font=FONTS["data"])
        self.loupe_color_box_id = self.loupe_canvas.create_rectangle(10, 135, 30, 155, fill="black", outline="white")

        if self.overlays:
            self.overlays[0].focus_force()

    def _update_loupe_multi_monitor(self, event):
        if not self.picking_active: return
        x_root, y_root = event.x_root, event.y_root
        
        current_monitor_idx = -1
        for i, (mx, my, mw, mh) in enumerate(self.monitors):
            if mx <= x_root < mx + mw and my <= y_root < my + mh:
                current_monitor_idx = i
                break
        
        if current_monitor_idx != self.last_monitor_idx:
            self.last_monitor_idx = current_monitor_idx
            for i, overlay in enumerate(self.overlays):
                if i == current_monitor_idx: overlay.attributes("-alpha", 0.01) 
                else: overlay.attributes("-alpha", 0.4) 

        win_x, win_y = x_root + 20, y_root + 20
        if win_x + 160 > self.root.winfo_screenwidth(): win_x = x_root - 180
        if win_y + 160 > self.root.winfo_screenheight(): win_y = y_root - 180
        self.loupe_win.geometry(f"160x160+{int(win_x)}+{int(win_y)}")
        
        try:
            img_x = x_root - self.v_min_x
            img_y = y_root - self.v_min_y
            
            crop_img = self.cached_screen.crop((img_x - 10, img_y - 10, img_x + 10, img_y + 10))
            zoom_img = crop_img.resize((160, 160), Image.NEAREST)
            self.tk_zoom = ImageTk.PhotoImage(zoom_img)
            
            center_rgb = self.get_pixel_color_ctypes(x_root, y_root)
            hex_c = f"#{center_rgb[0]:02X}{center_rgb[1]:02X}{center_rgb[2]:02X}"
            
            self.loupe_canvas.itemconfig(self.loupe_img_id, image=self.tk_zoom)
            self.loupe_canvas.itemconfig(self.loupe_pos_text_id, text=f"({x_root}, {y_root})")
            self.loupe_canvas.itemconfig(self.loupe_hex_text_id, text=hex_c)
            self.loupe_canvas.itemconfig(self.loupe_color_box_id, fill=hex_c)
        except Exception: 
            pass

    def _pick_color(self, event):
        try:
            r, g, b = self.get_pixel_color_ctypes(event.x_root, event.y_root)
            h, l, s = colorsys.rgb_to_hls(r/255, g/255, b/255)
            self.current_hsl = (h, s, l)
            self.sat_scale.set(s)
            self.light_scale.set(l)
            self.update_ui_from_hsl(update_wheel=True)
        except: pass
        self._cancel_pick()

    def _cancel_pick(self):
        self.picking_active = False
        self.cached_screen = None
        if self.loupe_win: self.loupe_win.destroy()
        for overlay in self.overlays:
            overlay.destroy()
        self.overlays = []
        self.root.deiconify()

    def update_wheel_image(self):
        current_s = self.sat_scale.get()
        current_l = self.light_scale.get()
        
        image = Image.new('RGBA', (WHEEL_SIZE, WHEEL_SIZE), (0,0,0,0))
        draw = ImageDraw.Draw(image)
        
        for x, y, hue in self.wheel_pixels:
            r, g, b = ColorHarmony.hsl_to_rgb(hue, current_s, current_l)
            draw.point((x, y), fill=(r, g, b, 255))
            
        image = Image.alpha_composite(image, self.wheel_mask)
        image = Image.alpha_composite(image, self.wheel_shadow)
        
        cx, cy = WHEEL_SIZE // 2, WHEEL_SIZE // 2
        radius = WHEEL_SIZE // 2 - 4
        inner_r = radius * 0.5
        draw = ImageDraw.Draw(image)
        draw.ellipse((cx-inner_r, cy-inner_r, cx+inner_r, cy+inner_r), fill=BG_COLOR)
        draw.ellipse((cx-inner_r, cy-inner_r, cx+inner_r, cy+inner_r), outline="#E0E0E0", width=2)
        
        self.wheel_img = ImageTk.PhotoImage(image)
        self.wheel_canvas.delete("wheel_bg")
        self.wheel_canvas.create_image(0, 0, image=self.wheel_img, anchor=tk.NW, tags="wheel_bg")
        self.wheel_canvas.tag_lower("wheel_bg")

    def draw_wheel_handle(self):
        self.wheel_canvas.delete("handle")
        cx, cy = WHEEL_SIZE // 2, WHEEL_SIZE // 2
        radius = (WHEEL_SIZE // 2 + (WHEEL_SIZE // 2 * 0.5)) / 2 
        
        h, s, l = self.current_hsl
        angle_rad = h * 2 * math.pi
        x = cx + radius * math.cos(angle_rad)
        y = cy + radius * math.sin(angle_rad)
        
        r, g, b = ColorHarmony.hsl_to_rgb(h, s, l)
        fill_color = f"#{r:02X}{g:02X}{b:02X}"
        outline_color = "#000000" if (r*0.299 + g*0.587 + b*0.114) > 128 else "#FFFFFF"

        self.wheel_canvas.create_line(cx, cy, x, y, fill="#E0E0E0", width=1, tags="handle")
        self.wheel_canvas.create_oval(x-9, y-9, x+9, y+9, fill="black", stipple="gray25", outline="", tags="handle")
        self.wheel_canvas.create_oval(x-7, y-7, x+7, y+7, outline=outline_color, width=2, fill=fill_color, tags="handle")

    def on_wheel_interact(self, event):
        cx, cy = WHEEL_SIZE // 2, WHEEL_SIZE // 2
        dx, dy = event.x - cx, event.y - cy
        angle = math.atan2(dy, dx)
        hue = (angle / (2 * math.pi)) % 1.0
        
        _, s, l = self.current_hsl
        self.current_hsl = (hue, s, l)
        self.update_ui_from_hsl(update_wheel=False)

    def on_slider_change(self, event=None):
        if not hasattr(self, 'sat_scale') or not hasattr(self, 'light_scale'): return
        h = self.current_hsl[0]
        s = self.sat_scale.get()
        l = self.light_scale.get()
        self.current_hsl = (h, s, l)
        self.update_ui_from_hsl(update_wheel=True)

    def update_ui_from_hsl(self, update_wheel=True):
        if not hasattr(self, 'sat_scale') or not hasattr(self, 'light_scale'): return
        h, s, l = self.current_hsl
        
        if abs(self.sat_scale.get() - s) > 0.01: self.sat_scale.set(s)
        if abs(self.light_scale.get() - l) > 0.01: self.light_scale.set(l)
        
        rgb = ColorHarmony.hsl_to_rgb(h, s, l)
        
        if hasattr(self, 'info_label'):
            if self.is_rgb_mode:
                self.info_label.config(text=f"基色: {rgb[0]}, {rgb[1]}, {rgb[2]}")
            else:
                hex_c = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
                self.info_label.config(text=f"基色: {hex_c}")
        
        if update_wheel:
            self.update_wheel_image()
        if hasattr(self, 'wheel_canvas'):
            self.draw_wheel_handle()

    def on_grid_size_change(self, event):
        self.root.focus()
        new_size = self.grid_size_var.get()
        if new_size == self._canvas_grid_size:
            return
        self._push_undo()
        self.init_empty_grid()

    def update_canvas_display(self):
        if self.image.size != (CANVAS_SIZE, CANVAS_SIZE):
            self.image = self.image.resize((CANVAS_SIZE, CANVAS_SIZE), Image.NEAREST)

        self.tk_image = ImageTk.PhotoImage(self.image)
        if self.canvas_image_id is None:
            self.canvas_image_id = self.canvas.create_image(
                0, 0, image=self.tk_image, anchor=tk.NW
            )
        else:
            self.canvas.itemconfig(self.canvas_image_id, image=self.tk_image)
        self._update_empty_hint()

    def _update_empty_hint(self):
        """Show guidance until the user creates or imports color data."""
        self.canvas.delete("empty_hint")
        if not self.has_content:
            self.canvas.create_text(
                CANVAS_SIZE // 2, CANVAS_SIZE // 2,
                text="点击“从图片导入”或使用色环开始绘制",
                fill="#999999", font=FONTS["body"], tags="empty_hint",
            )

    def on_canvas_hover(self, event):
        size = self.grid_size_var.get()
        step = CANVAS_SIZE // size
        col, row = event.x // step, event.y // step
        
        if 0 <= col < size and 0 <= row < size:
            self.canvas.config(cursor="hand2")
            x1, y1 = col * step, row * step
            x2, y2 = x1 + step, y1 + step
            
            self.canvas.delete("hover_highlight")
            self.canvas.create_rectangle(x1+1, y1+1, x2-1, y2-1, outline="#FFFFFF", width=2, tags="hover_highlight")
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="#000000", width=1, tags="hover_highlight")
        else:
            self.on_canvas_leave(event)

    def on_canvas_leave(self, event):
        self.canvas.delete("hover_highlight")
        self.canvas.config(cursor="")

    def _event_cell(self, event):
        size = self.grid_size_var.get()
        step = CANVAS_SIZE // size
        col, row = event.x // step, event.y // step
        if 0 <= col < size and 0 <= row < size:
            return col, row, step
        return None

    def _draw_canvas_cell(self, cell):
        col, row, step = cell
        if self._last_draw_cell == (col, row):
            return

        self._last_draw_cell = (col, row)
        x1, y1 = col * step, row * step
        draw = ImageDraw.Draw(self.image)
        h, s, l = self.current_hsl

        if self.brush_mode.get() == "random_hue":
            r, g, b = ColorHarmony.hsl_to_rgb(random.random(), s, l)
        else:
            r, g, b = ColorHarmony.hsl_to_rgb(h, s, l)

        draw.rectangle([x1, y1, x1+step, y1+step], fill=(r, g, b))
        self.has_content = True
        self.update_canvas_display()

    def on_canvas_press(self, event):
        cell = self._event_cell(event)
        if cell is None:
            return
        self._push_undo()
        self._stroke_active = True
        self._last_draw_cell = None
        self._draw_canvas_cell(cell)

    def on_canvas_drag(self, event):
        if not self._stroke_active:
            return
        cell = self._event_cell(event)
        if cell is not None:
            self._draw_canvas_cell(cell)

    def on_canvas_release(self, event=None):
        self._stroke_active = False
        self._last_draw_cell = None

    def action_fill_all(self):
        self._push_undo()
        draw = ImageDraw.Draw(self.image)
        size = self.grid_size_var.get()
        step = CANVAS_SIZE // size
        h, s, l = self.current_hsl
        
        for i in range(size):
            for j in range(size):
                if self.brush_mode.get() == "random_hue":
                     r, g, b = ColorHarmony.hsl_to_rgb(random.random(), s, l)
                else:
                     r, g, b = ColorHarmony.hsl_to_rgb(h, s, l)
                draw.rectangle([i*step, j*step, (i+1)*step, (j+1)*step], fill=(r,g,b))
        
        self.has_content = True
        self.update_canvas_display()

    def action_randomize(self):
        if not self.has_content:
            self.show_toast("当前没有可打乱的颜色")
            return
        self._push_undo()
        size = self.grid_size_var.get()
        step = CANVAS_SIZE // size
        
        colors = []
        for j in range(size):
            for i in range(size):
                cx, cy = int(i*step + step//2), int(j*step + step//2)
                cx, cy = min(cx, CANVAS_SIZE - 1), min(cy, CANVAS_SIZE - 1)
                colors.append(self.image.getpixel((cx, cy)))
        
        random.shuffle(colors)
        
        draw = ImageDraw.Draw(self.image)
        idx = 0
        for j in range(size):
            for i in range(size):
                if idx < len(colors):
                    x, y = i*step, j*step
                    draw.rectangle([x, y, x+step, y+step], fill=colors[idx])
                    idx += 1
        self.update_canvas_display()

    def action_sort(self):
        if not self.has_content:
            self.show_toast("当前没有可排序的颜色")
            return
        self._push_undo()
        size = self.grid_size_var.get()
        step = CANVAS_SIZE // size
        
        colors = []
        for j in range(size):
            for i in range(size):
                cx, cy = int(i*step + step//2), int(j*step + step//2)
                cx, cy = min(cx, CANVAS_SIZE - 1), min(cy, CANVAS_SIZE - 1)
                colors.append(self.image.getpixel((cx, cy)))
        
        def global_sort_key(c):
            r, g, b = c[0]/255.0, c[1]/255.0, c[2]/255.0
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            is_gray = 1 if s < 0.12 or v < 0.15 else 0
            shifted_h = (h + 0.5) % 1.0
            return (is_gray, shifted_h)
            
        colors.sort(key=global_sort_key)
        
        final_colors = []
        for row_idx in range(size):
            row_chunk = colors[row_idx * size : (row_idx + 1) * size]
            row_chunk.sort(key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2])
            final_colors.extend(row_chunk)
        
        draw = ImageDraw.Draw(self.image)
        idx = 0
        for j in range(size):
            for i in range(size):
                if idx < len(final_colors):
                    x, y = i*step, j*step
                    draw.rectangle([x, y, x+step, y+step], fill=final_colors[idx])
                    idx += 1
        self.update_canvas_display()

    def import_images(self):
        paths = filedialog.askopenfilenames(title="选择图片以提取色板（可多选）", filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.bmp")])
        if not paths: return

        # Loading feedback
        self.root.config(cursor="watch")
        self.root.update_idletasks()

        try:
            size = self.grid_size_var.get()
            total_cells = size * size
            num_images = len(paths)
            
            colors_per_img = math.ceil(total_cells / num_images)
            extracted_colors = []
            
            for path in paths:
                img = Image.open(path).convert('RGB')
                img.thumbnail((256, 256))
                
                q_img = img.quantize(colors=colors_per_img, method=0) 
                palette = q_img.getpalette()
                
                for i in range(colors_per_img):
                    if i*3+2 < len(palette):
                        r, g, b = palette[i*3], palette[i*3+1], palette[i*3+2]
                        extracted_colors.append((r, g, b))
            
            extracted_colors = extracted_colors[:total_cells]
            while len(extracted_colors) < total_cells:
                extracted_colors.append((0, 0, 0))
                
            random.shuffle(extracted_colors)

            # Snapshot before mutating canvas
            self._push_undo()

            draw = ImageDraw.Draw(self.image)
            step = CANVAS_SIZE // size
            idx = 0
            for j in range(size):
                for i in range(size):
                    if idx < len(extracted_colors):
                        x, y = i*step, j*step
                        draw.rectangle([x, y, x+step, y+step], fill=extracted_colors[idx])
                        idx += 1

            self.has_content = True
            self.update_canvas_display()

            self.root.config(cursor="")
            self.show_toast(f"成功提取 {num_images} 张图片的色板！可点击排序或打乱寻找灵感。")
        except Exception as e:
            self.root.config(cursor="")
            messagebox.showerror("提取失败", str(e))

    def save_image(self):
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            try:
                self.image.save(path)
                import os
                self.show_toast(f"色卡已保存→ {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("保存失败", str(e))

    def show_toast(self, text):
        if self._toast_after_id is not None:
            self.root.after_cancel(self._toast_after_id)
        self.toast_label.config(text=text)
        self.toast_label.place(relx=0.5, rely=0.9, anchor=tk.CENTER)
        self._toast_after_id = self.root.after(
            TOAST_DURATION, self._hide_toast
        )

    def _hide_toast(self):
        self.toast_label.place_forget()
        self._toast_after_id = None

if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    root = tk.Tk()
    app = GridCanvasEditor(root)
    root.mainloop()