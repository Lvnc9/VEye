import customtkinter as ctk
from customtkinter import *
from CTkTable import CTkTable
from PIL import Image, ImageTk, ImageSequence
import tkinter as tk
import qrcode
import threading
import time

class CustomTextBox(ctk.CTkTextbox):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.undo_stack = []  # Stack to store undo states
        self.bind_shortcuts()  # Bind shortcuts

    def bind_shortcuts(self):
        # Bind keyboard shortcuts
        self.bind("<Control-x>", self.cut_text)
        self.bind("<Control-c>", self.copy_text)
        self.bind("<Control-v>", self.paste_text)
        self.bind("<Control-z>", self.undo_text)
        self.bind("<Control-a>", self.select_all)

    def cut_text(self, event=None):
        try:
            selected_text = self.get("sel.first", "sel.last")
            self.clipboard_clear()
            self.clipboard_append(selected_text)
            self.save_state_for_undo()
            self.delete("sel.first", "sel.last")
        except Exception:
            pass  # No selection, do nothing
        return "break"

    def copy_text(self, event=None):
        try:
            selected_text = self.get("sel.first", "sel.last")
            self.clipboard_clear()
            self.clipboard_append(selected_text)
        except Exception:
            pass  # No selection, do nothing
        return "break"

    def paste_text(self, event=None):
        try:
            clipboard_text = self.clipboard_get()
            self.save_state_for_undo()
            self.insert("insert", clipboard_text)
        except Exception:
            pass  # No clipboard data, do nothing
        return "break"

    def select_all(self, event=None):
        # Select all text in the textbox
        self.tag_add("sel", "1.0", "end")
        return "break"
    
    def undo_text(self, event=None):
        if self.undo_stack:
            self.delete("1.0", "end")  # Clear the current text
            last_state = self.undo_stack.pop()
            self.insert("1.0", last_state)  # Restore the last state
        return "break"

    def save_state_for_undo(self):
        # Save the current state of the text for undo functionality
        current_text = self.get("1.0", "end-1c")  # Get all text except the trailing newline
        self.undo_stack.append(current_text)

class LoadingDialog:
    def __init__(self, parent, gif_path, title="Loading...", gif_size=(400, 300)):
        self.parent = parent
        self.gif_path = gif_path
        self.gif_size = gif_size
        self.window = None
        self.is_running = False
        self.title = title

    def start(self):
        # Create the CTkToplevel window
        self.window = ctk.CTkToplevel(self.parent)
        self.window.title(self.title)
        self.window.geometry("300x300")
        self.window.resizable(False, False)

        # Center the window
        x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - 150
        y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - 150
        self.window.geometry(f"+{x}+{y}")

        self.window.transient(self.parent)  # Set to appear above the parent
        self.window.protocol("WM_DELETE_WINDOW", lambda: None)  # Disable close button

        # Add a label for the GIF
        self.gif_label = ctk.CTkLabel(self.window, text="")
        self.gif_label.pack(expand=True, pady=10)

        # Add a close button
        close_button = ctk.CTkButton(self.window, text="Close", command=self.stop)
        close_button.pack(pady=10)

        # Delay grab_set() until the window is visible
        self.window.after(10, self._set_focus)

        # Start the animation
        self.is_running = True
        self._thread1 = threading.Thread(target=self._animate_gif, daemon=True)
        self._thread2 = threading.Thread(target=self.timeout)
        self._thread1.start()
        self._thread2.start()

    def timeout(self):
        import time
        time.sleep(4)
        print("STOPED!")
        self.stop()

    def _set_focus(self):
        try:
            self.window.grab_set()  # Block interaction with the parent window
        except Exception as e:
            print(f"Focus error: {e}")

    def stop(self):
        # Stop the animation and close the window
        self.is_running = False
        if self.window and self.window.winfo_exists():
            self.window.destroy()

    def _animate_gif(self):
        # Load and animate the GIF
        try:
            gif = Image.open(self.gif_path)
            frames = [
                ImageTk.PhotoImage(frame.copy().resize(self.gif_size, Image.Resampling.LANCZOS))
                for frame in ImageSequence.Iterator(gif)
            ]
            frame_count = len(frames)
            frame_index = 0

            while self.is_running:
                if self.window and self.window.winfo_exists() and self.gif_label.winfo_exists():
                    frame = frames[frame_index]
                    self.gif_label.configure(image=frame)
                    frame_index = (frame_index + 1) % frame_count
                    self.gif_label.update()
                else:
                    break
                self.gif_label.after(100)  # Adjust the frame rate for your GIF

        except Exception as e:
            print(f"Animation error: {e}")

class CTKTableWithEntries(ctk.CTkFrame):
    def __init__(self, master, headers=None, rows=None, **kwargs):
        super().__init__(master, **kwargs)
        self.headers = headers
        self.rows = rows

        # Header row
        if not headers:
            self.headers = ["Column", "Review Number", "Review Date", "Title of Changes"]
        self.header_labels = []

        # Add header labels
        for col, header_text in enumerate(self.headers):
            label = ctk.CTkLabel(
                self, 
                text=header_text, 
                width=100, 
                justify="center", 
                font=("Arial", 14, "bold"), 
                anchor="center",
                fg_color="#2A8C55",
                corner_radius=8,
            )
            label.grid(row=0, column=col, padx=5, pady=5, sticky="nsew")
            
            self.header_labels.append(label)

        # Add data rows (mock data)
        if not rows:
            self.rows = [
                ["1", "01", "1403/07/27", UndoableEntry(self, width=300)],
                ["2", "01", "1403/07/27", UndoableEntry(self, width=300)],
                ["3", "03", "1403/08/08", UndoableEntry(self, width=300)],
            ]

        #for e in self.rows:
        #    e.append(ctk.CTkEntry(self, width=150))
        
        # Populate rows
        for row_index, row_data in enumerate(self.rows, start=1):
            for col_index, cell_data in enumerate(row_data):
                if isinstance(cell_data, ctk.CTkEntry):
                    cell_data.grid(row=row_index, column=col_index, padx=5, pady=5, sticky="nsew")
                else:
                    label = ctk.CTkLabel(self, text=cell_data, width=100, justify="center", anchor="center")
                    label.grid(row=row_index, column=col_index, padx=5, pady=5, sticky="nsew")

        # Example of how to set an entry value programmatically
        self.rows[0][3].insert(0, "Prototype Change.")

