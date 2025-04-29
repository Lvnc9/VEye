from customtkinter import *
from CTkTable import CTkTable
from PIL import Image
import ttkbootstrap as tb


class UndoableEntry(CTkEntry):
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


class RegisterPersonel:

    def __init__(self, parent):
        #super().__init__()
        #self.title("BarAvard24. Business Management")
        #set_appearance_mode("light")
        self.parent = parent


        self.lvl_var = StringVar()
        self.roll_var = StringVar()

        #self.sidebar()
        #self.main_page()
        #self.configurations()
        #self.main_view_pack()
        #self.register_form()
        #self.register_configure()

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
            text="Register Personel Section", 
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
            text="Manager Dashboard/Register Personel",
            text_color='#fff',
            font=("Arial Bold", 14),
        )

    def register_form(self):
        self.register_form_frm = CTkFrame(
            self.main_view,
            fg_color="#fff",
        )

        img_doc = Image.open("./img/personel.png")
        img_doc = CTkImage(
            light_image=img_doc,
            dark_image=img_doc,
            size=(40,40),
        )

        self.register_title_1_1_lbl = CTkLabel(
            self.register_form_frm,
            text="Register A Personel",
            justify='left',
            image=img_doc,
            compound='left',
            font=("Arial Black", 18),
            text_color="#601E88",
        )
        self.conf_horizontal_separator_1_1 = CTkFrame(
            self.register_form_frm, 
            fg_color="gray",
            height=2, 
            width=450
        )

        self.information_frm = CTkFrame(
            master=self.register_form_frm, 
            fg_color="#fff"
        )

        self.personel_name_lbl = CTkLabel(
            master=self.information_frm,
            justify="left", 
            text="Name:", 
            font=("Arial Bold", 17), 
            text_color="#52A476"
        )

        self.personel_name_ent = UndoableEntry(
            master=self.information_frm,
            border_width=0,
            width=200,
            fg_color="#F0F0F0",
            font=("Arial Bold", 14),
            text_color='#000000',
        )

        self.personel_last_name_lbl = CTkLabel(
            master=self.information_frm,
            justify="left",
            text="National Code:", 
            font=("Arial Bold", 17), 
            text_color="#52A476"
        )

        self.personel_last_name_ent = UndoableEntry(
            master=self.information_frm,
            border_width=0, 
            width=200,
            fg_color="#F0F0F0",
            font=("Arial Bold", 14),
            text_color='#000000',
        )


        self.addrs_lbl = CTkLabel(
            master=self.information_frm,
            text="Mobile Phone:",
            justify="left",
            font=("Arial Bold", 17),
            text_color="#52A476",
        )

        self.addrs_txt = UndoableEntry(
            master=self.information_frm, 
            fg_color="#F0F0F0", 
            width=200, 
            corner_radius=8,
            font=("Arial Bold", 14),
            text_color='#000000',

            )

        self.access_lvl_lbl = CTkLabel(
            master=self.information_frm,
            text="Access Roll Level",
            justify="left", 
            font=("Arial Bold", 17), 
            text_color="#52A476"
        )

        self.access_lvl_cmb = CTkComboBox(
            master=self.information_frm,
            width=300,
            values=[
                'Level 1',
                'Level 2',
                'Level 3',
                ],
            button_color="#2A8C55", 
            border_color="#2A8C55", 
            border_width=2, 
            button_hover_color="#207244",
            dropdown_hover_color="#207244" , 
            dropdown_fg_color="#2A8C55", 
            dropdown_text_color="#fff",
            variable=self.lvl_var
        )

        self.access_roll_lbl = CTkLabel(
            master=self.information_frm,
            text="Access Roll:",
            justify="left", 
            font=("Arial Bold", 17), 
            text_color="#52A476"
        )

        self.access_roll_cmb = CTkComboBox(
            master=self.information_frm,
            width=300,
            values=[
                'Employer', 
                'Headquarters',
                "Guild",
                ],
                button_color="#2A8C55", 
                border_color="#2A8C55", 
                border_width=2, 
                button_hover_color="#207244",
                dropdown_hover_color="#207244", 
                dropdown_fg_color="#2A8C55", 
                dropdown_text_color="#fff",
                variable=self.roll_var,
        )

        self.select_btn = CTkButton(
            master=self.information_frm,
            width=100,
            text="Select", 
            font=("Arial Bold", 17), 
            hover_color="#207244", 
            fg_color="#2A8C55", 
            text_color="#fff",
            command=self.determiner
        )

        self.show_together_head_lbl = CTkLabel(
            master=self.information_frm,
            text="",
            justify="left", 
            font=("Arial Bold", 25), 
            text_color="#52A476",
        )

        self.show_together_lbl = CTkLabel(
            master=self.information_frm,
            text="",
            justify="left", 
            font=("Arial Bold", 17), 
            text_color="#52A476",
        )

        self.save_btn = CTkButton(
            master=self.information_frm,
            text="Save",
            width=100,
            font=("Arial Bold", 17), 
            hover_color="#207244", 
            fg_color="#2A8C55", 
            text_color="#fff",
            command=self.successful
        )

        self.successful_lbl = CTkLabel(
            master=self.information_frm,
            text="",
            justify="left", 
            font=("Arial Bold", 17), 
            text_color="#52A476",
        )
        #self.register_configure()
        self.last_explain_1_frm = CTkFrame(
            self.main_view,
            fg_color="#000000",
        )

        vroad = Image.open("./img/vroad.png")
        vroad = CTkImage(
            dark_image=vroad,
            light_image=vroad,
            size=(600,180)
        )

        self.footnote_8_1_lbl = CTkLabel(
            self.last_explain_1_frm,
            text="",
            fg_color='transparent',
            image=vroad,
            compound="left",
        )

    def register_configure(self):
        self.register_form_frm.pack(
            anchor="w",
            expand=True,
            fill=X,
            pady=10,
            padx=10,
        )

        self.register_title_1_1_lbl.pack(
            anchor='w',
            padx=5,
            pady=(5,0),
        )
        self.conf_horizontal_separator_1_1.pack(
            anchor='w',
            padx=5,
            pady=(6,25),
        )

        self.information_frm.pack(
            fill="both", 
            expand=True,
            anchor='w', 
            side='left',
            padx=27, 
            pady=(31,0),
            
        )

        #self.head_title.grid(
        #    row=0,
        #    column=0,
        #    padx=10,
        #    pady=30
