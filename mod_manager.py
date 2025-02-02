import os
import sys
import shutil
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser
import zipfile
import requests

if getattr(sys, 'frozen', False):
    # Running as an executable
    BASE_DIR = sys._MEIPASS
else:
    # Running as a script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "DWNOModManagerconfig.json")

class ModManager:
    def __init__(self, root):
        self.root = root
        self.root.title("DWNO Mod Manager")
        self.root.geometry("1000x600")

        self.config = self.load_config()
        self.GAME_PATH = self.get_game_path()
        self.PLUGIN_FOLDER = os.path.join(self.GAME_PATH, "BepInEx", "plugins")
        self.STAGING_FOLDER = os.path.join(self.GAME_PATH, "BepInEx", "staging")
        os.makedirs(self.PLUGIN_FOLDER, exist_ok=True)
        os.makedirs(self.STAGING_FOLDER, exist_ok=True)

        self.mod_links = self.config.get("mod_links", {})
        self.mod_descriptions = self.config.get("mod_descriptions", {})
        self.mod_vars = {}

        self.create_ui()
        self.update_mod_list()
    
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    content = f.read().strip()
                    if not content:
                        return {"game_path": "", "mod_links": {}, "mod_descriptions": {}}
                    return json.loads(content)
            except json.JSONDecodeError:
                messagebox.showerror("Error", "config.json is corrupted. Resetting settings.")
        return {"game_path": "", "mod_links": {}, "mod_descriptions": {}}
    
    def get_game_path(self):
        game_path = self.config.get("game_path", "")
        if not game_path or not os.path.exists(game_path):
            game_path = self.ask_for_game_path()
            if game_path:
                self.config["game_path"] = game_path
                with open(CONFIG_FILE, "w") as f:
                    json.dump(self.config, f, indent=4)
        return game_path

    def ask_for_game_path(self):
        return filedialog.askdirectory(title="Select Digimon World Next Order Game Folder")

    def create_ui(self):
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True)

        self.frame = ttk.Frame(self.main_frame, padding=10)
        self.frame.pack(fill="both", expand=True, side="left")

        self.bepinex_button = ttk.Button(self.frame, text="Install BepInEx", command=self.install_bepinex)
        self.bepinex_button.pack(side=tk.TOP, pady=5, anchor='w')

        self.mod_list = ttk.Treeview(self.frame, columns=("Status", "Mod Name"), show="headings")
        self.mod_list.heading("Status", text="Status")
        self.mod_list.heading("Mod Name", text="Mod Name")
        self.mod_list.column("Status", width=50, anchor="center")
        self.mod_list.column("Mod Name", width=200)
        self.mod_list.pack(fill="both", expand=True)
        self.mod_list.bind("<ButtonRelease-1>", self.show_mod_info)
        self.mod_list.bind("<Button-1>", self.toggle_status)

        self.toggle_button = ttk.Button(self.frame, text="Save Changes", command=self.toggle_mods)
        self.toggle_button.pack(side=tk.LEFT, pady=5)

        self.refresh_button = ttk.Button(self.frame, text="Refresh", command=self.update_mod_list)
        self.refresh_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.delete_button = ttk.Button(self.frame, text="Delete Mod", command=self.confirm_delete_mod)
        self.delete_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.import_button = ttk.Button(self.frame, text="Import Mods", command=self.import_mods)
        self.import_button.pack(side=tk.RIGHT, pady=5)

        # Right panel for mod description
        self.mod_info_frame = ttk.Frame(self.main_frame, padding=10)
        self.mod_info_frame.pack(fill="both", expand=True, side="right")

        self.mod_description_label = ttk.Label(self.mod_info_frame, text="Mod Description", font=("Arial", 12, "bold"))
        self.mod_description_label.pack(anchor="w")
        
        self.separator = ttk.Separator(self.mod_info_frame, orient="horizontal")
        self.separator.pack(fill="x", pady=5)

        self.mod_description_text = tk.Text(self.mod_info_frame, wrap="word", height=10, width=50, state="disabled")
        self.mod_description_text.pack(fill="both", expand=True, padx=5, pady=5)

        self.nexus_button = ttk.Button(self.mod_info_frame, text="Open in Nexus Mods", command=self.open_nexus_mod)
        self.nexus_button.pack(pady=5)
    
    def update_mod_list(self):
        for item in self.mod_list.get_children():
            self.mod_list.delete(item)
        mods = self.list_mods()
        self.mod_vars = {}
        for mod_name, enabled in mods:
            var = tk.BooleanVar(value=enabled)
            item = self.mod_list.insert("", tk.END, values=("✔" if enabled else "✖", mod_name))
            self.mod_vars[item] = var

    def show_mod_info(self, event):
        selected_item = self.mod_list.selection()
        if selected_item:
            mod_name = self.mod_list.item(selected_item, "values")[1]
            mod_description = self.mod_descriptions.get(mod_name, "No description available.")
            mod_url = self.mod_links.get(mod_name, "")

            self.mod_description_text.config(state="normal")
            self.mod_description_text.delete(1.0, tk.END)
            self.mod_description_text.insert(tk.END, mod_description)
            self.mod_description_text.config(state="disabled")

            self.nexus_button.config(command=lambda: webbrowser.open(mod_url) if mod_url else None)
    
    def confirm_delete_mod(self):
        selected_item = self.mod_list.selection()
        if selected_item:
            mod_name = self.mod_list.item(selected_item, "values")[1]
            response = messagebox.askyesno("Confirm Delete", f"Are you sure you want to permanently delete {mod_name}?")
            if response:
                self.delete_mod(mod_name)
    
    def delete_mod(self, mod_name):
        mod_path_plugin = os.path.join(self.PLUGIN_FOLDER, mod_name)
        mod_path_staging = os.path.join(self.STAGING_FOLDER, mod_name)
        if os.path.exists(mod_path_plugin):
            os.remove(mod_path_plugin)
        elif os.path.exists(mod_path_staging):
            os.remove(mod_path_staging)
        self.update_mod_list()
    
    def toggle_mods(self):
        for item in self.mod_list.get_children():
            mod_name = self.mod_list.item(item, "values")[1]
            current_status = self.mod_list.item(item, "values")[0] == "✔"
            
            if current_status:
                try:
                    src = os.path.join(self.STAGING_FOLDER, mod_name)
                    dst = os.path.join(self.PLUGIN_FOLDER, mod_name)
                except:
                    pass
            else:
                try:
                    src = os.path.join(self.PLUGIN_FOLDER, mod_name)
                    dst = os.path.join(self.STAGING_FOLDER, mod_name)
                except:
                    pass

            if os.path.exists(src):
                shutil.move(src, dst)
        
        self.update_mod_list()

    def toggle_status(self, event):
        col = self.mod_list.identify_column(event.x)
        if col == '#1':  # Only toggle if clicking the 'Status' column
            item = self.mod_list.identify_row(event.y)
            if item:
                current_status = self.mod_list.item(item, "values")[0] == "✔"
                new_status = "✔" if not current_status else "✖"
                mod_name = self.mod_list.item(item, "values")[1]
                self.mod_list.item(item, values=(new_status, mod_name))
    
    def open_nexus_mod(self):
        selected_item = self.mod_list.selection()
        if selected_item:
            mod_name = self.mod_list.item(selected_item, "values")[1]
            mod_url = self.mod_links.get(mod_name, "")
            if mod_url:
                webbrowser.open(mod_url)

    def list_mods(self):
        mods = []
        for folder, enabled in [(self.PLUGIN_FOLDER, True), (self.STAGING_FOLDER, False)]:
            for mod in os.listdir(folder):
                if mod.endswith(".dll"):
                    mods.append((mod, enabled))
        return mods
    
    def import_mods(self):
        mod_folder = filedialog.askdirectory(title="Select Mod Download Folder")
        if mod_folder:
            for file in os.listdir(mod_folder):
                if file.endswith(".zip"):
                    zip_path = os.path.join(mod_folder, file)
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        extract_path = os.path.join(self.STAGING_FOLDER, os.path.splitext(file)[0])
                        zip_ref.extractall(extract_path)
                        
                        for root, _, files in os.walk(extract_path):
                            for mod_file in files:
                                if mod_file.endswith(".dll"):
                                    shutil.move(os.path.join(root, mod_file), self.STAGING_FOLDER)
            
            self.update_mod_list()

    def install_bepinex(self):
        bep_link = "https://builds.bepinex.dev/projects/bepinex_be/666/BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.666%2Bc8aedd5.zip"
        save_path = filedialog.askdirectory(title="Select Game Folder for BepInEx Installation")
        if save_path:
            zip_path = os.path.join(save_path, "BepInEx.zip")
            response = requests.get(bep_link, stream=True)
            
            with open(zip_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(save_path)
            os.remove(zip_path)
            
            messagebox.showinfo("BepInEx Installation", "Please run the game and wait for BepInEx to fully install. Once the game reaches the main menu, close it.")

if __name__ == "__main__":
    root = tk.Tk()
    app = ModManager(root)
    root.mainloop()