class Widgets:
    """ Widgets for customing elements """

    def select_all(event=None):
        """Select all text in the Entry widget."""
        event.widget.select_range(0, END)  # Select all text
        event.widget.icursor(END)          # Move the cursor to the end
        return "break"  # Prevent default behavior (e.g., inserting 'a')
    
    #def undo(event):
    #    """Undo the last change."""
    #    try:
    #        event.widget.edit_undo()
    #    except tk.TclError:
    #        pass  # Ignore if there's nothing to undo
    #    return "break"
    
    def cut(event=None):
        """Cut selected text to clipboard."""
        event.widget.event_generate("<<Cut>>")
        return "break"
    
    def copy(event=None):
        """Copy selected text to clipboard."""
        event.widget.event_generate("<<Copy>>")
        return "break"

    
    def paste(event=None):
        """Paste text from clipboard."""
        event.widget.event_generate("<<Paste>>")
        return "break"
    
    def open_file(label, mode:str):
        # Open the file selector dialog
        if mode == "document":
            message = (
                ("Office Word", "*.docx"),
                ("Office Powerpoint", "*.pptx"),

                ("Office Excel - (macro-enabled )", "*xlsm"),
                ("Office Excel - (Binary Workbook)", "*xlsb"),
                ("Office Excel - (Before Excel 2007)", "*xls"),
                ("Office Excel - (Excel templates)", "*xltx"),
                ("Pdf file", "*.pdf"),
                ("txt file", "*.txt"),
                ("csv files", "*.csv"),
                )
        elif mode == "video":
            message = (
                ("mp4 videos", "*.mp4"),
                ("mov videos", "*.mov"),
                ("WebM files", "*.webm"),
                ("All video files", "*.*"),
            )
        elif mode == "picture":
            message = (
                ("PNG file", "*.png"),
                ("JPEG file", "*.jpeg"),
                ("JPNJ files", "*.jpng"),
                ("All picture files", "*.*"),
            )            

        file_path = filedialog.askopenfilename(
            title="Select a File",
            filetypes=message,
        )
        if file_path:
            # Update the label with the selected file path
            file_path = file_path.split("/")
            file_path = file_path[-1]
            
            file_icon = Image.open("./img/file1.png")
            file_icon = CTkImage(
                dark_image=file_icon, 
                light_image=file_icon, 
                size=(17,17)
            )
            
            label.configure(
                text_color="#601E88", 
                anchor="w", 
                justify="left", 
                font=("Arial Bold", 14), 
                image=file_icon, 
                compound='left',
                text=f"Selected File: {file_path}",
            )


    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        # CTkTextbox widget
        # Bind hotkeys for text operations
        self.bind("<Control-a>", self.select_all)  # Select All
        self.bind("<Control-c>", self.copy_text)  # Copy
        self.bind("<Control-v>", self.paste_text)  # Paste
        self.bind("<Control-x>", self.cut_text)  # Cut

    def select_all(self, event=None):
        """Select all text in the textbox."""
        self.tag_add("sel", "1.0", ctk.END)
        self.mark_set("insert", "1.0")
        self.see("insert")
        return "break"

    def copy_text(self, event=None):
        """Copy selected text to the clipboard."""
        try:
            selected_text = self.textbox.selection_get()
            self.clipboard_clear()
            self.clipboard_append(selected_text)
        except tk.TclError:
            pass
        return "break"

    def paste_text(self, event=None):
        """Paste text from the clipboard."""
        try:
            clipboard_text = self.clipboard_get()
            self.insert(ctk.INSERT, clipboard_text)
        except tk.TclError:
            pass
        return "break"

    def cut_text(self, event=None):
        """Cut selected text to the clipboard."""
        try:
            selected_text = self.textbox.selection_get()
            self.clipboard_clear()
            self.clipboard_append(selected_text)
            self.textbox.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        return "break"

class UndoableEntry(ctk.CTkEntry):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.history = []  # To store text history
        self.history_index = -1  # Current position in history
        
        # Bind key events to track changes
        
        self.bind("<KeyRelease>", self.track_changes)

    def track_changes(self, event=None):
        """Track text changes for undo/redo."""
        current_text = self.get()
        # If the text is different from the last history state, record it
        if not self.history or self.history[self.history_index] != current_text:
            self.history = self.history[:self.history_index + 1]  # Trim redo states
            self.history.append(current_text)
            self.history_index = len(self.history) - 1

        # Bind clipboard actions
        self.bind("<Control-x>", self.cut_text)  # Cut
        self.bind("<Control-c>", self.copy_text)  # Copy
        self.bind("<Control-v>", self.paste_text)  # Paste
        self.bind("<Control-a>", self.select_all)  # Select All
        self.bind("<Control-z>", self.undo)
        self.bind("<Control-Shift-Z>", self.redo)

    def undo(self, event=None):
        """Undo the last change.""" 
        if self.history_index > 0:
            self.history_index -= 1
            self.set(self.history[self.history_index])

    def redo(self, event=None):
        """Redo the undone change."""
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.set(self.history[self.history_index])

    def set(self, text):
        """Set the text in the entry without triggering events."""
        self.delete(0, ctk.END)
        self.insert(0, text)
    
    def cut_text(self, event=None):
        """Cut selected text to the clipboard."""
        try:
            start, end = self.get_selection_range()
            self.clipboard_clear()
            self.clipboard_append(self.get()[start:end])
            self.delete(start, end)
        except tk.TclError:
            pass
        return "break"

    def copy_text(self, event=None):
        """Copy selected text to the clipboard."""
        try:
            start, end = self.get_selection_range()
            self.clipboard_clear()
            self.clipboard_append(self.get()[start:end])
        except tk.TclError:
            pass
        return "break"

    def paste_text(self, event=None):
        """Paste text from the clipboard."""
        try:
            clipboard_text = self.clipboard_get()
            start, end = self.get_selection_range()
            if start is not None and end is not None:
                self.delete(start, end)
                self.insert(start, clipboard_text)
            else:
                self.insert(ctk.END, clipboard_text)
        except tk.TclError:
            pass
        return "break"

    def select_all(self, event=None):
        """Select all text in the entry widget."""
        self.select_range(0, ctk.END)
        self.icursor(ctk.END)  # Move the cursor to the end
        return "break"

    def get_selection_range(self):
        """Get the current selection range in the entry widget."""
        try:
            return self.index(ctk.SEL_FIRST), self.index(ctk.SEL_LAST)
        except tk.TclError:
            return None, None
    
    #def undo(event):
    #    """Undo the last change."""
    #    try:
    #        event.widget.edit_undo()
    #    except tk.TclError:
    #        pass  # Ignore if there's nothing to undo
    #    return "break"
    