#
        #)
        #self.personel_name_lbl.pack(
        #    anchor="nw", 
        #    pady=(25,0), 
        #    padx=27
        #)

        self.personel_name_lbl.grid(
            row=0,
            column=0,
            sticky="w"
        )

        self.personel_name_ent.grid(
            row=1,
            column=0,
            ipady=10,
            sticky="w",
            pady=10
        )

        self.personel_last_name_lbl.grid(
            row=0,
            column=1,
            sticky="w"
        )

        
        self.personel_last_name_ent.grid(
            row=1,
            column=1,
            ipady=10,
            sticky="w",
            pady=10
        )

        self.addrs_lbl.grid(
            row=2,
            column=0,
            ipady=10,
            sticky="w",
        )

        self.addrs_txt.grid(
            row=3,
            column=0,
            ipady=10,
            sticky="w",
        )

        self.access_roll_lbl.grid(
            row=4,
            column=0,
            sticky='w',
            pady=10,
        )

        self.access_roll_cmb.grid(
            row=5,
            column=0,
            sticky='w'
        )

        self.access_lvl_lbl.grid(
            row=4,
            column=1,
            sticky='w',
            padx=10,
            pady=10
        )

        self.access_lvl_cmb.grid(
            row=5,
            column=1,
            sticky='w',
            padx=10,
            pady=10
        )

        self.select_btn.grid(
            row=5,
            column=2,
            sticky='w',
            padx=10,
            pady=10
        )

        self.show_together_head_lbl.grid(
            row=6,
            column=0,
            sticky='w'
        )
        self.show_together_lbl.grid(
            row=7,
            column=0,
            sticky='w'
        )
        self.save_btn.grid(
            row=8,
            column=0,
            pady=25,
            sticky='w',
        )
        self.successful_lbl.grid(
            row=8,
            column=1,
            pady=25,
            sticky='w'
        )
        self.last_explain_1_frm.pack(
            anchor='n',
            fill='x',
            pady=(20,10),
            padx=10
        )

        self.footnote_8_1_lbl.pack(
            anchor='n',
            pady=(35,30)
        )


    def last_bar(self):
        self.last_explain_1_frm = CTkFrame(
            self.main_view,
            fg_color="#177cff",
        )

        baravord = Image.open("./img/Baravord.png")
        baravord = CTkImage(
            dark_image=baravord,
            light_image=baravord,
            size=(327,50)
        )

        self.footnote_8_1_lbl = CTkLabel(
            self.last_explain_1_frm,
            text="",
            fg_color='transparent',
            image=baravord,
            compound="left",
        )

    def last_bar_config(self):
        self.last_explain_1_frm.pack(
            anchor='w',
            fill='x',
            pady=(20,10),
            padx=10
        )

        self.footnote_8_1_lbl.pack(
            anchor='n',
        )

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


    def determiner(self):
        t1 = self.lvl_var.get()
        t2 = self.roll_var.get()

        if t2 == "Employer" and t1 == "Level 1":
            title = "CEO"
        elif t2 == "Employer" and t1 == "Level 2":
            title = "Chairman of the Board"
        elif t2 == "Employer" and t1 == "Level 3":
            title = "Board Member"

        elif t2 == "Headquarters" and t1 == "Level 1":
            title = "Management representative"
        elif t2 == "Headquarters" and t1 == "Level 2":
            title = "Deputy/Advisor"
        elif t2 == "Headquarters" and t1 == "Level 3":
            title = "Manager/Chairman"
    
        elif t2 == "Guild" and t1 == "Level 1":
            title = "Supervisor"
        elif t2 == "Guild" and t1 == "Level 2":
            title = "Expert"        
        elif t2 == "Guild" and t1 == "Level 3":
            title = "Employee/Operator"
        else:
            print("not found")
            return None
             
        self.show_together_head_lbl.configure(text='Your Roll:')
        self.show_together_lbl.configure(text=title)

        return True
    
    def successful(self):
        if not self.determiner():
            self.successful_lbl.configure(text="You have not Choose any roll")            
        else:
            self.successful_lbl.configure(text="Successfuly Saved!")

def main():
    """ configurations of root window.
    title, icon, main loop """
    global window

    #root = tb.Window(
    #    themename="vapor"
    #)

    window = RegisterPersonel()
    window.geometry("1000x720")
#    window.resizable(False, False)
    #1080x645
    window.mainloop()

if __name__ == "__main__":
        main()