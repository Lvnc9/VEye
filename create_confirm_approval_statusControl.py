import customtkinter as ctk
from customtkinter import *
from CTkTable import CTkTable
from PIL import Image, ImageTk, ImageSequence
import tkinter as tk
import qrcode
import threading
import ttkbootstrap as ttk

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


class CrCoApSt:

    def __init__(self, parent):
        #super().__init__(master)
        #self.title("BarAvard24. Business Management")
        #set_appearance_mode("light")
        self.parent = parent

        self.base_font = ctk.CTkFont(family="Arial", size=12)
        self.bold_font = ctk.CTkFont(family="Arial", size=15, weight="bold", underline=1,)
        self.italic_font = ctk.CTkFont(family="Arial", size=12, slant="italic")
        self.underline_font = ctk.CTkFont(family="Arial", size=12, underline=1)
        
        self.is_bold = False
        self.is_italic = False
        self.is_underlined = False

        
        #self.sidebar()
        #self.main_page()
        #self.tadvin()
        #self.confirm()
        #self.approval()
        #self.control()
        #self.last_bar()
        #self.configurations()

        #self.tad_config()
        #self.conf_config()
        #self.app_config()
        #self.cont_config()
        #self.last_bar_config()

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

    def enable_all(self):
        tk.messagebox.showinfo("Enabled", "Successfully Enabled to Edit")
        self.conf_explain_1_1_ent.configure(state=NORMAL)
        self.conf_radio_1_1_rdbtn.configure(state=NORMAL)
        self.conf_radio_1_2_rdbtn.configure(state=NORMAL)
        self.conf_radio_1_3_rdbtn.configure(state=NORMAL)
        self.conf_radio_1_4_rdbtn.configure(state=NORMAL)
        self.conf_notes_1_3_txt.configure(state=NORMAL)
        self.conf_date_2_3_ent.configure(state=NORMAL)


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
            text="System Management Dashboard", 
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
            text="Edit Documents // Design",
            text_color='#fff',
            font=("Arial Bold", 14),
        )

    def tadvin(self):
        self.tad_explain_1_frm = CTkFrame(
            self.main_view,
            fg_color="#fff",
        )

        img_doc = Image.open("./img/documents.png")
        img_doc = CTkImage(
            light_image=img_doc,
            dark_image=img_doc,
            size=(40,40),
        )

        self.tad_title_1_1_lbl = CTkLabel(
            self.tad_explain_1_frm,
            text="Creater: Name and Last Name of Creater",
            justify='left',
            image=img_doc,
            compound='left',
            font=("Arial Black", 18),
            text_color="#601E88",
        )
        self.tad_horizontal_separator_1_1 = ctk.CTkFrame(
            self.tad_explain_1_frm, 
            fg_color="gray", 
            height=2, 
            width=450
        )
        
        self.tad_border_frame_1_frm = CTkFrame(
            self.tad_explain_1_frm,
            fg_color="black", 
            corner_radius=15
            )

        self.tad_explain_1_1_frm = CTkFrame(
            self.tad_border_frame_1_frm,
            border_color="#000000",
            fg_color="#fff",
        )

        glass_img = Image.open("./img/glasses-01.png")
        glass_img = CTkImage(
            light_image=glass_img,
            dark_image=glass_img,
            size=(50,50)
        )

        self.tad_title_1_2_lbl = CTkLabel(
            self.tad_explain_1_1_frm,
            text=" Visible details on the document",
            image=glass_img,
            compound='left',
            justify='left',
            font=("Arial Black", 14),
            text_color="#000000",
        )
        self.tad_explain_1_2_frm = CTkFrame(
            self.tad_explain_1_1_frm,
            fg_color="#fff",
        )
        
        self.tad_explain_1_1_ent = UndoableEntry(
            self.tad_explain_1_2_frm,
            placeholder_text="Free Text: With Gratetude;",
            justify='left',
            width=200,
        )

        self.tad_radio_1_1_rdbtn = CTkCheckBox(
            self.tad_explain_1_2_frm,
            text="Responsibility",
            #border_color="#1cff91",
            #hover_color="#E44982",
            #image=pen_img,
            #compound='left',
            corner_radius=50,
            border_color="#325f80",
            hover_color="#ff0000",
            text_color="#000000",
        )

        #self.radio_1_1_rdbtn = ttk.Checkbutton(
        #    self.radio_1_1_frm,
        #    text="Responsibility",
        #    #style="success-round-toggle",
        #)
        
        self.tad_radio_1_2_rdbtn = CTkCheckBox(
            self.tad_explain_1_2_frm,
            text="Name & Last name",
            corner_radius=50,
            border_color="#325f80",
            hover_color="#ff0000",
            text_color="#000000",
        )

        self.tad_radio_1_3_rdbtn = CTkCheckBox(
            self.tad_explain_1_2_frm,
            text="Role",
            corner_radius=50,
            border_color="#325f80",
            hover_color="#ff0000",
            text_color="#000000",
        )

        self.tad_radio_1_4_rdbtn = CTkCheckBox(
            self.tad_explain_1_2_frm,
            text="Date & Signature",
            corner_radius=50,
            border_color="#325f80",
            hover_color="#ff0000",
            text_color="#000000",
        )

        self.tad_explain_1_3_frm = CTkFrame(
            self.tad_explain_1_frm,
            fg_color="#fff",
        )

        pen_img = Image.open("./img/pen-02.png")
        pen_img = CTkImage(
            light_image=pen_img,
            dark_image=pen_img,
            size=(25,25),
        )
        self.tad_exp_1_3_lbl = CTkLabel(
            self.tad_explain_1_frm,
            image=pen_img,
            compound='left',
            text_color="#601E88",
            font=("Arial Bold", 14),
            text="Explain Your Documentation",
        )

        self.tad_notes_1_3_txt = CustomTextBox(
            self.tad_explain_1_3_frm,
            width=700,
            height=200,
            corner_radius=8,
            border_color="#030202",
            fg_color="#b8a7a7",
            )

        self.tad_explain_1_4_frm = CTkFrame(
            self.tad_explain_1_frm,
            fg_color="#fff",
        )

        self.tad_explain_1_4_1_frm = CTkFrame(
            self.tad_explain_1_frm,
            fg_color="#fff",
        )

        self.tad_date_2_3_ent = UndoableEntry(
            self.tad_explain_1_4_frm,
            placeholder_text="Creation Date:",
            justify='left',
            font=self.base_font,
            width=200,
            fg_color="#EEEEEE", 
            border_color="#601E88",
            border_width=1, 
            text_color="#000000",
        )

        self.tad_horizontal_separator_1_2 = CTkFrame(
            self.tad_explain_1_frm, 
            fg_color="gray", 
            height=2, 
            width=150,
        )

        self.tad_save_1_4_btn = CTkButton(
            self.tad_explain_1_4_1_frm,
            text="Confirm & Send",
            fg_color="#028000",
            hover_color="#E44982",
            text_color="#ffffff",
            command=self.success_mssg
        )
        self.tad_save_2_4_btn = CTkButton(
            self.tad_explain_1_4_1_frm,
            text="Returned",
            fg_color="#ffb300",
            hover_color="#E44982",
            text_color="#ffffff",
            command=self.enable_all
        )
        
    def confirm(self):
        self.conf_explain_1_frm = CTkFrame(
            self.main_view,
            fg_color="#fff",
        )

        img_doc = Image.open("./img/documents.png")
        img_doc = CTkImage(
            light_image=img_doc,
            dark_image=img_doc,
            size=(40,40),
        )

        self.conf_title_1_1_lbl = CTkLabel(
            self.conf_explain_1_frm,
            text="Confirmer: Name and Last Name of Creater",
            justify='left',
            image=img_doc,
            compound='left',
            font=("Arial Black", 18),
            text_color="#601E88",
        )
        self.conf_horizontal_separator_1_1 = CTkFrame(
            self.conf_explain_1_frm, 
            fg_color="gray", 
            height=2, 
            width=450
        )
        
        self.conf_border_frame_1_frm = CTkFrame(
            self.conf_explain_1_frm,
            fg_color="black", 
            corner_radius=15
            )

        self.conf_explain_1_1_frm = CTkFrame(
            self.conf_border_frame_1_frm,
            border_color="#000000",
            fg_color="#fff",
        )

        glass_img = Image.open("./img/glasses-01.png")
        glass_img = CTkImage(
            light_image=glass_img,
            dark_image=glass_img,
            size=(50,50)
        )

        self.conf_title_1_2_lbl = CTkLabel(
            self.conf_explain_1_1_frm,
            text=" Visible details on the document",
            image=glass_img,
            compound='left',
            justify='left',
            font=("Arial Black", 14),
            text_color="#000000",

        )
        self.conf_explain_1_2_frm = CTkFrame(
            self.conf_explain_1_1_frm,
            fg_color="#fff",
        )
        
        self.conf_explain_1_1_ent = UndoableEntry(
            self.conf_explain_1_2_frm,
            placeholder_text="Free Text: With Gratetude;",
            state=DISABLED,
            justify='left',
            width=200,
        )

        self.conf_radio_1_1_rdbtn = CTkCheckBox(
            self.conf_explain_1_2_frm,
            text="Responsibility",
            #border_color="#1cff91",
            #hover_color="#E44982",
            #image=pen_img,
            #compound='left',
            state=DISABLED,
            corner_radius=50,
            border_color="#325f80",
            hover_color="#ff0000",
            text_color="#000000",

        )

        #self.radio_1_1_rdbtn = ttk.Checkbutton(
        #    self.radio_1_1_frm,
        #    text="Responsibility",
        #    #style="success-round-toggle",
        #)
        self.conf_radio_1_2_rdbtn = CTkCheckBox(
            self.conf_explain_1_2_frm,
            text="Name & Last name",
            state=DISABLED,
            corner_radius=50,
            border_color="#325f80",
            hover_color="#ff0000",
            text_color="#000000",

        )

        self.conf_radio_1_3_rdbtn = CTkCheckBox(
            self.conf_explain_1_2_frm,
            text="Role",
            corner_radius=50,
            state=DISABLED,
            border_color="#325f80",
            hover_color="#ff0000",
            text_color="#000000",

        )

        self.conf_radio_1_4_rdbtn = CTkCheckBox(
            self.conf_explain_1_2_frm,
            text="Date & Signature",
            state=DISABLED,
            corner_radius=50,
            border_color="#325f80",
            hover_color="#ff0000",
            text_color="#000000",

        )

        self.conf_explain_1_3_frm = CTkFrame(
            self.conf_explain_1_frm,
            fg_color="#fff",
        )

        pen_img = Image.open("./img/pen-02.png")
        pen_img = CTkImage(
            light_image=pen_img,
            dark_image=pen_img,
            size=(25,25),
        )
        self.conf_exp_1_3_lbl = CTkLabel(
            self.conf_explain_1_frm,
            image=pen_img,
            compound='left',
            text_color="#601E88",
            font=("Arial Bold", 14),
            text="Explain Your Documentation",
        )

        self.conf_notes_1_3_txt = CustomTextBox(
            self.conf_explain_1_3_frm,
            width=700,
            height=200,
            corner_radius=8,
            state=DISABLED,
            border_color="#030202",
            fg_color="#b8a7a7",
            )

        self.conf_explain_1_4_frm = CTkFrame(
            self.conf_explain_1_frm,
            fg_color="#fff",
        )

        self.conf_explain_1_4_1_frm = CTkFrame(
            self.conf_explain_1_frm,
            fg_color="#fff",
        )

        self.conf_date_2_3_ent = UndoableEntry(
            self.conf_explain_1_4_frm,
            placeholder_text="Creation Date:",
            justify='left',
            font=self.base_font,
            width=200,
            state=DISABLED,
            fg_color="#EEEEEE", 
            border_color="#601E88",
            border_width=1, 
            text_color="#000000",
        )

        self.conf_horizontal_separator_1_2 = CTkFrame(
            self.conf_explain_1_frm, 
            fg_color="gray", 
            height=2, 
            width=150,
        )

        self.conf_save_1_4_btn = CTkButton(
            self.conf_explain_1_4_1_frm,
            text="Save & Send",
            fg_color="#028000",
            hover_color="#E44982",
            text_color="#ffffff",
            command=self.success_mssg
        )
        self.conf_save_2_4_btn = CTkButton(
            self.conf_explain_1_4_1_frm,
            text="Edit",
            fg_color="#ffb300",
            hover_color="#E44982",
            text_color="#ffffff",
            command=self.enable_all
        )


    def approval(self):
        self.app_explain_1_frm = CTkFrame(
            self.main_view,
            fg_color="#fff",
        )

        img_doc = Image.open("./img/documents.png")
        img_doc = CTkImage(
            light_image=img_doc,
            dark_image=img_doc,
            size=(40,40),
        )

        self.app_title_1_1_lbl = CTkLabel(
            self.app_explain_1_frm,
            text="Approver: Name and Last Name of Creater",
            justify='left',
            image=img_doc,
            compound='left',
            font=("Arial Black", 18),
            text_color="#601E88",
        )
        self.app_horizontal_separator_1_1 = ctk.CTkFrame(
            self.app_explain_1_frm, 
            fg_color="gray", 
            height=2, 
            width=450
        )
        
        self.app_border_frame_1_frm = CTkFrame(
            self.app_explain_1_frm,
            fg_color="black", 
            corner_radius=15
            )

        self.app_explain_1_1_frm = CTkFrame(
            self.app_border_frame_1_frm,
            border_color="#000000",
            fg_color="#fff",
        )

        glass_img = Image.open("./img/glasses-01.png")
        glass_img = CTkImage(
            light_image=glass_img,
            dark_image=glass_img,
            size=(50,50)
        )

        self.app_title_1_2_lbl = CTkLabel(
            self.app_explain_1_1_frm,
            text=" Visible details on the document",
            image=glass_img,
            compound='left',
            justify='left',
            font=("Arial Black", 14),
            text_color="#000000",
        )
        self.app_explain_1_2_frm = CTkFrame(
            self.app_explain_1_1_frm,
            fg_color="#fff",
        )
        
        self.app_explain_1_1_ent = UndoableEntry(
            self.app_explain_1_2_frm,
            placeholder_text="Free Text: With Gratetude;",
            justify='left',
            width=200,
        )

        self.app_radio_1_1_rdbtn = CTkCheckBox(
            self.app_explain_1_2_frm,
            text="Responsibility",
            #border_color="#1cff91",
            #hover_color="#E44982",
            #image=pen_img,
            #compound='left',
            corner_radius=50,
            border_color="#325f80",
            hover_color="#ff0000",
            text_color="#000000",
        )

        #self.radio_1_1_rdbtn = ttk.Checkbutton(
        #    self.radio_1_1_frm,
        #    text="Responsibility",
        #    #style="success-round-toggle",
        #)
        self.app_radio_1_2_rdbtn = CTkCheckBox(
            self.app_explain_1_2_frm,
            text="Name & Last name",
            corner_radius=50,
            border_color="#325f80",
            hover_color="#ff0000",
            text_color="#000000",
        )

        self.app_radio_1_3_rdbtn = CTkCheckBox(
            self.app_explain_1_2_frm,
            text="Role",
            corner_radius=50,
            border_color="#325f80",
            hover_color="#ff0000",
            text_color="#000000",
        )

        self.app_radio_1_4_rdbtn = CTkCheckBox(
            self.app_explain_1_2_frm,
            text="Date & Signature",
            corner_radius=50,
            border_color="#325f80",
            hover_color="#ff0000",
            text_color="#000000",
        )

        self.app_explain_1_3_frm = CTkFrame(
            self.app_explain_1_frm,
            fg_color="#fff",
        )

        pen_img = Image.open("./img/pen-02.png")
        pen_img = CTkImage(
            light_image=pen_img,
            dark_image=pen_img,
            size=(25,25),
        )
        self.app_exp_1_3_lbl = CTkLabel(
            self.app_explain_1_frm,
            image=pen_img,
            compound='left',
            text_color="#601E88",
            font=("Arial Bold", 14),
            text="Explain Your Documentation",
        )

        self.app_notes_1_3_txt = CustomTextBox(
            self.app_explain_1_3_frm,
            width=700,
            height=200,
            corner_radius=8,
            border_color="#030202",
            fg_color="#b8a7a7",
            )

        self.app_explain_1_4_frm = CTkFrame(
            self.app_explain_1_frm,
            fg_color="#fff",
        )

        self.app_explain_1_4_1_frm = CTkFrame(
            self.app_explain_1_frm,
            fg_color="#fff",
        )

        self.app_date_2_3_ent = UndoableEntry(
            self.app_explain_1_4_frm,
            placeholder_text="Creation Date:",
            justify='left',
            font=self.base_font,
            width=200,
            fg_color="#EEEEEE", 
            border_color="#601E88",
            border_width=1, 
            text_color="#000000",
        )

        self.app_horizontal_separator_1_2 = CTkFrame(
            self.app_explain_1_frm, 
            fg_color="gray", 
            height=2, 
            width=150,
        )

        self.app_save_1_4_btn = CTkButton(
            self.app_explain_1_4_1_frm,
            text="Approve & Distribute",
            fg_color="#028000",
            hover_color="#E44982",
            text_color="#ffffff",
            command=self.success_mssg
        )
        self.app_save_2_4_btn = CTkButton(
            self.app_explain_1_4_1_frm,
            text="Returned",
            fg_color="#ffb300",
            hover_color="#E44982",
            text_color="#ffffff",
            command=self.enable_all
        )

    def control(self):
        self.cont_explain_1_frm = CTkFrame(
            self.main_view,
            fg_color='#fff',
        )

        img_stats = Image.open("./img/stats1.png")
        img_stats = CTkImage(
            light_image=img_stats,
            dark_image=img_stats,
            size=(40,40)
        )

        self.cont_title_1_1_lbl = CTkLabel(
            self.cont_explain_1_frm,
            text="Control Status",
            justify='left',
            image=img_stats,
            compound='left',
            font=("Arial Black", 18),
            text_color="#601E88",
        )
        self.cont_horizontal_separator_1_1 = ctk.CTkFrame(
            self.cont_explain_1_frm, 
            fg_color="gray", 
            height=2, 
            width=450
        )
        
        self.cont_border_frame_1_frm = CTkFrame(
            self.cont_explain_1_frm,
            fg_color="black", 
            corner_radius=15
            )

        self.cont_explain_1_1_frm = CTkFrame(
            self.cont_border_frame_1_frm,
            border_color="#000000",
            fg_color="#fff",
        )

        scan_img = Image.open('./img/scan.png')
        scan_img = CTkImage(
            light_image=scan_img,
            dark_image=scan_img,
            size=(50,50)
        )

        self.cont_title_1_2_lbl = CTkLabel(
            self.cont_explain_1_1_frm,
            text=" Visible details after scanning the QRcode",
            image=scan_img,
            compound='left',
            justify='left',
            font=("Arial Black", 14),
            text_color="#000000",
        )

        self.cont_explain_1_2_frm = CTkFrame(
            self.cont_explain_1_1_frm,
            fg_color="#fff",
        )
        img_qr = Image.open("./img/insurance1.png")
        img_qr = CTkImage(
            light_image=img_qr,
            dark_image=img_qr,
            size=(150,150)
        )
        self.qr_1_1_lbl = CTkLabel(
            self.cont_explain_1_2_frm,
            text="",
            compound='left',
            image=img_qr
        )

        self.cont_explain_1_1_ent = UndoableEntry(
            self.cont_explain_1_2_frm,
            placeholder_text="Free Text:\nWith scanning the QRcode make sure of the validation of your documents!\nwith gratetude!\nplanning unit.",
            width=700,
            height=150,
            justify='left',
        )

        self.cont_explain_1_3_frm = CTkFrame(
            self.cont_explain_1_2_frm,
            fg_color='#fff',
        )
        self.rd_value = StringVar() 

        self.valid_1_ckbtn = CTkRadioButton(
            self.cont_explain_1_3_frm,
            text='Valid',
            text_color="#028000",
            fg_color="#028000",
            hover_color="#028000",
            corner_radius=50,
            font=self.bold_font,
            value='on',
            variable=self.rd_value,
        )

        self.invalid_1_ckbtn = CTkRadioButton(
            self.cont_explain_1_3_frm,
            text="Outdated",
            text_color='#fc0303',
            corner_radius=50,
            fg_color="#fc0303",
            hover_color="#fc0303",
            font=self.bold_font,
            value='off',
            variable=self.rd_value,
        )

    def cont_config(self):
        self.cont_explain_1_frm.pack(
            anchor='w',
            expand=True,
            fill=X,
            pady=10,
            padx=10,
        )

        self.cont_title_1_1_lbl.pack(
            anchor='w',
            padx=5,
            pady=(5,0),
        )
        self.cont_horizontal_separator_1_1.pack(
            anchor='w',
            expand=True,
            padx=5,
            pady=(6,25),
        )
        self.cont_border_frame_1_frm.pack(
            anchor='w',
            expand=True,
            padx=35,
            pady=5,
        )
        self.cont_explain_1_1_frm.pack(
            anchor='w',
            expand=True,
            padx=5,
            pady=5,
        )
        
        self.cont_title_1_2_lbl.pack(
            anchor='n',
            padx=5,
            pady=5,
        )
        self.cont_explain_1_2_frm.pack(
            anchor='w',
            padx=5,
            pady=5,
        )

        self.qr_1_1_lbl.pack(
            anchor='w',
            padx=5,
            pady=5,
        )

        self.cont_explain_1_1_ent.pack(
            anchor='w',
            padx=5,
            pady=5,
        )
        self.cont_explain_1_3_frm.pack(
            anchor='w',
            padx=5,
            pady=5,
        )
        self.valid_1_ckbtn.grid(
            row=0,
            column=0,
            padx=5,
            pady=5,
        )
        self.invalid_1_ckbtn.grid(
            row=0,
            column=1,
            padx=5,
            pady=5,
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

    def last_bar(self):
        self.last_explain_1_frm = CTkFrame(
            self.main_view,
            fg_color="#000000",
        )
        self.upper_1_frm = CTkFrame(
            self.last_explain_1_frm,
            fg_color="#1b1a1c",
        )
        self.send_kartable_1_btn = CTkButton(
            self.upper_1_frm,
            text='Send to Kartaubl',
            corner_radius=40,
            fg_color="#601E88",
            hover_color="#E44982",
            command=self.success_mssg,
        )
        self.preview_2_btn = CTkButton(
            self.upper_1_frm,
            text='Show Preview',
            corner_radius=40,
            fg_color="#601E88",
            hover_color="#E44982",
            command=self.success_mssg,
        )

        self.save_3_btn = CTkButton(
            self.upper_1_frm,
            text='Save',
            corner_radius=40,
            fg_color="#601E88",
            hover_color="#E44982",
            command=self.success_mssg
        )

        self.lower_2_frm = CTkFrame(
            self.last_explain_1_frm,
            fg_color='#000000',
        )

        vroad = Image.open("./img/vroad.png")
        vroad = CTkImage(
            dark_image=vroad,
            light_image=vroad,
            size=(600,180)
        )

        self.footnote_8_1_lbl = CTkLabel(
            self.lower_2_frm,
            text="",
            fg_color='transparent',
            image=vroad,
            compound="left",
        )

    def last_bar_config(self):
        self.last_explain_1_frm.pack(
            anchor='w',
            fill='x',
            pady=(20,10),
            padx=10
        )
        self.upper_1_frm.pack(
            anchor='n',
            side="top",
            padx=5,
            pady=(5,35),
        )
        self.send_kartable_1_btn.grid(
            row=0,
            column=0,
            padx=5,
            pady=5,
        )

        self.preview_2_btn.grid(
            row=0,
            column=1,
            padx=5,
            pady=5,
        )
        self.save_3_btn.grid(
            row=0,
            column=2,
            padx=5,
            pady=5,
        )
        self.lower_2_frm.pack(
            anchor='n',
            side='top',
            padx=5,
            pady=(25,20)
        )

        self.footnote_8_1_lbl.pack(
            anchor='n',
        )


    def tad_config(self):
        self.tad_explain_1_frm.pack(
            anchor="w",
            expand=True,
            fill=X,
            pady=10,
            padx=10,
        )

        self.tad_title_1_1_lbl.pack(
            anchor='w',
            padx=5,
            pady=(5,0),
        )
        self.tad_horizontal_separator_1_1.pack(
            anchor='w',
            padx=5,
            pady=(6,25),
        )
        self.tad_border_frame_1_frm.pack(
            anchor='w',
            expand=True,
            padx=35,
            pady=5,
        )
        self.tad_explain_1_1_frm.pack(
            anchor='n',
            expand=True,
            padx=5,
            pady=5,
        )
        self.tad_title_1_2_lbl.pack(
            anchor='n',
            padx=5,
            pady=5,
        )
        self.tad_explain_1_2_frm.pack(
            anchor='w',
            expand=True,
            padx=5,
            pady=5,
        )
        self.tad_explain_1_1_ent.grid(
            row=0,
            column=0,
            padx=5,
        )
        self.tad_radio_1_1_rdbtn.grid(
            row=0,
            column=1,
            padx=5,
        )
        self.tad_radio_1_2_rdbtn.grid(
            row=0,
            column=2,
            padx=5,
        )
        self.tad_radio_1_3_rdbtn.grid(
            row=0,
            column=3,
            padx=5,
        )
        self.tad_radio_1_4_rdbtn.grid(
            row=0,
            column=4,
            padx=5,
        )

        self.tad_exp_1_3_lbl.pack(
            anchor='w',
            expand=True,
            padx=35,
            pady=(10,0),
        )
        self.tad_explain_1_3_frm.pack(
            anchor='w',
            expand=True,
            padx=35,
#            pady=10,
        )
        self.tad_notes_1_3_txt.grid(
            row=0,
            column=0,
            padx=3
        )
        self.tad_explain_1_4_frm.pack(
            anchor='w',
            padx=35,
            pady=(10,5),
        )

        self.tad_horizontal_separator_1_2.pack(
            anchor='w',
            expand=True,
            pady=(5,5),
            padx=40,
        )

        self.tad_explain_1_4_1_frm.pack(
            anchor='w',
            padx=35,
            pady=(30,5),
        )
        self.tad_date_2_3_ent.grid(
            row=0,
            column=0,
            padx=5,
        )
        self.tad_save_1_4_btn.grid(
            row=1,
            column=0,
            padx=5,
        )
        self.tad_save_2_4_btn.grid(
            row=1,
            column=1,
            padx=5,
        )

    def conf_config(self):
        self.conf_explain_1_frm.pack(
            anchor="w",
            expand=True,
            fill=X,
            pady=10,
            padx=10,
        )

        self.conf_title_1_1_lbl.pack(
            anchor='w',
            padx=5,
            pady=(5,0),
        )
        self.conf_horizontal_separator_1_1.pack(
            anchor='w',
            padx=5,
            pady=(6,25),
        )
        self.conf_border_frame_1_frm.pack(
            anchor='w',
            expand=True,
            padx=35,
            pady=5,
        )
        self.conf_explain_1_1_frm.pack(
            anchor='n',
            expand=True,
            padx=5,
            pady=5,
        )
        self.conf_title_1_2_lbl.pack(
            anchor='n',
            padx=5,
            pady=5,
        )
        self.conf_explain_1_2_frm.pack(
            anchor='w',
            expand=True,
            padx=5,
            pady=5,
        )
        self.conf_explain_1_1_ent.grid(
            row=0,
            column=0,
            padx=5,
        )
        self.conf_radio_1_1_rdbtn.grid(
            row=0,
            column=1,
            padx=5,
        )
        self.conf_radio_1_2_rdbtn.grid(
            row=0,
            column=2,
            padx=5,
        )
        self.conf_radio_1_3_rdbtn.grid(
            row=0,
            column=3,
            padx=5,
        )
        self.conf_radio_1_4_rdbtn.grid(
            row=0,
            column=4,
            padx=5,
        )

        self.conf_exp_1_3_lbl.pack(
            anchor='w',
            expand=True,
            padx=35,
            pady=(10,0),
        )
        self.conf_explain_1_3_frm.pack(
            anchor='w',
            expand=True,
            padx=35,
#            pady=10,
        )
        self.conf_notes_1_3_txt.grid(
            row=0,
            column=0,
            padx=3
        )
        self.conf_explain_1_4_frm.pack(
            anchor='w',
            padx=35,
            pady=(10,5),
        )

        self.conf_horizontal_separator_1_2.pack(
            anchor='w',
            expand=True,
            pady=(5,5),
            padx=40,
        )

        self.conf_explain_1_4_1_frm.pack(
            anchor='w',
            padx=35,
            pady=(30,5),
        )
        self.conf_date_2_3_ent.grid(
            row=0,
            column=0,
            padx=5,
        )
        self.conf_save_1_4_btn.grid(
            row=1,
            column=0,
            padx=5,
        )
        self.conf_save_2_4_btn.grid(
            row=1,
            column=1,
            padx=5,
        )


    def app_config(self):
        self.app_explain_1_frm.pack(
            anchor="w",
            expand=True,
            fill=X,
            pady=10,
            padx=10,
        )

        self.app_title_1_1_lbl.pack(
            anchor='w',
            padx=5,
            pady=(5,0),
        )
        self.app_horizontal_separator_1_1.pack(
            anchor='w',
            padx=5,
            pady=(6,25),
        )
        self.app_border_frame_1_frm.pack(
            anchor='w',
            expand=True,
            padx=35,
            pady=5,
        )
        self.app_explain_1_1_frm.pack(
            anchor='n',
            expand=True,
            padx=5,
            pady=5,
        )
        self.app_title_1_2_lbl.pack(
            anchor='n',
            padx=5,
            pady=5,
        )
        self.app_explain_1_2_frm.pack(
            anchor='w',
            expand=True,
            padx=5,
            pady=5,
        )
        self.app_explain_1_1_ent.grid(
            row=0,
            column=0,
            padx=5,
        )
        self.app_radio_1_1_rdbtn.grid(
            row=0,
            column=1,
            padx=5,
        )
        self.app_radio_1_2_rdbtn.grid(
            row=0,
            column=2,
            padx=5,
        )
        self.app_radio_1_3_rdbtn.grid(
            row=0,
            column=3,
            padx=5,
        )
        self.app_radio_1_4_rdbtn.grid(
            row=0,
            column=4,
            padx=5,
        )

        self.app_exp_1_3_lbl.pack(
            anchor='w',
            expand=True,
            padx=35,
            pady=(10,0),
        )
        self.app_explain_1_3_frm.pack(
            anchor='w',
            expand=True,
            padx=35,
#            pady=10,
        )
        self.app_notes_1_3_txt.grid(
            row=0,
            column=0,
            padx=3
        )
        self.app_explain_1_4_frm.pack(
            anchor='w',
            padx=35,
            pady=(10,5),
        )

        self.app_horizontal_separator_1_2.pack(
            anchor='w',
            expand=True,
            pady=(5,5),
            padx=40,
        )

        self.app_explain_1_4_1_frm.pack(
            anchor='w',
            padx=35,
            pady=(30,5),
        )
        self.app_date_2_3_ent.grid(
            row=0,
            column=0,
            padx=5,
        )
        self.app_save_1_4_btn.grid(
            row=1,
            column=0,
            padx=5,
        )
        self.app_save_2_4_btn.grid(
            row=1,
            column=1,
            padx=5,
        )


def main():
    """ configurations of root window.
    title, icon, main loop """
    global window 

    #root = tb.Window(
    #    themename="vapor"
    #)

    window = CrCoApSt()
    window.geometry("1080x645")
    window.mainloop()

if __name__ == "__main__":
    main()