class Poster:

    def __init__(self, parent):
        #super().__init__(master)
        #self.title("BarAvard24. Business Management")
        #set_appearance_mode("light")
        self.parent = parent

        self.base_font = ctk.CTkFont(family="Arial", size=12)
        self.bold_font = ctk.CTkFont(family="Arial", size=12, weight="bold")
        self.italic_font = ctk.CTkFont(family="Arial", size=12, slant="italic")
        self.underline_font = ctk.CTkFont(family="Arial", size=12, underline=1)
        
        self.is_bold = False
        self.is_italic = False
        self.is_underlined = False

        self.main_page()
        self.half_fields()
        self.half_fields_conf()
        
        #self.login()
        #self.sidebar()
        #self.main_page()
        #self.half_fields()
        #self.configurations()
        #self.half_fields_conf()
        #self.bindings()

    def run(self):
        self.sidebar()
        self.main_page()
        self.half_fields()
        self.half_fields_conf()
        self.configurations()
        self.bindings()

    def show_loading_dialog(self):
        # Create and start the loading dialog
        import time
        loading_dialog = LoadingDialog(self, "./img/loading-03.gif", gif_size=(200, 200))
        loading_dialog.start()


    def update_font(self, element):
        """Update the font based on the active styles."""
        new_font = ctk.CTkFont(family="Arial", size=12)

        if self.is_bold:
            new_font.configure(weight="bold")
        if self.is_italic:
            new_font.configure(slant="italic")
        if self.is_underlined:
            new_font.configure(underline=1)

        element.configure(font=new_font)

        self.current_font = new_font
        self.apply_font_to_selection(element)

    def apply_font_to_selection(self, element):
        """Apply the current font to the selected text."""
        try:
            selected_text = element.selection_get()
            start_index = element.index("sel.first")
            end_index = element.index("sel.last")

            element.delete(start_index, end_index)
            element.insert(start_index, selected_text, (self.current_font,))
        except tk.TclError:
            pass  # No text selected

    def toggle_bold(self, element):
        """Toggle bold style."""
        self.is_bold = not self.is_bold
        self.update_font(element)

    def toggle_italic(self, element):
        """Toggle italic style."""
        self.is_italic = not self.is_italic
        self.update_font(element)

    def toggle_underline(self, element):
        """Toggle underline style."""
        self.is_underlined = not self.is_underlined
        self.update_font(element)

    def copy_text(self, element):
        """Copy the text in the entry widget to the clipboard."""
        text = element.get()
        self.clipboard_clear()
        self.clipboard_append(text)
        tk.messagebox.showinfo("Copied", "Text copied to clipboard!")

    def success_mssg(self):
        tk.messagebox.showinfo("Success", "Successfully saved to archive.")
        

    def bindings(self):
        self.main_view.bind("<MouseWheel>", self.on_mouse_scroll)
        self.main_view.bind("<Button-4>", lambda e: self.main_view._parent_canvas.yview_scroll(-1, "units"))  # Linux
        self.main_view.bind("<Button-5>", lambda e: self.main_view._parent_canvas.yview_scroll(1, "units"))   # Linux

    def on_mouse_scroll(self, event):
        self.main_view._parent_canvas.yview_scroll(-1 * (event.delta // 120), "units")

        #self.exp_1_1_ent.bind("<Control-a>", Widgets.select_all)
        #self.exp_1_1_ent.bind("<Command-a>", Widgets.select_all)
        #self.exp_1_1_ent.bind("<Control-c>", Widgets.copy)
        #self.exp_1_1_ent.bind("<Control-v>", Widgets.paste)
        #self.exp_1_1_ent.bind("<Control-x>", Widgets.cut)
        #self.exp_1_1_ent.bind("<Control-z>", self.exp_1_1_ent.undo)

        self.explain_1_5_ent.bind("<Control-a>", Widgets.select_all)
        self.explain_1_5_ent.bind("<Control-c>", Widgets.copy)
        self.explain_1_5_ent.bind("<Control-v>", Widgets.paste)
        self.explain_1_5_ent.bind("<Control-x>", Widgets.cut)
        self.explain_1_5_ent.bind("<Control-z>", self.explain_1_5_ent.undo)


    def sidebar(self):
        self.sidebar_frame = CTkFrame(
            master=self, 
            fg_color="#2A8C55", 
            width=176, 
            height=650, 
            corner_radius=0
        )
        logo_img_data = Image.open("./img/organization.png")
        logo_img = CTkImage(
            dark_image=logo_img_data, 
            light_image=logo_img_data, 
            size=(77.68, 85.42)
        )

        self.idk = CTkLabel(
            master=self.sidebar_frame, 
            text="", 
            image=logo_img
            )

        analytics_img_data = Image.open("./img/stats1.png")
        analytics_img = CTkImage(
            dark_image=analytics_img_data, 
            light_image=analytics_img_data
            )
        
        self.dashboard = CTkButton(
            master=self.sidebar_frame, 
            image=analytics_img, 
            text="Dashboard", 
            fg_color="#fff", 
            font=("Arial Bold", 14),
            text_color="#2A8C55",
            hover_color="#207244", 
            anchor="w"
        )

        package_img_data = Image.open("./img/box1.png")
        package_img = CTkImage(
            dark_image=package_img_data, 
            light_image=package_img_data)

        self.making_documents = CTkButton(
            master=self.sidebar_frame, 
            image=package_img, 
            text="Making Documents", 
            fg_color="transparent", 
            font=("Arial Bold", 14),  
            hover_color="#207244", 
            anchor="w"
        )

        returns_img_data = Image.open("./img/returns_icon.png")
        returns_img = CTkImage(
            dark_image=returns_img_data, 
            light_image=returns_img_data
            )
        self.document_history = CTkButton(
            master=self.sidebar_frame, 
            image=returns_img, 
            text="Document History", 
            fg_color="transparent", 
            font=("Arial Bold", 14), 
            hover_color="#207244", 
            anchor="w"
            )

        #settings_img_data = Image.open("settings_icon.png")
        #settings_img = CTkImage(
        #    dark_image=settings_img_data, 
        #    light_image=settings_img_data)
        #self.settings = CTkButton(
        #    master=self.sidebar_frame, 
        #    image=settings_img, 
        #    text="Settings", 
        #    fg_color="transparent", 
        #    font=("Arial Bold", 14), 
        #    hover_color="#207244", 
        #    anchor="w"
        #    )

        person_img_data = Image.open("./img/person_icon.png")
        person_img = CTkImage(
            dark_image=person_img_data, 
            light_image=person_img_data
            )
        self.account = CTkButton(
            master=self.sidebar_frame, 
            image=person_img, 
            text="Account", 
            fg_color="transparent", 
            font=("Arial Bold", 14), 
            hover_color="#207244", 
            anchor="w"
            )
    
    def configurations(self):
        self.sidebar_frame.pack_propagate(0)
        self.sidebar_frame.pack(
            fill="y", 
            anchor="w", 
            side="left"
        )

        self.idk.pack(
            pady=(38, 0), 
            anchor="center"
        )

        self.dashboard.pack(
            anchor="center", 
            ipady=5, 
            pady=(60, 0)
        )

        self.making_documents.pack(
            anchor="center", 
            ipady=5, 
            pady=(16, 0)
        )

        self.document_history.pack(
            anchor="center", 
            ipady=5, 
            pady=(16, 0)
        )

        #self.settings.pack(
        #    anchor="center", 
        #    ipady=5, 
        #    pady=(16, 0)
        #)
        
        self.account.pack(
            anchor="center", 
            ipady=5, 
            pady=(160, 0)
        )

        #self.main_view.pack_propagate(0)

    def main_view_pack(self):
        self.main_view.pack(
            side="right"
            )


        self.title_frame.pack(
            anchor="w",
            fill="x",
            expand=True,
            padx=27, 
            )
        self.title_lbl.pack(
            anchor="n", 
            side="top",
            fill='x',
            pady=(35,10),
            padx=(27, 40),
        )
        
        self.section_lbl.pack(
            anchor='w',
            side='right',
            pady=(35,10),
            padx=(27, 40),
        )



    def main_page(self):
        self.main_view = CTkScrollableFrame(
            master=self.parent.main_view_1,
            fg_color="#d6d4ce",  
            width=1200, 
            height=1080, 
            corner_radius=0
        )

        self.title_frame = CTkFrame(
            master=self.main_view, 
            fg_color="#442f7a",
            #bg_color=""
            height=400,
            width=1200,
            )

        self.content_frm = CTkFrame(
            master=self.main_view,

        )
        
        self.title_lbl = CTkLabel(
            master=self.title_frame, 
            text="Business Management System", 
            font=("Arial Black", 25),
            justify="center",
            text_color="#fff")
        
        
        #self.compony_lbl = CTkLabel(
        #    master=self.upside_frm,
        #    text="Business Management Administration",
        #    font=("Arial Bold", 25),
        #    justify="left",
        #    compound='left',
        #)

        self.section_lbl = CTkLabel(
            master=self.title_frame,
            text="System Documents/Design Poster",
            text_color='#fff',
            font=("Arial Bold", 14),
        )



    def half_fields(self):
        self.explain_1_1_frm = CTkFrame(
            self.main_view,
            fg_color="#fff",
        )
        img_doc = Image.open("./img/rules.png")
        img_doc = CTkImage(
            light_image=img_doc,
            dark_image=img_doc,
            size=(40,40),
        )
        self.exp_1_1_lbl = CTkLabel(
            self.explain_1_1_frm,
            text=" Short Explanation:",
            justify='left',
            image=img_doc,
            compound='left',
            font=("Arial Black", 18),
            text_color="#601e88",
        )
        self.conf_horizontal_separator_1_1 = CTkFrame(
            self.explain_1_1_frm, 
            fg_color="gray", 
            height=2, 
            width=450
        )

        self.exp_1_1_ent = UndoableEntry(
            self.explain_1_1_frm,
            justify='left',
            placeholder_text="1-Porpuse:",
            width=400,
        )

        self.exp_2_1_ent = UndoableEntry(
            self.explain_1_1_frm,
            justify='left',
            placeholder_text="1.1-Type Purpose:",
            width=400,
        )


        self.exp_3_1_ent = UndoableEntry(
            self.explain_1_1_frm,
            justify='left',
            placeholder_text="1.2-",
            width=400,            
        )

        self.explain_1_2_frm = CTkFrame(
            self.main_view,
            fg_color="#fff",
        )
        
        self.exp_1_2_lbl = CTkLabel(
            self.explain_1_2_frm,
            text="Short Explanation:",
            justify='left',
            image=img_doc,
            compound='left',
            font=("Arial Black", 18),
            text_color="#601e88",
        )

        self.conf_horizontal_separator_2_1 = CTkFrame(
            self.explain_1_2_frm, 
            fg_color="gray", 
            height=2, 
            width=450
        )

        self.exp_1_2_ent = UndoableEntry(
            self.explain_1_2_frm,
            justify='left',
            placeholder_text="2-Usage Domain:",
            width=400,
        )

        self.exp_2_2_ent = UndoableEntry(
            self.explain_1_2_frm,
            justify='left',
            placeholder_text="2.1-Type:",
            width=400,
        )

        self.exp_3_2_ent = UndoableEntry(
            self.explain_1_2_frm,
            justify='left',
            placeholder_text="2.2-",
            width=400,
        )
        
        self.explain_1_3_frm = CTkFrame(
            self.main_view,
            fg_color="#fff",
        )

        self.explain_1_3_lbl = CTkLabel(
            self.explain_1_3_frm,
            text="Responsibilities:",
            justify='right',
            image=img_doc,
            compound='left',
            font=("Arial Black", 18),
            text_color="#601e88",
        )
        self.conf_horizontal_separator_3_1 = CTkFrame(
            self.explain_1_3_frm, 
            fg_color="gray", 
            height=2, 
            width=450
        )

        self.temp_1_3 = CTkFrame(
            self.explain_1_3_frm,
            fg_color="#fff",
        )
        self.explain_2_3_lbl = CTkLabel(
            self.temp_1_3,
            text="Responder:",
            justify='left',
            text_color="#000000",
            font=("Arial Black", 14),
        )

        self.explain_3_3_lbl = CTkLabel(
            self.temp_1_3,
            text="Reciver:",
            justify='left',
            text_color="#000000",
            font=("Arial Black", 14),
        )

        self.explain_4_3_lbl = CTkLabel(
            self.temp_1_3,
            text="Calculator",
            justify='left',
            text_color="#000000",
            font=("Arial Black", 14),
        )

        self.explain_5_3_lbl = CTkLabel(
            self.temp_1_3,
            text="Supervisor:",
            justify='left',
            text_color="#000000",
            font=("Arial Black", 14),
        )

        self.explain1_3_optMenue = CTkOptionMenu(
            self.temp_1_3,
            values=['Organiztion Post'],
            font=("Arial Black", 12),
        )

        self.explain2_3_optMenue = CTkOptionMenu(
            self.temp_1_3,
            values=['Organiztion Post'],
            font=("Arial Black", 12),
        )

        self.explain3_3_optMenue = CTkOptionMenu(
            self.temp_1_3,
            values=['Organiztion Post'],
            font=("Arial Black", 12),
        )

        self.explain4_3_optMenue = CTkOptionMenu(
            self.temp_1_3,
            values=['Organiztion Post'],
            font=("Arial Black", 12),
        )

        self.explain5_3_optMenue = CTkOptionMenu(
            self.temp_1_3,
            values=['SuperVisor'],
            font=("Arial Black", 12),
        )

        self.explain6_3_optMenue = CTkOptionMenu(
            self.temp_1_3,
            values=['SuperVisor'],
            font=("Arial Black", 12),
        )

        self.explain7_3_optMenue = CTkOptionMenu(
            self.temp_1_3,
            values=['SuperVisor'],
            font=("Arial Black", 12),
        )

        self.explain8_3_optMenue = CTkOptionMenu(
            self.temp_1_3,
            values=['SuperVisor'],
            font=("Arial Black", 12),
        )

        self.explain_1_3_ent = UndoableEntry(
            self.temp_1_3,
            justify='left',
            placeholder_text="3-Responsiblities:",
            width=400,
        )
        self.explain_2_3_ent = UndoableEntry(
            self.temp_1_3,
            justify='left',
            placeholder_text="3-1-",
            width=400,
        )
        self.explain_3_3_ent = UndoableEntry(
            self.temp_1_3,
            justify='left',
            placeholder_text="3-2",
            width=400,
        )
        self.explain_4_3_ent = UndoableEntry(
            self.temp_1_3,
            justify='left',
            placeholder_text="3-3",
            width=400,
        )
        self.explain_5_3_ent = UndoableEntry(
            self.temp_1_3,
            justify='left',
            placeholder_text="3-4",
            width=400,
        )
    
        self.explain_1_4_frm = CTkFrame(
            self.main_view,
            fg_color="#fff",
        )
        self.exp_1_4_lbl = CTkLabel(
            self.explain_1_4_frm,
            text="Short Explanation:",
            justify='left',
            image=img_doc,
            compound='left',
            font=("Arial Black", 18),
            text_color="#601e88",
        )
        self.conf_horizontal_separator_4_1 = CTkFrame(
            self.explain_1_4_frm, 
            fg_color="gray", 
            height=2, 
            width=450
        )

        self.exp_1_4_ent = UndoableEntry(
            self.explain_1_4_frm,
            justify='left',
            placeholder_text="1-Porpuse:",
            width=400,
        )

        self.exp_2_4_ent = UndoableEntry(
            self.explain_1_4_frm,
            justify='left',
            placeholder_text="1.1-Type Purpose:",
            width=400,
        )


        self.exp_3_4_ent = UndoableEntry(
            self.explain_1_4_frm,
            justify='left',
            placeholder_text="1.2-",
            width=400,
        )

        self.explain_5_frm = CTkFrame(
            self.main_view,
            fg_color="#fff",
        )
        self.exp_1_5_lbl = CTkLabel(
            self.explain_5_frm,
            text="Long Explanation:",
            justify='left',
            image=img_doc,
            compound='left',
            font=("Arial Black", 18),
            text_color="#601e88",
        )
        self.conf_horizontal_separator_5_1 = CTkFrame(
            self.explain_5_frm, 
            fg_color="gray", 
            height=2, 
            width=450
        )
        self.explain_1_5_1_frm = CTkFrame(
            self.explain_5_frm,
            fg_color="#fff",
        )
        self.explain_1_5_2_frm = CTkFrame(
            self.explain_5_frm,
            fg_color="#fff",
        )
        self.explain_1_5_3_frm = CTkFrame(
            self.explain_5_frm,
            fg_color="#fff",
        )
        self.explain_1_5_4_frm = CTkFrame(
            self.explain_5_frm,
            fg_color="#fff",
        )

        self.file_1_5_btn = CTkButton(
            self.explain_1_5_1_frm,
            text="Add Picture",
            fg_color="#601E88", 
            hover_color="#E44982", 
            font=("Arial Bold", 12), 
            text_color="#ffffff", 
            width=50,
            command=lambda: Widgets.open_file(self.file_4_5_lbl, "picture")
        )

        self.file_2_5_btn = CTkButton(
            self.explain_1_5_1_frm,
            text="Add File",
            fg_color="#601E88", 
            hover_color="#E44982", 
            font=("Arial Bold", 12), 
            text_color="#ffffff", 
            width=50,
            command=lambda: Widgets.open_file(self.file_4_5_lbl, "document")
        )

        self.file_3_5_btn = CTkButton(
            self.explain_1_5_1_frm,
            text="Add Video",
            fg_color="#601E88", 
            hover_color="#E44982", 
            font=("Arial Bold", 12), 
            text_color="#ffffff", 
            width=50,
            command=lambda: Widgets.open_file(self.file_4_5_lbl, "video")
        )

        self.file_4_5_lbl = CTkLabel(
            self.explain_1_5_1_frm,
            text='',
            font=("Arial Bold", 12), 
            text_color="#ffffff",
        )

        self.font_1_5_btn = CTkButton(
            self.explain_1_5_2_frm,
            text="B",
            fg_color="#c4beab", 
            hover_color="#E44982", 
            font=("Arial Bold", 12), 
            text_color="#000000", 
            width=10,
            command=lambda: self.toggle_bold(self.explain_1_5_ent)
        )

        self.font_2_5_btn = CTkButton(
            self.explain_1_5_2_frm,
            text="I",
            fg_color="#c4beab", 
            hover_color="#fff", 
            font=("Arial Bold", 12), 
            text_color="#000000", 
            width=10,
            command=lambda:self.toggle_italic(self.explain_1_5_ent)
        )

        self.font_3_5_btn = CTkButton(
            self.explain_1_5_2_frm,
            text="U",
            fg_color="#c4beab", 
            hover_color="#E44982", 
            font=("Arial Bold", 12),
            text_color="#000000",   
            width=10,
            command=lambda: self.toggle_underline(self.explain_1_5_ent)
        )

        self.copy_1_5_btn = CTkButton(
            self.explain_1_5_2_frm,
            text="Copy",
            fg_color="#c4beab", 
            hover_color="#E44982",
            text_color="#000000", 
            font=("Arial Bold", 12), 
            width=50,
            command=lambda: self.copy_text(self.explain_1_5_ent),
            
        )

        self.explain_1_5_ent = UndoableEntry(
            self.explain_1_5_3_frm,
            justify='left',
            placeholder_text="5-Explain:",
            font=self.base_font,
            #border_color="#b8af98",
            width=400,
        )
        
        self.explain_2_5_txt = CustomTextBox(
            self.explain_1_5_4_frm,
            #justify='left',
            #placeholder_text="5-1-Type By the Operator:",
            border_color="#030202",
            fg_color="#b8a7a7",
            #placeholder_text="5-1-Type By The Operator",
            #justify='left',
            width=700,
            height=200,
            corner_radius=8,            
        )

        self.explain_6_frm = CTkFrame(
            self.main_view,
            fg_color="#fff",
        )
        #self.bold_font = ctk.CTkFont(family="Arial", size=16, weight="bold")
        
        insurrance_img = Image.open("./img/warranty.png")

        insurrance_img = CTkImage(
            dark_image=insurrance_img,
            light_image=insurrance_img,
            size=(50,50)
        )
        self.insurance_lbl = CTkLabel(
            self.explain_6_frm,
            text=" Insurance:",
            justify='left',
            image=insurrance_img,
            compound='left',
            font=("Arial Black", 18),
            text_color="#601e88",
        )
        self.conf_horizontal_separator_6_1 = CTkFrame(
            self.explain_6_frm, 
            fg_color="gray", 
            height=2, 
            width=450
        )
        self.explain_6_1_frm = CTkFrame(
            self.explain_6_frm,
            fg_color="#fff",
        )

        self.explain_6_1_1_frm = CTkFrame(
            self.explain_6_1_frm,
            fg_color="#fff",
        )

        self.explain_6_1_2_frm = CTkFrame(
            self.explain_6_1_frm,
            fg_color="#fff",
        )


        self.insurance_1_6_ent = UndoableEntry(
            self.explain_6_1_1_frm,
            placeholder_text="6-1-Type the title of include",
            font=self.base_font,
            #border_color="#b8af98",
            width=400,
        )

        self.insurance_2_6_ent = UndoableEntry(
            self.explain_6_1_1_frm,
            placeholder_text="6-2-Type the title of include",
            font=self.base_font,
            #border_color="#b8af98",
            width=400,
        )

        self.insurance_1_6_btn = CTkButton(
            self.explain_6_1_1_frm,
            text="Document Link",
            fg_color="#c4beab", 
            hover_color="#E44982",
            text_color="#000000", 
            font=("Arial Bold", 12), 
            width=150,
            command=lambda: Widgets.open_file(self.insurance_3_6_lbl, "document"),
        )

        self.insurance_2_6_btn = CTkButton(
            self.explain_6_1_1_frm,
            text="Document Link",
            fg_color="#c4beab", 
            hover_color="#E44982",
            text_color="#000000", 
            font=("Arial Bold", 12), 
            width=150,
            command=lambda: Widgets.open_file(self.insurance_4_6_lbl, "document"),
        )
        self.insurance_3_6_lbl = CTkLabel(
            self.explain_6_1_1_frm,
            text='',
            font=("Arial Bold", 12), 
            text_color="#ffffff",
        )

        self.insurance_4_6_lbl = CTkLabel(
            self.explain_6_1_1_frm,
            text='',
            font=("Arial Bold", 12), 
            text_color="#ffffff",
        )
        img1 = Image.open("./img/insurance1.png")
        img2 = Image.open("./img/insurance2.png")

        img1 = CTkImage(
            dark_image=img1,
            light_image=img1,
            size=(100,100)
        )

        img2 = CTkImage(
            dark_image=img2,
            light_image=img2,
            size=(100,100)
        )

        self.qr_code_1_6_lbl = CTkLabel(
            self.explain_6_1_2_frm,
            text="",
            anchor="w", 
            justify="left", 
            font=("Arial Bold", 24), 
            image=img1, 
            compound='left',
            )

        self.qr_code_2_6_lbl = CTkLabel(
            self.explain_6_1_2_frm,
            text="",
            anchor="w", 
            justify="left", 
            font=("Arial Bold", 24), 
            image=img2, 
            compound='left',
            )

        self.explain_7_frm = CTkFrame(
            self.main_view,
            fg_color="#fff",
        )
        change_img = Image.open("./img/change.png")
        change_img = CTkImage(
            light_image=change_img,
            dark_image=change_img,
            size=(50,50)
        )
        self.table_7_lbl = CTkLabel(
            self.explain_7_frm,
            text=" Table of Changes",
            anchor="w", 
            justify="left",
            image=change_img,
            compound='left',
            font=("Arial Black", 18),
            text_color="#601e88",
        )
        self.conf_horizontal_separator_7_1 = CTkFrame(
            self.explain_7_frm, 
            fg_color="gray", 
            height=2, 
            width=450
        )
        self.table_7_tbl = CTKTableWithEntries(
            self.explain_7_frm
        )

        self.explain_8_frm = CTkFrame(
            self.main_view,
            fg_color="#fff",
        )
        scan_img = Image.open('./img/footnote.png')
        scan_img = CTkImage(
            light_image=scan_img,
            dark_image=scan_img,
            size=(75,75)
        )
        self.footnote_8_lbl = CTkLabel(
            self.explain_8_frm, 
            text=" Footnote", 
            anchor="w", 
            image=scan_img,
            compound="left",
            justify="right", 
            font=("Arial Black", 18),
            text_color="#601e88",
        )
        self.conf_horizontal_separator_8_1 = CTkFrame(
            self.explain_8_frm, 
            fg_color="gray", 
            height=2, 
            width=450
        )
        self.footnote_qr_lbl = CTkLabel(
            self.explain_8_frm,
            text="",
            image=img2,
            compound="left",
        )

        self.explain_8_1_frm = CTkFrame(
            self.explain_8_frm,
            fg_color="#fff",
        )

        vroad = Image.open("./img/vroad.png")
        vroad = CTkImage(
            dark_image=vroad,
            light_image=vroad,
            size=(600,180)
        )
    
        self.footnote_8_1_ent = UndoableEntry(
            self.explain_8_1_frm,
            placeholder_text="Free Text: For example planning unit of the compony",
            font=self.base_font,
            #border_color="#b8af98",
            width=400,
        )

        self.footnote_8_2_ent = UndoableEntry(
            self.explain_8_1_frm,
            placeholder_text="Where to type the desired text",
            font=self.base_font,
            #border_color="#b8af98",
            width=200,
        )

        self.footnote_8_3_ent = UndoableEntry(
            self.explain_8_1_frm,
            placeholder_text="Page Counter:",
            font=self.base_font,
            #border_color="#b8af98",
            width=100,
        )
        self.explain_8_2_frm = CTkFrame(
            self.explain_8_frm,
            fg_color="#000000",
        )
        self.footnote_8_1_lbl = CTkLabel(
            self.explain_8_2_frm,
            text="",
            image=vroad,
            compound="left",
        )

        self.last_9_frm = CTkFrame(
            self.explain_8_frm,
            fg_color="#fff",
        )
        self.save_9_1_btn = CTkButton(
            self.last_9_frm,
            text="Save",
            fg_color="#c4beab", 
            hover_color="#E44982",
            text_color="#000000", 
            font=("Arial Bold", 12), 
            width=150,
            command=self.success_mssg
        )

        self.show_9_2_btn = CTkButton(
            self.last_9_frm,
            text="Show",
            fg_color="#c4beab", 
            hover_color="#E44982",
            text_color="#000000", 
            font=("Arial Bold", 12), 
            width=150,
            command=self.show_loading_dialog
        )
        vroad = Image.open("./img/vroad.png")
        vroad = CTkImage(
            dark_image=vroad,
            light_image=vroad,
            size=(327,50)
        )

    def half_fields_conf(self):
        self.explain_1_1_frm.pack(
            anchor="w",
            fill="x",
            expand=True,
            padx=27,
            pady=(27,0)
        )

        #self.exp_1_lbl.grid(
        #    row=0,
        #    column=0,
        #    pady=15
        #)
        self.exp_1_1_lbl.pack(
            anchor='w',
            padx=10,
            pady=(10,5)
        )
        self.conf_horizontal_separator_1_1.pack(
            anchor='w',
            padx=5,
            pady=(6,25),
        )
        self.exp_1_1_ent.pack(
            anchor='w',
            padx=(20),
            pady=(5),
        )
        self.exp_2_1_ent.pack(
            anchor='w',
            padx=(40),
            pady=(5),
        )

        self.exp_3_1_ent.pack(
            anchor='w',
            padx=40,
            pady=(5)
        )
        
        self.explain_1_2_frm.pack(
            anchor="w",
            fill="x",
            expand=True,
            padx=27,
            pady=5,
        )

        self.exp_1_2_lbl.pack(
            anchor='w',
            padx=10,
            pady=(10,5),
        )
        self.conf_horizontal_separator_2_1.pack(
            anchor='w',
            padx=5,
            pady=(6, 25)
        )
        self.exp_1_2_ent.pack(
            anchor='w',
            padx=(20),
            pady=(5),
        )
        self.exp_2_2_ent.pack(
            anchor='w',
            padx=(40),
            pady=(5),
        )

        self.exp_3_2_ent.pack(
            anchor='w',
            padx=40,
            pady=(5),
        )

        self.explain_1_3_frm.pack(
            anchor="w",
            fill="x",
            expand=True,
            padx=27,
            pady=5,
        )

        #self.explain_1_3_lbl.pack(
        #    #anchor='e',
        #    side=RIGHT,
        #    padx=10,
        #    pady=(10,5),
        #)
        self.explain_1_3_lbl.pack(
            anchor='w',
            padx=4,
            pady=(10,5),
        )
        self.conf_horizontal_separator_3_1.pack(
            anchor='w',
            padx=5,
            pady=(6, 25)
        )
        self.temp_1_3.pack(
            anchor='w',
        )

        self.explain_2_3_lbl.grid(
            row=0,
            column=0,
            padx=4,
            pady=(5),
        )
        self.explain_3_3_lbl.grid(
            row=1,
            column=0,
            padx=4,
            pady=(5),
        )
        self.explain_4_3_lbl.grid(
            row=2,
            column=0,
            padx=4,
            pady=(5),
        )

        self.explain_5_3_lbl.grid(
            row=3,
            column=0,
            padx=4,
            pady=(5),
        )

        self.explain1_3_optMenue.grid(
            row=0,
            column=1,
            padx=4,
            pady=(10,5),
        )
        self.explain2_3_optMenue.grid(
            row=1,
            column=1,
            padx=4,
            pady=(5),
        )
        self.explain3_3_optMenue.grid(
            row=2,
            column=1,
            padx=4,
            pady=(5),
        )
        self.explain4_3_optMenue.grid(
            row=3,
            column=1,
            padx=4,
            pady=(5),
        )

        self.explain5_3_optMenue.grid(
            row=0,
            column=2,
            padx=4,
            pady=(5),
        )
        self.explain6_3_optMenue.grid(
            row=1,
            column=2,
            padx=4,
            pady=(5),
        )
        self.explain7_3_optMenue.grid(
            row=2,
            column=2,
            padx=4,
            pady=(5),
        )
        self.explain8_3_optMenue.grid(
            row=3,
            column=2,
            padx=4,
            pady=(5),
        )

        self.explain_1_3_ent.grid(
            row=0,
            column=3,
            padx=4,
            pady=(5),
        )
        self.explain_2_3_ent.grid(
            row=1,
            column=3,
            padx=4,
            pady=(5),
        )
        self.explain_3_3_ent.grid(
            row=2,
            column=3,
            padx=4,
            pady=(5),
        )
        self.explain_4_3_ent.grid(
            row=3,
            column=3,
            padx=4,
            pady=(5),
        )
        self.explain_5_3_ent.grid(
            row=4,
            column=3,
            padx=4,
            pady=(5),
        )
        self.explain_1_4_frm.pack(
            anchor="w",
            fill="x",
            expand=True,
            padx=27,
            pady=5,
        )
        self.exp_1_4_lbl.pack(
            anchor='w',
            padx=10,
            pady=(10,5)
        )
        self.conf_horizontal_separator_4_1.pack(
            anchor='w',
            padx=5,
            pady=(5,26)
        )
        self.exp_1_4_ent.pack(
            anchor='w',
            padx=(20),
            pady=(5),
        )
        self.exp_2_4_ent.pack(
            anchor='w',
            padx=(40),
            pady=(5),
        )

        self.exp_3_4_ent.pack(
            anchor='w',
            padx=40,
            pady=(5)
        )

        self.explain_5_frm.pack(
            anchor="w",
            fill="x",
            expand=True,
            padx=27,
            pady=(5,0),
        )
        self.exp_1_5_lbl.pack(
            anchor='w',
            expand=True,
            padx=27,
            pady=(10,0),
        )
        self.conf_horizontal_separator_5_1.pack(
            anchor='w',
            padx=5,
            pady=(6,25)
        )
        self.explain_1_5_1_frm.pack(
            anchor="w",
            fill="x",
            expand=True,
            padx=27,
            pady=(25,0),
        )

        self.file_1_5_btn.grid(
            row=0,
            column=0,
            padx=5,
            #pady=5,

        )

        self.file_2_5_btn.grid(
            row=0,
            column=1,
            padx=5,
            #pady=(15,5),
        )
#
        self.file_3_5_btn.grid(
            row=0,
            column=2,
            padx=5,
            #pady=(15,5),
        )
        self.file_4_5_lbl.grid(
            row=0,
            column=3,
            padx=35,
        )

        self.explain_1_5_2_frm.pack(
            anchor="w",
            fill="x",
            expand=True,
            padx=27,
            pady=(8,0),
        )

        self.font_1_5_btn.grid(
            row=0,
            column=0,
            padx=2,
            #pady=(15,5),
        )

        self.font_2_5_btn.grid(
            row=0,
            column=1,
            padx=2,
            #pady=(15,5),
        )

        self.font_3_5_btn.grid(
            row=0,
            column=2,
            padx=2,
            #pady=(15,5),
        )

        self.copy_1_5_btn.grid(
            row=0,
            column=3,
            padx=8,
        )

        self.explain_1_5_3_frm.pack(
            anchor="w",
            fill="x",
            expand=True,
            padx=27,
            pady=(5,0),
        )

        self.explain_1_5_ent.grid(
            row=0,
            column=0,
            pady=5,
            padx=2,
        )

        self.explain_1_5_4_frm.pack(
            anchor="w",
            fill="x",
            expand=True,
            padx=27,
            pady=(5,20),
        )

        self.explain_2_5_txt.grid(
            row=0,
            column=0,
            pady=2,
            padx=2
        )

        self.explain_6_frm.pack(
            anchor="w",
            fill="x",
            expand=True,
            padx=27,
            pady=(15,0),
        )

        self.insurance_lbl.pack(
            anchor='nw',
            padx=5,
            pady=(10,0)
        )
        self.conf_horizontal_separator_6_1.pack(
            anchor='w',
            padx=5,
            pady=(6,25),
        )

        self.explain_6_1_frm.pack(
            anchor='nw',
            padx=5,
        )

        self.explain_6_1_1_frm.pack(
            anchor='w'
        )
        self.explain_6_1_2_frm.pack(
            anchor='w'
        )
        self.insurance_1_6_ent.grid(
            row=0,
            column=0,
            padx=25,
            pady=(5,2),
        )
        self.insurance_2_6_ent.grid(
            row=1,
            column=0,
            padx=25,
            pady=(5,0),
        )
        self.insurance_1_6_btn.grid(
            row=0,
            column=1,
            padx=7,
            pady=(5,0),
        )
        self.insurance_2_6_btn.grid(
            row=1,
            column=1,
            padx=7,
            pady=(5,0),
        )

        self.insurance_3_6_lbl.grid(
            row=0,
            column=2,
            padx=7,
            pady=(5,0),            
        )

        self.insurance_4_6_lbl.grid(
            row=1,
            column=2,
            padx=7,
            pady=(5,0),
        )

        self.qr_code_1_6_lbl.grid(
            row=0,
            column=0,
            padx=10,
            pady=(5,0),
        )
        self.qr_code_2_6_lbl.grid(
            row=0,
            column=1,
            padx=10,
            pady=(5,0),
        )

        self.explain_7_frm.pack(
            anchor="w",
            fill="x",
            expand=True,
            padx=27,
            pady=(15,0),
        )

        self.table_7_lbl.pack(
            anchor='w',
            pady=10,
            padx=10,
        )
        self.conf_horizontal_separator_7_1.pack(
            anchor='w',
            padx=5,
            pady=(6,25),
        )
        self.table_7_tbl.pack(
            anchor='w',
            pady=10,
            padx=5,
        )

        self.explain_8_frm.pack(
            anchor='w',
            expand=True,
            fill='x',
            padx=27,
            pady=(15,0)
        )

        self.footnote_8_lbl.pack(
            anchor='w',
            padx=5,
            pady=(10,0),
        )
        self.conf_horizontal_separator_8_1.pack(
            anchor='w',
            padx=5,
            pady=(6,25),
        )
        self.footnote_qr_lbl.pack(
            anchor='w',
            padx=5,
            pady=(5,0)
        )
        self.explain_8_1_frm.pack(
            anchor='w',
            padx=5,
            pady=(10,0),
        )
        self.footnote_8_1_ent.pack(
            anchor='w',
            padx=5,
            pady=(5,0),
        )

        self.footnote_8_2_ent.pack(
            anchor='w',
            padx=5,
            pady=(5,0),
        )
        self.footnote_8_3_ent.pack(
            anchor='w',
            padx=5,
            pady=(5,0),
        )
        self.last_9_frm.pack(
            fill=X,
            anchor='s',
            padx=5,
            pady=5,
        )
        #self.save_9_1_btn.pack(
        #    side="bottom",
        #    padx=5,
        #    pady=(5,0)
        #)
        self.save_9_1_btn.grid(
            row=0,
            column=0,
            padx=5,
            pady=(5,0)

        )
        self.show_9_2_btn.grid(
            row=0,
            column=1,
            padx=5,
            pady=(5,0)

        )
        self.explain_8_2_frm.pack(
            fill=X,
            anchor='n',
            padx=5,
            pady=(15, 3)
        )
        self.footnote_8_1_lbl.pack(
            #justify="center",
            fill='x',
            side="bottom",
            padx=5,
            pady=(35,30)
        )

        #self.show_9_2_btn.pack(
        #    side="bottom",
        #    padx=5,
        #    pady=(5,0)
        #)

    def configurations(self):
        self.sidebar_frame.pack_propagate(0)
        self.sidebar_frame.pack(
            fill="y", 
            anchor="w", 
            side="left"
        )

        self.idk.pack(
            pady=(38, 0), 
            anchor="center"
        )

        self.dashboard.pack(
            anchor="center", 
            ipady=5, 
            pady=(60, 0)
        )

        self.making_documents.pack(
            anchor="center", 
            ipady=5, 
            pady=(16, 0)
        )

        self.document_history.pack(
            anchor="center", 
            ipady=5, 
            pady=(16, 0)
        )

        #self.settings.pack(
        #    anchor="center", 
        #    ipady=5, 
        #    pady=(16, 0)
        #)
        
        self.account.pack(
            anchor="center", 
            ipady=5, 
            pady=(160, 0)
        )

        #self.main_view.pack_propagate(0)
    
    #def main_view_pack(self):
    #    self.main_view.pack(
    #        side="right"
    #        )
#
#
    #    self.title_frame.pack(
    #        anchor="w",
    #        fill="x",
    #        expand=True,
    #        padx=27, 
    #        )
    #    self.title_lbl.pack(
    #        anchor="n", 
    #        side="top",
    #        fill='x',
    #        pady=(35,10),
    #        padx=(27, 40),
    #    )
    #    
    #    self.section_lbl.pack(
    #        anchor='w',
    #        side='right',
    #        pady=(35,10),
    #        padx=(27, 40),
    #    )

def main():
    """ configurations of root window.
    title, icon, main loop """
    global window 

    #root = tb.Window(
    #    themename="vapor"
    #)

    window = Poster()
    #window.run()
    window.geometry("1080x645")
    window.mainloop()

if __name__ == "__main__":
    main()
