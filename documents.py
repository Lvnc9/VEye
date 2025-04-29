import customtkinter as ctk
from customtkinter import *
from CTkTable import CTkTable
from PIL import Image, ImageTk, ImageSequence
import tkinter as tk
import qrcode
import threading
import os

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
        self._thread = threading.Thread(target=self._animate_gif, daemon=True)
        self._thread.start()

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


class Documents:

    def __init__(self, parent):
        self.parent = parent
        #super().__init__(master)
        ##self.title("BarAvard24. Business Management")
        #set_appearance_mode("light")

        self.base_font = ctk.CTkFont(family="Arial", size=12)
        self.bold_font = ctk.CTkFont(family="Arial", size=12, weight="bold")
        self.italic_font = ctk.CTkFont(family="Arial", size=12, slant="italic")
        self.underline_font = ctk.CTkFont(family="Arial", size=12, underline=1)
        
        self.is_bold = False
        self.is_italic = False
        self.is_underlined = False

        #self.login()
        #self.sidebar()
        #self.main_page()
        #self.column()
        #self.column_conf()
        
        #self.category()
        #self.category_conf()
        #self.title()
        #self.title_conf()

        #self.groups()
        #self.groups_conf()
        
        #self.rearangement()
        #self.rearangment_conf()

        #self.code_part()
        #self.code_conf()
        

        #self.accountant()
        #self.accountant_conf()

        #self.answerer()
        #self.answerer_conf()

        #self.responder()
        #self.responder_conf()

        #self.creater()
        #self.creater_conf()

        #self.confirm()
        #self.confirm_conf()

        #self.approve()
        #self.approve_conf()

        #self.status()
        #self.status_conf()

        #self.last()
        #self.last_conf()

        #self.configurations()
        #self.bindings()

    def show_loading_dialog(self):
        # Create and start the loading dialog
        loading_dialog = LoadingDialog(self, "loading-03.gif", gif_size=(200, 200))
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

        #settings_img_data = Image.open("./img/settings_icon.png")
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
        
        self.main_page()

    def main_page(self):
        self.main_view = CTkScrollableFrame(
            master=self.parent.main_view_1, 
            fg_color="#d6d4ce",  
            width=1200, 
            height=1080, 
            corner_radius=0,
            orientation="vertical",
        )



        self.title_frame = CTkFrame(
            master=self.main_view, 
            fg_color="#442f7a",
            #bg_color=""
            height=400,
            width=1200,
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

        self.center_titles_frm = CTkFrame(
            self.title_frame,
            fg_color="transparent",
        )

        self.section_lbl = CTkLabel(
            master=self.title_frame,
            text="System Documents:",
            text_color='#fff',
            font=("Arial Bold", 14),
        )
        self.search_btn = CTkButton(
            self.center_titles_frm,
            text="Search",
            fg_color="transparent", 
            hover_color="#E44982",
            text_color="#fff",
            border_color="#fcba03",
            border_width=2,             
            font=("Arial Bold", 12),
            width=60,
        )
        self.search_ent = UndoableEntry(
            self.center_titles_frm,
            placeholder_text="Example: outside organization docs",
            width=250,
        )

        self.total_fields_frm = CTkFrame(
            self.main_view,
            fg_color="#fff",
        )
        self.inner_view = CTkScrollableFrame(
            master=self.total_fields_frm, 
            fg_color="#fff",  
            corner_radius=0,
            width=1200, 
            height=550, 
            orientation="horizontal",
        )
        vroad = Image.open("./img/vroad.png")
        vroad = CTkImage(
            dark_image=vroad,
            light_image=vroad,
            size=(600,180)
        )
        self.explain_8_2_frm = CTkFrame(
            self.main_view,
            fg_color="#000000",
        )
        self.footnote_8_1_lbl = CTkLabel(
            self.explain_8_2_frm,
            text="",
            image=vroad,
            compound="left",
        )
    def column(self):
        self.colm_frm = CTkFrame(
            self.inner_view,
            fg_color="#ffffff"
        )

        self.colm_title = CTkButton(
            self.colm_frm,
            text="Columns",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=20,
            height=50,
        )
        self.colm_1 = CTkButton(
            master=self.colm_frm,
            text="1",
            font=("Arial Bold", 18),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            text_color_disabled="#000000",
            state=DISABLED,
            width=50,
            height=50
        )

        self.colm_2 = CTkButton(
            master=self.colm_frm,
            text="2",
            font=("Arial Bold", 18),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            text_color_disabled="#000000",
            state=DISABLED,
            width=50,
            height=50
        )

        self.colm_3 = CTkButton(
            master=self.colm_frm,
            text="3",
            font=("Arial Bold", 18),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            text_color_disabled="#000000",
            state=DISABLED,
            width=50,
            height=50
        )
        self.colm_4 = CTkButton(
            master=self.colm_frm,
            text="4",
            font=("Arial Bold", 18),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            text_color_disabled="#000000",
            state=DISABLED,
            width=50,
            height=50
        )

        self.colm_5 = CTkButton(
            master=self.colm_frm,
            text="5",
            font=("Arial Bold", 18),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            text_color_disabled="#000000",
            state=DISABLED,
            width=50,
            height=50
        )

        self.colm_6 = CTkButton(
            master=self.colm_frm,
            text="6",
            font=("Arial Bold", 18),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            text_color_disabled="#000000",
            state=DISABLED,
            width=50,
            height=50
        )

        self.colm_7 = CTkButton(
            master=self.colm_frm,
            text="7",
            font=("Arial Bold", 18),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            text_color_disabled="#000000",
            state=DISABLED,
            width=50,
            height=50
        )

        self.colm_8 = CTkButton(
            master=self.colm_frm,
            text="new+",
            font=("Arial Bold", 18),
            fg_color="#ff0000",
            hover_color="#00d5ff",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            width=20,
            height=50
        )

    def column_conf(self):
        self.colm_frm.pack(
            anchor='e',
            side="right",
            #fill=Y,
            padx=(2,2),
            pady=5,
        )
        self.colm_title.grid(
            row=0,
            column=0,
            pady=(5,0)
        )
        self.colm_1.grid(
            row=1,
            column=0,
            pady=(5,0),
        )
        self.colm_2.grid(
            row=2,
            column=0,
            pady=(5,0),
        )
        self.colm_3.grid(
            row=3,
            column=0,
            pady=(5,0),
        )
        self.colm_4.grid(
            row=4,
            column=0,
            pady=(5,0),
        )
        self.colm_5.grid(
            row=5,
            column=0,
            pady=(5,0),
        )
        self.colm_6.grid(
            row=6,
            column=0,
            pady=(5,0),
        )
        self.colm_7.grid(
            row=7,
            column=0,
            pady=(5,0),
        )
        self.colm_8.grid(
            row=8,
            column=0,
            pady=(5,0),
        )

    def category(self):
        self.category_frm = CTkFrame(
            self.inner_view,
            fg_color="#fff"
        )

        self.cat_title_lbl = CTkComboBox(
            master=self.category_frm,
            values=["Category",],
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            #text_color_disabled="#000000",
            text_color="#000000",
            #state=DISABLED,
            width=130,
            height=50
        )
        self.cat_1 = CTkButton(
            master=self.category_frm,
            text="Outside of Org.",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=20,
            height=50
        )

        self.cat_2 = CTkButton(
            master=self.category_frm,
            text="inside of Org.",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            width=20,
            text_color_disabled="#000000",
            state=DISABLED,
            height=50,
        )

        self.cat_3 = CTkButton(
            master=self.category_frm,
            text="inside of Org.",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,

            width=20,
            height=50
        )

        self.cat_4 = CTkButton(
            master=self.category_frm,
            text="inside of Org.",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=20,
            height=50
        )

        self.cat_5 = CTkButton(
            master=self.category_frm,
            text="inside of Org.",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=20,
            height=50
        )

        self.cat_6 = CTkButton(
            master=self.category_frm,
            text="inside of Org.",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=20,
            height=50
        )

        self.cat_7 = CTkButton(
            master=self.category_frm,
            text="inside of Org.",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=20,
            height=50
        )

        self.cat_8 = CTkComboBox(
            master=self.category_frm,
            values=['Org.'],
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            justify="center",
            #hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color="#000000",
            width=120,
            height=50
        )
    
    def category_conf(self):
        self.category_frm.pack(
            anchor='e',
            side='right',
            padx=(2,0),
            pady=5,
        )
        self.cat_title_lbl.grid(
            row=0,
            column=0,
            pady=(5,0),
        )
        self.cat_1.grid(
            row=1,
            column=0,
            pady=(5,0)
        )
        self.cat_2.grid(
            row=2,
            column=0,
            pady=(5,0)
        )
        self.cat_3.grid(
            row=3,
            column=0,
            pady=(5,0)
        )
        self.cat_4.grid(
            row=4,
            column=0,
            pady=(5,0)
        )
        self.cat_5.grid(
            row=5,
            column=0,
            pady=(5,0)
        )
        self.cat_6.grid(
            row=6,
            column=0,
            pady=(5,0)
        )
        self.cat_7.grid(
            row=7,
            column=0,
            pady=(5,0)
        )
        self.cat_8.grid(
            row=8,
            column=0,
            pady=(5,0)
        )

    def title(self):
        self.title_frm = CTkFrame(
            self.inner_view,
            fg_color='#fff',
        )

        self.title_btn = CTkComboBox(
            self.title_frm,
            values=["Title",],
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color="#000000",
            width=300,
            height=50
        )

        self.title_1_btn = CTkButton(
            master=self.title_frm,
            text="invite to co-operate on poll",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=300,
            height=50
        )

        self.title_2_btn = CTkButton(
            master=self.title_frm,
            text="editting methods",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=300,
            height=50
        )

        self.title_3_btn = CTkButton(
            master=self.title_frm,
            text="editting methods",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=300,
            height=50
        )

        self.title_4_btn = CTkButton(
            master=self.title_frm,
            text="Instructions of Turning",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=300,
            height=50
        )

        self.title_5_btn = CTkButton(
            master=self.title_frm,
            text="Request for for dismissal",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=300,
            height=50
        )

        self.title_6_btn = CTkButton(
            master=self.title_frm,
            text="Request for for dismissal",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=300,
            height=50
        )

        self.title_7_btn = CTkButton(
            master=self.title_frm,
            text="Orders letter writing",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=300,
            height=50
        )

        self.title_8_btn = CTkComboBox(
            self.title_frm,
            values=["Title",],
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            border_color="#000000",
            text_color="#000000",
            border_width=2,
            corner_radius=10,
            width=300,
            height=50
        )

    def title_conf(self):
        self.title_frm.pack(
            anchor='e',
            side='right',
            padx=(2,0),
            pady=5,
        )
        self.title_btn.grid(
            row=0,
            column=0,
            pady=(5,0)
        )
        self.title_1_btn.grid(
            row=1,
            column=0,
            pady=(5,0)
        )
        self.title_2_btn.grid(
            row=2,
            column=0,
            pady=(5,0)
        )
        self.title_3_btn.grid(
            row=3,
            column=0,
            pady=(5,0)
        )
        self.title_4_btn.grid(
            row=4,
            column=0,
            pady=(5,0)
        )
        self.title_5_btn.grid(
            row=5,
            column=0,
            pady=(5,0)
        )
        self.title_6_btn.grid(
            row=6,
            column=0,
            pady=(5,0)
        )
        self.title_7_btn.grid(
            row=7,
            column=0,
            pady=(5,0)
        )

        self.title_8_btn.grid(
            row=8,
            column=0,
            pady=(5,0),
        )

    def groups(self):
        self.group_frm = CTkFrame(
            self.inner_view,
            fg_color="#fff",
        )

        self.group_btn = CTkComboBox(
            master=self.group_frm,
            #text="Instruction",
            values=['Groups'],
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            border_color="#000000",
            text_color="#000000",
            border_width=2,
            corner_radius=10,
            width=100,
            height=50
        )
        self.group_1_btn = CTkButton(
            master=self.group_frm,
            text="Poster",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=100,
            height=50
        )

        self.group_2_btn = CTkButton(
            master=self.group_frm,
            text="Poster",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=100,
            height=50
        )

        self.group_3_btn = CTkButton(
            master=self.group_frm,
            text="Instruction",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=100,
            height=50
        )

        self.group_4_btn = CTkButton(
            master=self.group_frm,
            text="Instruction",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=100,
            height=50
        )

        self.group_5_btn = CTkButton(
            master=self.group_frm,
            text="Instruction",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=100,
            height=50
        )

        self.group_6_btn = CTkButton(
            master=self.group_frm,
            text="Instruction",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=100,
            height=50
        )
        self.group_7_btn = CTkButton(
            master=self.group_frm,
            text="Instruction",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=100,
            height=50
        )

        self.group_8_btn = CTkComboBox(
            master=self.group_frm,
            #text="Instruction",
            values=['Groups'],
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color="#000000",
            width=100,
            height=50
        )


    def groups_conf(self):
        self.group_frm.pack(
            anchor='e',
            side='right',
            padx=(2,0),
            pady=5,
        )
        self.group_btn.grid(
            row=0,
            column=0,
            pady=(5,0),
        )

        self.group_1_btn.grid(
            row=1,
            column=0,
            pady=(5,0)
        )
        self.group_2_btn.grid(
            row=2,
            column=0,
            pady=(5,0)
        )
        self.group_3_btn.grid(
            row=3,
            column=0,
            pady=(5,0)
        )
        self.group_4_btn.grid(
            row=4,
            column=0,
            pady=(5,0)
        )
        self.group_5_btn.grid(
            row=5,
            column=0,
            pady=(5,0)
        )
        self.group_6_btn.grid(
            row=6,
            column=0,
            pady=(5,0)
        )
        self.group_7_btn.grid(
            row=7,
            column=0,
            pady=(5,0)
        )
        self.group_8_btn.grid(
            row=8,
            column=0,
            pady=(5,0)
        )

    def rearangement(self):
        self.rearangement_frm = CTkFrame(
            self.inner_view,
            fg_color="#fff",
        )
        self.arng_cmb = CTkComboBox(
            master=self.rearangement_frm,
            values=["01",],
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color="#000000",

            width=100,
            height=50
        )

        self.arng_1 = CTkButton(
            master=self.rearangement_frm,
            text="01",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=50,
            height=50
        )
        self.arng_2 = CTkButton(
            master=self.rearangement_frm,
            text="01",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=50,
            height=50
        )
        self.arng_3 = CTkButton(
            master=self.rearangement_frm,
            text="01",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=50,
            height=50
        )
        self.arng_4 = CTkButton(
            master=self.rearangement_frm,
            text="01",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=50,
            height=50
        )
        self.arng_5 = CTkButton(
            master=self.rearangement_frm,
            text="01",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=50,
            height=50
        )
        self.arng_6 = CTkButton(
            master=self.rearangement_frm,
            text="01",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=50,
            height=50
        )
        self.arng_7 = CTkButton(
            master=self.rearangement_frm,
            text="01",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=50,
            height=50
        )
        self.arng_8 = CTkButton(
            master=self.rearangement_frm,
            text="",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=50,
            height=50
        )

    def rearangment_conf(self):
        self.rearangement_frm.pack(
            anchor='e',
            side="right",
            padx=2,
            pady=(5,0)
        )
        self.arng_cmb.grid(
            row=0,
            column=0,
            pady=(5,0)
        )
        self.arng_1.grid(
            row=1,
            column=0,
            pady=(5,0)
        )
        self.arng_2.grid(
            row=2,
            column=0,
            pady=(5,0)
        )
        self.arng_3.grid(
            row=3,
            column=0,
            pady=(5,0)
        )
        self.arng_4.grid(
            row=4,
            column=0,
            pady=(5,0)
        )
        self.arng_5.grid(
            row=5,
            column=0,
            pady=(5,0)
        )
        self.arng_6.grid(
            row=6,
            column=0,
            pady=(5,0)
        )
        self.arng_7.grid(
            row=7,
            column=0,
            pady=(5,0)
        )
        self.arng_8.grid(
            row=8,
            column=0,
            pady=(5,0)
        )

    def code_part(self):
        self.code_frm = CTkFrame(
            self.inner_view,
            fg_color="#fff",
        )
        self.code_cmb = CTkComboBox(
            master=self.code_frm,
            values=["PO-01",],
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color="#000000",
            width=100,
            height=50
        )
        self.code_1 = CTkButton(
            master=self.code_frm,
            text="PO-01",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=100,
            height=50
        )
        self.code_2 = CTkButton(
            master=self.code_frm,
            text="PR-01",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=100,
            height=50
        )
        self.code_3 = CTkButton(
            master=self.code_frm,
            text="PR-01",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=100,
            height=50
        )
        self.code_4 = CTkButton(
            master=self.code_frm,
            text="WI-01",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=100,
            height=50
        )
        self.code_5 = CTkButton(
            master=self.code_frm,
            text="FR-01",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=100,
            height=50
        )
        self.code_6 = CTkButton(
            master=self.code_frm,
            text="FR-01",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=100,
            height=50
        )
        self.code_7 = CTkButton(
            master=self.code_frm,
            text="DRAFT-01",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=100,
            height=50
        )
        self.code_8 = CTkButton(
            master=self.code_frm,
            text="",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            border_width=2,
            corner_radius=10,
            text_color_disabled="#000000",
            state=DISABLED,
            width=100,
            height=50
        )

    def code_conf(self):
        self.code_frm.pack(
            anchor='e',
            side='right',
            padx=2,
            pady=(5,0)
        )
        self.code_cmb.grid(
            row=0,
            column=0,
            pady=(5,0),
        )
        self.code_1.grid(
            row=1,
            column=0,
            pady=(5,0)
        )
        self.code_2.grid(
            row=2,
            column=0,
            pady=(5,0)
        )
        self.code_3.grid(
            row=3,
            column=0,
            pady=(5,0)
        )
        self.code_4.grid(
            row=4,
            column=0,
            pady=(5,0)
        )
        self.code_5.grid(
            row=5,
            column=0,
            pady=(5,0)
        )
        self.code_6.grid(
            row=6,
            column=0,
            pady=(5,0)
        )
        self.code_7.grid(
            row=7,
            column=0,
            pady=(5,0)
        )
        self.code_8.grid(
            row=8,
            column=0,
            pady=(5,0)
        )

    def accountant(self):
        self.accountant_frm_1 = CTkFrame(
            self.inner_view,
            fg_color="#fff",
        )
        self.accountant_cmb = CTkComboBox(
            self.accountant_frm_1,
            values=["Accountant",],
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            border_color="#000000",
            text_color="#000000",
            border_width=2,
            corner_radius=10,
            width=100,
            height=50
        )

        self.accountant_frm_1_1 = CTkFrame(
            self.accountant_frm_1,
            width=130,
            height=50,
            fg_color="#fff",
        )

        self.org_post_btn_2_1 = CTkButton(
            master=self.accountant_frm_1_1,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_2_1 = CTkButton(
            master=self.accountant_frm_1_1,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.accountant_frm_1_2 = CTkFrame(
            self.accountant_frm_1,
            width=130,
            height=50,
            fg_color="#fff",
        )

        self.org_post_btn_2_2 = CTkButton(
            master=self.accountant_frm_1_2,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_2_2 = CTkButton(
            master=self.accountant_frm_1_2,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.accountant_frm_1_3 = CTkFrame(
            self.accountant_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_2_3 = CTkButton(
            master=self.accountant_frm_1_3,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_2_3 = CTkButton(
            master=self.accountant_frm_1_3,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.accountant_frm_1_4 = CTkFrame(
            self.accountant_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_2_4 = CTkButton(
            master=self.accountant_frm_1_4,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_2_4 = CTkButton(
            master=self.accountant_frm_1_4,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.accountant_frm_1_5 = CTkFrame(
            self.accountant_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_2_5 = CTkButton(
            master=self.accountant_frm_1_5,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_2_5 = CTkButton(
            master=self.accountant_frm_1_5,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.accountant_frm_1_6 = CTkFrame(
            self.accountant_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_2_6 = CTkButton(
            master=self.accountant_frm_1_6,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_2_6 = CTkButton(
            master=self.accountant_frm_1_6,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )

        self.show_new_btn = CTkButton(
            master=self.accountant_frm_1,
            text="Show",
            font=("Arial Bold", 14),
            fg_color="#ff0000",
            hover_color="#E44982",
            border_color="#000000",
            text_color="#ffffff",
            border_width=2,
            width=110,
            height=50
        )
        self.create_new_btn = CTkButton(
            master=self.accountant_frm_1,
            text="Create",
            font=("Arial Bold", 14),
            fg_color="#ff0000",
            hover_color="#E44982",
            border_color="#000000",
            text_color="#ffffff",
            border_width=2,
            width=110,
            height=50
        )
    def accountant_conf(self):
        self.accountant_frm_1.pack(
            anchor='e',
            side="right",
            padx=2,
            pady=(5,0)
        )
        self.accountant_cmb.grid(
            row=0,
            column=0,
            pady=(5,0),
        )
        self.accountant_frm_1_1.grid(
            row=1,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_2_1.pack(
            side='top',
        )
        self.sup_post_btn_2_1.pack(
            side='top'
        )

        self.accountant_frm_1_2.grid(
            row=2,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_2_2.pack(
            side='top',
        )
        self.sup_post_btn_2_2.pack(
            side='top'
        )

        self.accountant_frm_1_3.grid(
            row=3,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_2_3.pack(
            side='top',
        )
        self.sup_post_btn_2_3.pack(
            side='top'
        )

        self.accountant_frm_1_4.grid(
            row=4,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_2_4.pack(
            side='top',
        )
        self.sup_post_btn_2_4.pack(
            side='top'
        )

        self.accountant_frm_1_5.grid(
            row=5,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_2_5.pack(
            side='top',
        )
        self.sup_post_btn_2_5.pack(
            side='top'
        )
        
        self.accountant_frm_1_6.grid(
            row=6,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_2_6.pack(
            side='top',
        )
        self.sup_post_btn_2_6.pack(
            side='top'
        )
        
        self.show_new_btn.grid(
            row=7,
            column=0,
            pady=(5,0),
        )
        self.create_new_btn.grid(
            row=8,
            column=0,
            pady=(5,0),
        )

    def answerer(self):
        self.ans_frm_1 = CTkFrame(
            self.inner_view,
            fg_color="#fff",
        )
        self.ans_cmb = CTkComboBox(
            self.ans_frm_1,
            values=["Questioner",],
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            border_color="#000000",
            text_color="#000000",
            border_width=2,
            corner_radius=10,
            width=100,
            height=50
        )

        self.ans_frm_1_1 = CTkFrame(
            self.ans_frm_1,
            width=130,
            height=50,
            fg_color="#fff",
        )

        self.org_post_btn_3_1 = CTkButton(
            master=self.ans_frm_1_1,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_3_1 = CTkButton(
            master=self.ans_frm_1_1,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.ans_frm_1_2 = CTkFrame(
            self.ans_frm_1,
            width=130,
            height=50,
            fg_color="#fff",
        )

        self.org_post_btn_3_2 = CTkButton(
            master=self.ans_frm_1_2,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_3_2 = CTkButton(
            master=self.ans_frm_1_2,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.ans_frm_1_3 = CTkFrame(
            self.ans_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_3_3 = CTkButton(
            master=self.ans_frm_1_3,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_3_3 = CTkButton(
            master=self.ans_frm_1_3,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.ans_frm_1_4 = CTkFrame(
            self.ans_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_3_4 = CTkButton(
            master=self.ans_frm_1_4,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_3_4 = CTkButton(
            master=self.ans_frm_1_4,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.ans_frm_1_5 = CTkFrame(
            self.ans_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_3_5 = CTkButton(
            master=self.ans_frm_1_5,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_3_5 = CTkButton(
            master=self.ans_frm_1_5,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.ans_frm_1_6 = CTkFrame(
            self.ans_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_3_6 = CTkButton(
            master=self.ans_frm_1_6,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_3_6 = CTkButton(
            master=self.ans_frm_1_6,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )

        self.show_new_btn_2 = CTkButton(
            master=self.ans_frm_1,
            text="",
            font=("Arial Bold", 14),
            fg_color="#fff",
            hover_color="#fff",
            border_color="#fff",
            text_color="#ffffff",
            border_width=2,
            width=110,
            height=50
        )

        self.create_new_btn_2 = CTkButton(
            master=self.ans_frm_1,
            text="",
            font=("Arial Bold", 14),
            fg_color="#fff",
            hover_color="#fff",
            border_color="#fff",
            text_color="#ffffff",
            border_width=2,
            width=110,
            height=50
        )
    def answerer_conf(self):
        self.ans_frm_1.pack(
            anchor='e',
            side="right",
            padx=2,
            pady=(5,0)
        )
        self.ans_cmb.grid(
            row=0,
            column=0,
            pady=(5,0),
        )
        self.ans_frm_1_1.grid(
            row=1,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_3_1.pack(
            side='top',
        )
        self.sup_post_btn_3_1.pack(
            side='top'
        )

        self.ans_frm_1_2.grid(
            row=2,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_3_2.pack(
            side='top',
        )
        self.sup_post_btn_3_2.pack(
            side='top'
        )

        self.ans_frm_1_3.grid(
            row=3,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_3_3.pack(
            side='top',
        )
        self.sup_post_btn_3_3.pack(
            side='top'
        )

        self.ans_frm_1_4.grid(
            row=4,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_3_4.pack(
            side='top',
        )
        self.sup_post_btn_3_4.pack(
            side='top'
        )

        self.ans_frm_1_5.grid(
            row=5,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_3_5.pack(
            side='top',
        )
        self.sup_post_btn_3_5.pack(
            side='top'
        )
        
        self.ans_frm_1_6.grid(
            row=6,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_3_6.pack(
            side='top',
        )
        self.sup_post_btn_3_6.pack(
            side='top'
        )
        
        self.show_new_btn_2.grid(
            row=7,
            column=0,
            pady=(5,0),
        )
        self.create_new_btn_2.grid(
            row=8,
            column=0,
            pady=(5,0),
        )

    def responder(self):
        self.resp_frm_1 = CTkFrame(
            self.inner_view,
            fg_color="#fff",
        )
        self.resp_cmb = CTkComboBox(
            self.resp_frm_1,
            values=["Responder",],
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            border_color="#000000",
            text_color="#000000",
            border_width=2,
            corner_radius=10,
            width=100,
            height=50,
        )

        self.resp_frm_1_1 = CTkFrame(
            self.resp_frm_1,
            width=130,
            height=50,
            fg_color="#fff",
        )

        self.org_post_btn_4_1 = CTkButton(
            master=self.resp_frm_1_1,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_4_1 = CTkButton(
            master=self.resp_frm_1_1,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.resp_frm_1_2 = CTkFrame(
            self.resp_frm_1,
            width=130,
            height=50,
            fg_color="#fff",
        )

        self.org_post_btn_4_2 = CTkButton(
            master=self.resp_frm_1_2,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_4_2 = CTkButton(
            master=self.resp_frm_1_2,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.resp_frm_1_3 = CTkFrame(
            self.resp_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_4_3 = CTkButton(
            master=self.resp_frm_1_3,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_4_3 = CTkButton(
            master=self.resp_frm_1_3,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.resp_frm_1_4 = CTkFrame(
            self.resp_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_4_4 = CTkButton(
            master=self.resp_frm_1_4,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_4_4 = CTkButton(
            master=self.resp_frm_1_4,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.resp_frm_1_5 = CTkFrame(
            self.resp_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_4_5 = CTkButton(
            master=self.resp_frm_1_5,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_4_5 = CTkButton(
            master=self.resp_frm_1_5,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.resp_frm_1_6 = CTkFrame(
            self.resp_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_4_6 = CTkButton(
            master=self.resp_frm_1_6,
            text="Organazation Post",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_4_6 = CTkButton(
            master=self.resp_frm_1_6,
            text="SuperVisor",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )

        self.show_new_btn_3 = CTkButton(
            master=self.resp_frm_1,
            text="",
            font=("Arial Bold", 14),
            fg_color="#fff",
            hover_color="#fff",
            border_color="#fff",
            text_color="#ffffff",
            border_width=2,
            width=110,
            height=50
        )

        self.create_new_btn_3 = CTkButton(
            master=self.resp_frm_1,
            text="",
            font=("Arial Bold", 14),
            fg_color="#fff",
            hover_color="#fff",
            border_color="#fff",
            text_color="#ffffff",
            border_width=2,
            width=110,
            height=50
        )
    def responder_conf(self):
        self.resp_frm_1.pack(
            anchor='e',
            side="right",
            padx=2,
            pady=(5,0)
        )
        self.resp_cmb.grid(
            row=0,
            column=0,
            pady=(5,0),
        )
        self.resp_frm_1_1.grid(
            row=1,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_4_1.pack(
            side='top',
        )
        self.sup_post_btn_4_1.pack(
            side='top'
        )

        self.resp_frm_1_2.grid(
            row=2,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_4_2.pack(
            side='top',
        )
        self.sup_post_btn_4_2.pack(
            side='top'
        )

        self.resp_frm_1_3.grid(
            row=3,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_4_3.pack(
            side='top',
        )
        self.sup_post_btn_4_3.pack(
            side='top'
        )

        self.resp_frm_1_4.grid(
            row=4,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_4_4.pack(
            side='top',
        )
        self.sup_post_btn_4_4.pack(
            side='top'
        )

        self.resp_frm_1_5.grid(
            row=5,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_4_5.pack(
            side='top',
        )
        self.sup_post_btn_4_5.pack(
            side='top'
        )
        
        self.resp_frm_1_6.grid(
            row=6,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_4_6.pack(
            side='top',
        )
        self.sup_post_btn_4_6.pack(
            side='top'
        )
        
        self.show_new_btn_3.grid(
            row=7,
            column=0,
            pady=(5,0),
        )
        self.create_new_btn_3.grid(
            row=8,
            column=0,
            pady=(5,0),
        )

    def creater(self):
        self.creater_frm_1 = CTkFrame(
            self.inner_view,
            fg_color="#fff",
        )
        self.creater_cmb = CTkComboBox(
            self.creater_frm_1,
            values=["Creater",],
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            border_color="#000000",
            text_color="#000000",
            border_width=2,
            corner_radius=10,
            width=100,
            height=50,
        )

        self.creater_frm_1_1 = CTkFrame(
            self.creater_frm_1,
            width=130,
            height=50,
            fg_color="#fff",
        )

        self.org_post_btn_5_1 = CTkButton(
            master=self.creater_frm_1_1,
            text="Name",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_5_1 = CTkButton(
            master=self.creater_frm_1_1,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.creater_frm_1_2 = CTkFrame(
            self.creater_frm_1,
            width=130,
            height=50,
            fg_color="#fff",
        )

        self.org_post_btn_5_2 = CTkButton(
            master=self.creater_frm_1_2,
            text="Name",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_5_2 = CTkButton(
            master=self.creater_frm_1_2,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.creater_frm_1_3 = CTkFrame(
            self.creater_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_5_3 = CTkButton(
            master=self.creater_frm_1_3,
            text="Name",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_5_3 = CTkButton(
            master=self.creater_frm_1_3,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.creater_frm_1_4 = CTkFrame(
            self.creater_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_5_4 = CTkButton(
            master=self.creater_frm_1_4,
            text="ٔName",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_5_4 = CTkButton(
            master=self.creater_frm_1_4,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.creater_frm_1_5 = CTkFrame(
            self.creater_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_5_5 = CTkButton(
            master=self.creater_frm_1_5,
            text="ٔName",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_5_5 = CTkButton(
            master=self.creater_frm_1_5,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.creater_frm_1_6 = CTkFrame(
            self.creater_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_5_6 = CTkButton(
            master=self.creater_frm_1_6,
            text="ٔName",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_5_6 = CTkButton(
            master=self.creater_frm_1_6,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )

        self.show_new_btn_4 = CTkButton(
            master=self.creater_frm_1,
            text="",
            font=("Arial Bold", 14),
            fg_color="#fff",
            hover_color="#fff",
            border_color="#fff",
            text_color="#ffffff",
            border_width=2,
            width=110,
            height=50
        )

        self.create_new_btn_4 = CTkButton(
            master=self.creater_frm_1,
            text="",
            font=("Arial Bold", 14),
            fg_color="#fff",
            hover_color="#fff",
            border_color="#fff",
            text_color="#ffffff",
            border_width=2,
            width=110,
            height=50
        )
    def creater_conf(self):
        self.creater_frm_1.pack(
            anchor='e',
            side="right",
            padx=2,
            pady=(5,0)
        )
        self.creater_cmb.grid(
            row=0,
            column=0,
            pady=(5,0),
        )
        self.creater_frm_1_1.grid(
            row=1,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_5_1.pack(
            side='top',
        )
        self.sup_post_btn_5_1.pack(
            side='top'
        )

        self.creater_frm_1_2.grid(
            row=2,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_5_2.pack(
            side='top',
        )
        self.sup_post_btn_5_2.pack(
            side='top'
        )

        self.creater_frm_1_3.grid(
            row=3,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_5_3.pack(
            side='top',
        )
        self.sup_post_btn_5_3.pack(
            side='top'
        )

        self.creater_frm_1_4.grid(
            row=4,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_5_4.pack(
            side='top',
        )
        self.sup_post_btn_5_4.pack(
            side='top'
        )

        self.creater_frm_1_5.grid(
            row=5,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_5_5.pack(
            side='top',
        )
        self.sup_post_btn_5_5.pack(
            side='top'
        )
        
        self.creater_frm_1_6.grid(
            row=6,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_5_6.pack(
            side='top',
        )
        self.sup_post_btn_5_6.pack(
            side='top'
        )
        
        self.show_new_btn_4.grid(
            row=7,
            column=0,
            pady=(5,0),
        )
        self.create_new_btn_4.grid(
            row=8,
            column=0,
            pady=(5,0),
        )

    def confirm(self):
        self.confirm_frm_1 = CTkFrame(
            self.inner_view,
            fg_color="#fff",
        )
        self.confirm_cmb = CTkComboBox(
            self.confirm_frm_1,
            values=["Confirm",],
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            border_color="#000000",
            text_color="#000000",
            border_width=2,
            corner_radius=10,
            width=100,
            height=50,
        )

        self.confirm_frm_1_1 = CTkFrame(
            self.confirm_frm_1,
            width=130,
            height=50,
            fg_color="#fff",
        )

        self.org_post_btn_6_1 = CTkButton(
            master=self.confirm_frm_1_1,
            text="Name",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_6_1 = CTkButton(
            master=self.confirm_frm_1_1,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.confirm_frm_1_2 = CTkFrame(
            self.confirm_frm_1,
            width=130,
            height=50,
            fg_color="#fff",
        )

        self.org_post_btn_6_2 = CTkButton(
            master=self.confirm_frm_1_2,
            text="Name",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_6_2 = CTkButton(
            master=self.confirm_frm_1_2,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.confirm_frm_1_3 = CTkFrame(
            self.confirm_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_6_3 = CTkButton(
            master=self.confirm_frm_1_3,
            text="Name",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_6_3 = CTkButton(
            master=self.confirm_frm_1_3,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.confirm_frm_1_4 = CTkFrame(
            self.confirm_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_6_4 = CTkButton(
            master=self.confirm_frm_1_4,
            text="ٔName",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_6_4 = CTkButton(
            master=self.confirm_frm_1_4,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.confirm_frm_1_5 = CTkFrame(
            self.confirm_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_6_5 = CTkButton(
            master=self.confirm_frm_1_5,
            text="ٔName",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_6_5 = CTkButton(
            master=self.confirm_frm_1_5,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.confirm_frm_1_6 = CTkFrame(
            self.confirm_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_6_6 = CTkButton(
            master=self.confirm_frm_1_6,
            text="ٔName",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_6_6 = CTkButton(
            master=self.confirm_frm_1_6,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )

        self.show_new_btn_6 = CTkButton(
            master=self.confirm_frm_1,
            text="",
            font=("Arial Bold", 14),
            fg_color="#fff",
            hover_color="#fff",
            border_color="#fff",
            text_color="#ffffff",
            border_width=2,
            width=110,
            height=50
        )

        self.create_new_btn_6 = CTkButton(
            master=self.confirm_frm_1,
            text="",
            font=("Arial Bold", 14),
            fg_color="#fff",
            hover_color="#fff",
            border_color="#fff",
            text_color="#ffffff",
            border_width=2,
            width=110,
            height=50
        )
    def confirm_conf(self):
        self.confirm_frm_1.pack(
            anchor='e',
            side="right",
            padx=2,
            pady=(5,0)
        )
        self.confirm_cmb.grid(
            row=0,
            column=0,
            pady=(5,0),
        )
        self.confirm_frm_1_1.grid(
            row=1,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_6_1.pack(
            side='top',
        )
        self.sup_post_btn_6_1.pack(
            side='top'
        )

        self.confirm_frm_1_2.grid(
            row=2,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_6_2.pack(
            side='top',
        )
        self.sup_post_btn_6_2.pack(
            side='top'
        )

        self.confirm_frm_1_3.grid(
            row=3,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_6_3.pack(
            side='top',
        )
        self.sup_post_btn_6_3.pack(
            side='top'
        )

        self.confirm_frm_1_4.grid(
            row=4,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_6_4.pack(
            side='top',
        )
        self.sup_post_btn_6_4.pack(
            side='top'
        )

        self.confirm_frm_1_5.grid(
            row=5,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_6_5.pack(
            side='top',
        )
        self.sup_post_btn_6_5.pack(
            side='top'
        )
        
        self.confirm_frm_1_6.grid(
            row=6,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_6_6.pack(
            side='top',
        )
        self.sup_post_btn_6_6.pack(
            side='top'
        )
        
        self.show_new_btn_6.grid(
            row=7,
            column=0,
            pady=(5,0),
        )
        self.create_new_btn_6.grid(
            row=8,
            column=0,
            pady=(5,0),
        )

    def approve(self):
        self.approve_frm_1 = CTkFrame(
            self.inner_view,
            fg_color="#fff",
        )
        self.approve_cmb = CTkComboBox(
            self.approve_frm_1,
            values=["Approve",],
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            border_color="#000000",
            text_color="#000000",
            border_width=2,
            corner_radius=10,
            width=100,
            height=50,
        )

        self.approve_frm_1_1 = CTkFrame(
            self.approve_frm_1,
            width=130,
            height=50,
            fg_color="#fff",
        )

        self.org_post_btn_7_1 = CTkButton(
            master=self.approve_frm_1_1,
            text="Name",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_7_1 = CTkButton(
            master=self.approve_frm_1_1,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.approve_frm_1_2 = CTkFrame(
            self.approve_frm_1,
            width=130,
            height=50,
            fg_color="#fff",
        )

        self.org_post_btn_7_2 = CTkButton(
            master=self.approve_frm_1_2,
            text="Name",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_7_2 = CTkButton(
            master=self.approve_frm_1_2,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.approve_frm_1_3 = CTkFrame(
            self.approve_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_7_3 = CTkButton(
            master=self.approve_frm_1_3,
            text="Name",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_7_3 = CTkButton(
            master=self.approve_frm_1_3,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.approve_frm_1_4 = CTkFrame(
            self.approve_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_7_4 = CTkButton(
            master=self.approve_frm_1_4,
            text="ٔName",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_7_4 = CTkButton(
            master=self.approve_frm_1_4,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.approve_frm_1_5 = CTkFrame(
            self.approve_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_7_5 = CTkButton(
            master=self.approve_frm_1_5,
            text="ٔName",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_7_5 = CTkButton(
            master=self.approve_frm_1_5,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.approve_frm_1_6 = CTkFrame(
            self.approve_frm_1,
            width=130,
            height=110,
            fg_color="#fff",
        )

        self.org_post_btn_7_6 = CTkButton(
            master=self.approve_frm_1_6,
            text="ٔName",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )
        self.sup_post_btn_7_6 = CTkButton(
            master=self.approve_frm_1_6,
            text="Date",
            font=("Arial Bold", 9),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#000000",
            state=DISABLED,
            border_width=2,
            width=110,
            height=25
        )

        self.show_new_btn_7 = CTkButton(
            master=self.approve_frm_1,
            text="",
            font=("Arial Bold", 14),
            fg_color="#fff",
            hover_color="#fff",
            border_color="#fff",
            text_color="#ffffff",
            border_width=2,
            width=110,
            height=50
        )

        self.create_new_btn_7 = CTkButton(
            master=self.approve_frm_1,
            text="",
            font=("Arial Bold", 14),
            fg_color="#fff",
            hover_color="#fff",
            border_color="#fff",
            text_color="#ffffff",
            border_width=2,
            width=110,
            height=50
        )
    def approve_conf(self):
        self.approve_frm_1.pack(
            anchor='e',
            side="right",
            padx=2,
            pady=(5,0)
        )
        self.approve_cmb.grid(
            row=0,
            column=0,
            pady=(5,0),
        )
        self.approve_frm_1_1.grid(
            row=1,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_7_1.pack(
            side='top',
        )
        self.sup_post_btn_7_1.pack(
            side='top'
        )

        self.approve_frm_1_2.grid(
            row=2,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_7_2.pack(
            side='top',
        )
        self.sup_post_btn_7_2.pack(
            side='top'
        )

        self.approve_frm_1_3.grid(
            row=3,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_7_3.pack(
            side='top',
        )
        self.sup_post_btn_7_3.pack(
            side='top'
        )

        self.approve_frm_1_4.grid(
            row=4,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_7_4.pack(
            side='top',
        )
        self.sup_post_btn_7_4.pack(
            side='top'
        )

        self.approve_frm_1_5.grid(
            row=5,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_7_5.pack(
            side='top',
        )
        self.sup_post_btn_7_5.pack(
            side='top'
        )
        
        self.approve_frm_1_6.grid(
            row=6,
            column=0,
            pady=(5,0),
        )
        self.org_post_btn_7_6.pack(
            side='top',
        )
        self.sup_post_btn_7_6.pack(
            side='top'
        )
        
        self.show_new_btn_7.grid(
            row=7,
            column=0,
            pady=(5,0),
        )
        self.create_new_btn_7.grid(
            row=8,
            column=0,
            pady=(5,0),
        )

    def status(self):
        self.status_frm_1 = CTkFrame(
            self.inner_view,
            fg_color="#fff",
        )
        self.status_cmb = CTkComboBox(
            self.status_frm_1,
            values=["Status",],
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            border_color="#000000",
            text_color="#000000",
            border_width=2,
            corner_radius=10,
            width=100,
            height=50,
        )
        self.status_1_btn = CTkButton(
            self.status_frm_1,
            text="Valid",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#00ff26",
            state=DISABLED,
            border_width=2,
            width=100,
            height=50,
        )
        self.status_2_btn = CTkButton(
            self.status_frm_1,
            text="Invalid",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#ff002f",
            state=DISABLED,
            border_width=2,
            width=100,
            height=50,
        )
        self.status_3_btn = CTkButton(
            self.status_frm_1,
            text="Invalid",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#ff002f",
            state=DISABLED,
            border_width=2,
            width=100,
            height=50,
        )
        self.status_4_btn = CTkButton(
            self.status_frm_1,
            text="Invalid",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#ff002f",
            state=DISABLED,
            border_width=2,
            width=100,
            height=50,
        )
        self.status_5_btn = CTkButton(
            self.status_frm_1,
            text="Invalid",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#ff002f",
            state=DISABLED,
            border_width=2,
            width=100,
            height=50,
        )
        self.status_6_btn = CTkButton(
            self.status_frm_1,
            text="Valid",
            font=("Arial Bold", 12),
            fg_color="#ffffff",
            hover_color="#E44982",
            border_color="#000000",
            text_color_disabled="#00ff26",
            state=DISABLED,
            border_width=2,
            width=100,
            height=50,
        )
        self.show_new_btn_8 = CTkButton(
            master=self.status_frm_1,
            text="",
            font=("Arial Bold", 14),
            fg_color="#fff",
            hover_color="#fff",
            border_color="#fff",
            text_color="#ffffff",
            border_width=2,
            width=100,
            height=50
        )

        self.create_new_btn_8 = CTkButton(
            master=self.status_frm_1,
            text="",
            font=("Arial Bold", 14),
            fg_color="#fff",
            hover_color="#fff",
            border_color="#fff",
            text_color="#ffffff",
            border_width=2,
            width=100,
            height=50
        )
    def status_conf(self):


        self.status_frm_1.pack(
            anchor='e',
            side="right",
            padx=2,
            pady=(5,0)
        )
        self.status_cmb.grid(
            row=0,
            column=0,
            pady=(5,0),
        )
        self.status_1_btn.grid(
            row=1,
            column=0,
            pady=(5,0),
        )
        self.status_2_btn.grid(
            row=2,
            column=0,
            pady=(5,0),
        )
        self.status_3_btn.grid(
            row=3,
            column=0,
            pady=(5,0),
        )
        self.status_4_btn.grid(
            row=4,
            column=0,
            pady=(5,0),
        )
        self.status_5_btn.grid(
            row=5,
            column=0,
            pady=(5,0),
        )
        self.status_6_btn.grid(
            row=6,
            column=0,
            pady=(5,0),
        )
        #self.status_7_btn.grid(
        #    row=7,
        #    column=0,
        #    pady=(5,0),
        #)
        self.show_new_btn_8.grid(
            row=7,
            column=0,
            pady=(5,0)
        )
        self.create_new_btn_8.grid(
            row=8,
            column=0,
            pady=(5,0)
        )

    def last(self):
        self.last_frm_1 = CTkFrame(
            self.inner_view,
            fg_color="#fff",
        )
        self.last_cmb = CTkButton(
            self.last_frm_1,
            text="Print List",
            font=("Arial Bold", 12),
            fg_color="#ff002f",
            border_color="#000000",
            text_color="#000000",
            border_width=2,
            corner_radius=10,
            width=100,
            height=50,
        )
        self.last_1_btn = CTkButton(
            self.last_frm_1,
            text="Show",
            font=("Arial Bold", 12),
            fg_color="#ff002f",
            hover_color="#E44982",
            border_color="#000000",
            text_color="#000000",
            corner_radius=10,
            text_color_disabled="#00ff26",
            border_width=2,
            width=100,
            height=50,
        )
        self.last_2_btn = CTkButton(
            self.last_frm_1,
            text="Show",
            font=("Arial Bold", 12),
            fg_color="#ff002f",
            hover_color="#E44982",
            border_color="#000000",
            text_color="#000000",
            corner_radius=10,
            text_color_disabled="#ff002f",
            border_width=2,
            width=100,
            height=50,
        )
        self.last_3_btn = CTkButton(
            self.last_frm_1,
            text="Show",
            font=("Arial Bold", 12),
            fg_color="#ff002f",
            hover_color="#E44982",
            border_color="#000000",
            text_color="#000000",
            corner_radius=10,
            text_color_disabled="#ff002f",
            border_width=2,
            width=100,
            height=50,
        )
        self.last_4_btn = CTkButton(
            self.last_frm_1,
            text="Show",
            font=("Arial Bold", 12),
            fg_color="#ff002f",
            hover_color="#E44982",
            border_color="#000000",
            text_color="#000000",
            corner_radius=10,
            text_color_disabled="#ff002f",
            border_width=2,
            width=100,
            height=50,
        )
        self.last_5_btn = CTkButton(
            self.last_frm_1,
            text="Show",
            font=("Arial Bold", 12),
            fg_color="#ff002f",
            hover_color="#E44982",
            border_color="#000000",
            text_color="#000000",
            corner_radius=10,
            text_color_disabled="#ff002f",
            border_width=2,
            width=100,
            height=50,
        )
        self.last_6_btn = CTkButton(
            self.last_frm_1,
            text="Show",
            font=("Arial Bold", 12),
            fg_color="#ff002f",
            hover_color="#E44982",
            border_color="#000000",
            text_color="#000000",
            corner_radius=10,
            text_color_disabled="#00ff26",
            border_width=2,
            width=100,
            height=50,
        )
        self.show_new_btn_9 = CTkButton(
            master=self.last_frm_1,
            text="",
            font=("Arial Bold", 14),
            fg_color="#fff",
            hover_color="#fff",
            border_color="#fff",
            text_color="#ffffff",
            border_width=2,
            width=100,
            height=50
        )

        self.create_new_btn_9 = CTkButton(
            master=self.last_frm_1,
            text="",
            font=("Arial Bold", 14),
            fg_color="#fff",
            hover_color="#fff",
            border_color="#fff",
            text_color="#ffffff",
            border_width=2,
            width=100,
            height=50
        )
    def last_conf(self):


        self.last_frm_1.pack(
            anchor='e',
            side="right",
            padx=2,
            pady=(5,0)
        )
        self.last_cmb.grid(
            row=0,
            column=0,
            pady=(5,0),
        )
        self.last_1_btn.grid(
            row=1,
            column=0,
            pady=(5,0),
        )
        self.last_2_btn.grid(
            row=2,
            column=0,
            pady=(5,0),
        )
        self.last_3_btn.grid(
            row=3,
            column=0,
            pady=(5,0),
        )
        self.last_4_btn.grid(
            row=4,
            column=0,
            pady=(5,0),
        )
        self.last_5_btn.grid(
            row=5,
            column=0,
            pady=(5,0),
        )
        self.last_6_btn.grid(
            row=6,
            column=0,
            pady=(5,0),
        )
        #self.status_7_btn.grid(
        #    row=7,
        #    column=0,
        #    pady=(5,0),
        #)
        self.show_new_btn_9.grid(
            row=7,
            column=0,
            pady=(5,0)
        )
        self.create_new_btn_9.grid(
            row=8,
            column=0,
            pady=(5,0)
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
            anchor='n',
            fill='both',
        )

        self.title_frame.pack(
            anchor="w",
            fill="x",
            expand=True,
            padx=27, 
        )
        self.title_lbl.grid(
            row=0,
            column=1,
            #pady=(35,10),
            padx=(27, 40),
        )
        #self.title_lbl.pack(
        #    anchor="n", 
        #    side="top",
        #    fill='x',
        #    pady=(35,10),
        #    padx=(27, 40),
        #)

        self.center_titles_frm.grid(
            row=0,
            column=0,
            pady=(70,10),
            padx=5
        )
        

        self.section_lbl.grid(
            row=0,
            column=2,
            pady=(70,10),
            padx=(27, 40),
        )

        self.search_btn.pack(
            anchor='w',
            side='right',
            #pady=(35,10),
            #padx=(0,350),
        )
        self.search_ent.pack(
            anchor='w',
            side='right',
            #pady=(35,10),
        )
        self.total_fields_frm.pack(
            anchor="e",
            fill='both',
        )
        self.inner_view.pack(
            anchor='e',
            fill="both",
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

def main():
    """ configurations of root window.
    title, icon, main loop """
    global window 

    #root = tb.Window(
    #    themename="vapor"
    #)
    import platform
    
    window = Documents()

    if platform.system() == "Linux":
        window.attributes('-zoomed', True)
    else:
        window.state("zoomed")

    #window.geometry("1080x645")
    #window.minsize(700, 700)
    window.mainloop()

if __name__ == "__main__":
    main()
