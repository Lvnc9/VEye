import customtkinter as ctk
from customtkinter import *
from CTkTable import CTkTable
import random
from PIL import Image, ImageTk, ImageSequence
import tkinter as tk
from tkinter import PhotoImage
import qrcode
import threading
import os
#from Dashboard import Dashboard
from Dashboard import Dashboard
from create_confirm_approval_statusControl import CrCoApSt 
from documents import Documents
from register import RegisterPersonel
from poster import Poster, LoadingDialog, UndoableEntry
import time

accounts = {
    "root" : "1234",
}


class Login(CTk):
    """ Gather all the other libraries and use them on a single class """

    def __init__(self, master=None):
        super().__init__(master)
        self.title("Lvnc9. Business Management")
        set_appearance_mode("light")

        self.userVar = StringVar()
        self.passwordVar = StringVar()
        self.robotVar = StringVar()
        
        # bools for moving between sections.
        self.dashboardBool = BooleanVar()
        self.documentBool = BooleanVar()
        self.historyBool = BooleanVar()
        self.registerBool = BooleanVar()
        self.accountBool = BooleanVar()
        self.posterBool = BooleanVar()


        self.login()
        #self.run()
    def show_loading_dialog(self):
        # Create and start the loading dialog
        import time
        loading_dialog = LoadingDialog(self, "./img/loading-03.gif", gif_size=(200, 200))
        loading_dialog.start()

    def return_back(self,element1, element2=None):
        if not element2:
            element1.configure(
                text='your username or password is wrong.'
            )
        else:
            element2.configure(
                text="Pleas enter the correct value for CAPTCHA"
            )
            element1.configure(text="")
    
    def validation(self, userVar, passwordVar, robotVar, passwd, elem1, elem2):
        flag = False
        temp = False
        u = userVar.get()
        p = passwordVar.get()
        r = robotVar.get()
        
        keys = accounts.keys()
        values = accounts.values()

        if u not in keys:
            self.return_back(elem1)
            temp = True
        
        elif p not in values:
            self.return_back(elem1)
            temp = True
        
        elif not r.isnumeric:
            self.return_back(elem1, elem2)
            temp = True
        
        elif passwd:
            for i in passwd:
                if int(r) in i:
                    flag = True
                    print("FOUND!")
                    temp = False
            if not flag:
                    print("not correct")
                    self.return_back(elem1, elem2)
                    temp = True
        
        if not temp:
            elem1.configure(
                text=""
            )
            elem2.configure(
                text=""
            )
            print("showing Dialog")
            self.show_loading_dialog()
            #dashboard = Dashboard()
            #dashboard.main_view_dashboard.configure(master=self)
            self.destroy()  
            #time.sleep(4)

            main = Main()
            main.title("VEye. Business Management")
            main.geometry("1080x645")
            main.mainloop()

    def login(self):
        self.passwords = [
            ["90 + 20", 110],     
            ["50 + 20", 70,],
            ["100 - 10", 90,],
            ["20 + 30", 50,],
            ["10 + 15", 25,],
            [ "45 + 20", 65],]

        side_img_data = Image.open("./img/side-img.png")
        email_icon_data = Image.open("./img/email-icon.png")
        password_icon_data = Image.open("./img/password-icon.png")
        google_icon_data = Image.open("./img/sports-quiz-bg.png")
        password_i = Image.open("./img/robot1.png")

        side_img = CTkImage(dark_image=side_img_data, light_image=side_img_data, size=(300, 480))
        email_icon = CTkImage(dark_image=email_icon_data, light_image=email_icon_data, size=(20,20))
        password_icon = CTkImage(dark_image=password_icon_data, light_image=password_icon_data, size=(17,17))
        google_icon = CTkImage(dark_image=google_icon_data, light_image=google_icon_data, size=(17,17))
        password_i = CTkImage(dark_image=password_i, light_image=password_i, size=(17,17))

        self.side = CTkLabel(
            self, 
            text="", 
            image=side_img
        )
        self.side.pack(
            expand=True, 
            side="right"
        )

        frame = CTkFrame(
            self, 
            width=350, 
            height=480, 
            fg_color="#ffffff"
        )

        frame.pack_propagate(0)
        frame.pack(expand=True, side="right")

        vEye_lbl = CTkLabel(
            master=frame, 
            text="VEye", 
            text_color="#601E88", 
            anchor="w", 
            justify="left", 
            font=("Arial Bold", 24)

        )
        vEye_lbl.pack(
            anchor="w", 
            pady=(10, 0), 
            padx=(25, 0)
        )

        bms = CTkLabel(
            master=frame, 
            text="Business Management System", 
            text_color="#7E7E7E", 
            anchor="w", 
            justify="left", 
            font=("Arial Bold", 12)
        )

        bms.pack(
            anchor="w",
            padx=(25, 0))
        
        self.error_lbl_1 = CTkLabel(
            frame,
            text="",
            font=("Arial Bold", 14),
        )
        self.error_lbl_1.pack(
            anchor='w',
            pady=(20,0),
            padx=(25,0),
        )

        self.national_code_lbl = CTkLabel(
            master=frame, 
            text="  National-Code:", 
            text_color="#601E88", 
            anchor="w", 
            justify="left", 
            font=("Arial Bold", 14), 
            image=email_icon, 
            compound="left")

        self.national_code_lbl.pack(
            anchor="w", 
            pady=(5, 0), 
            padx=(25, 0),)



        self.national_code_ent = UndoableEntry(
            master=frame, 
            width=225, 
            fg_color="#EEEEEE", 
            border_color="#601E88", 
            border_width=1, 
            text_color="#000000",
            textvariable=self.userVar,
            )
        self.national_code_ent.pack(
            anchor="w", 
            padx=(25, 0))


        self.passwd_lbl = CTkLabel(
            master=frame, 
            text="  Password:", 
            text_color="#601E88", 
            anchor="w", 
            justify="left", 
            font=("Arial Bold", 14), 
            image=password_icon, 
            compound="left")
        
        self.passwd_lbl.pack(
            anchor="w", 
            pady=(21, 0), 
            padx=(25, 0),
        )

        
        self.passwd_ent = UndoableEntry(
            master=frame, 
            width=225, 
            fg_color="#EEEEEE", 
            border_color="#601E88", 
            border_width=1, 
            text_color="#000000", 
            show="*",
            textvariable=self.passwordVar,
            )
        
        self.passwd_ent.pack(
            anchor="w", 
            padx=(25, 0))

        choice = random.choice(self.passwords)

        self.robot_lbl = CTkLabel(
            master=frame, 
            text=f" {choice[0]}?", 
            text_color="#601E88", 
            anchor="w", 
            justify="left", 
            font=("Arial Bold", 14), 
            image=password_i, 
            compound='left'
        )
        self.robot_lbl.pack(
                anchor="w", 
                pady=(21, 0), 
                padx=(25, 0))

        self.robot_ent = UndoableEntry(
            master=frame, 
            width=225, 
            fg_color="#EEEEEE", 
            border_color="#601E88", 
            border_width=1, 
            text_color="#000000",
            textvariable=self.robotVar
            )
        
        self.robot_ent.pack(
            anchor="w", 
            padx=(25, 0))

        self.login_btn = CTkButton(
            master=frame, 
            text="Login", 
            fg_color="#601E88", 
            hover_color="#E44982", 
            font=("Arial Bold", 12), 
            text_color="#ffffff", 
            width=50,
            command=lambda: self.validation(
                self.userVar,
                self.passwordVar,
                self.robotVar,
                self.passwords,
                self.error_lbl_1,
                self.error_lbl_2,
            )
            )
        
        self.login_btn.pack(
            anchor="w", padx=(25, 0), pady=(20, 0))

        self.error_lbl_2 = CTkLabel(
            frame,
            text="",
            font=("Arial Bold", 12),
            text_color="#ff0015",
        )
        self.error_lbl_2.pack(
            anchor='w',
            padx=(25,0),
            pady=(5,0)
        )
        self.quizzes_taken_frame = CTkFrame(
            master=frame, 
            fg_color="#ffffff", 
            width=50
        )
        self.quizzes_taken_frame.pack(
            anchor="w", 
            side="left", 
            padx=(0, 5)
        )


        self.google = CTkFrame(
            master=frame, 
            fg_color="#ffffff", 
            width=50
        )
        self.google.pack(
        anchor="w", 
        side="left", 
        padx=(0, 5)
        )

        self.forgot_p = CTkFrame(
            master=frame, 
            fg_color="#ffffff", 
            width=50
        )
        self.forgot_p.pack(
        anchor="w", 
        side="left", 
        padx=(0, 5)
        )


        self.sign_in_btn = CTkButton(
            master=self.quizzes_taken_frame, 
            text="Sign-in", 
            fg_color="#EEEEEE", 
            hover_color="#E44982", 
            font=("Arial Bold", 12), 
            text_color="#601E88", 
            width=50)
        
        self.sign_in_btn.pack(
            anchor="w", padx=(10, 0))

        self.google_btn = CTkButton(
            master=self.google, 
            text="Forgot Password", 
            fg_color="#EEEEEE", 
            hover_color="#E44982", 
            font=("Arial Bold", 12), 
            text_color="#601E88", 
            width=50
            )
        self.google_btn.pack(
            anchor="w", padx=(5, 0))

        self.change_phone_number_btn = CTkButton(
            master=self.forgot_p, 
            text="Change Phone Number", 
            fg_color="#EEEEEE", 
            hover_color="#E44982", 
            font=("Arial Bold", 12), 
            text_color="#601E88", 
            width=50)
        self.change_phone_number_btn.pack(
            anchor="w", padx=(5, 0))



class Main(CTk):
    """ The main winodw """
    PREVIOUS = False
    POSTER = False
    DASHBOARD = False
    LASTSIDE = None

    main_view = None
    main_page = None


    def __init__(self, master=None):
        super().__init__(master)
        self.sidebar()
        self.dashboard_run()
        self.configurations()

        #change_to_register = self.change_to_register
        self.main_view = None
        
        image = Image.open("./img/b-icon-new.png")
        resized_image = image.resize((256, 256), Image.Resampling.LANCZOS)
        resized_image.save("./img/b-icon-new-re.png")
        
        icon_image = PhotoImage(file="./img/b-icon-new-re.png")    
        self.iconphoto(False, icon_image)
        #self.iconbitmap("./img/b-icon.ico")

    def poster_run(self):
        #self.sidebar()
        self.main_page()
        self.half_fields()
        self.half_fields_conf()
        #self.configurations()
        self.bindings()

    def change_to_CrCoApStCo(self):
        Main.main_view.pack_forget()
        
        self.CrCoaApStCo = CrCoApSt(self)
        self.main_page = self.CrCoaApStCo.main_page

        self.tadvin = self.CrCoaApStCo.tadvin
        self.confirm = self.CrCoaApStCo.confirm
        self.approval = self.CrCoaApStCo.approval
        self.control = self.CrCoaApStCo.control
        self.last_bar = self.CrCoaApStCo.last_bar
        self.tad_config = self.CrCoaApStCo.tad_config
        self.conf_config = self.CrCoaApStCo.conf_config
        self.app_config = self.CrCoaApStCo.app_config
        self.cont_config = self.CrCoaApStCo.cont_config
        self.last_bar_config = self.CrCoaApStCo.last_bar_config
        self.bindings = self.CrCoaApStCo.bindings
        self.main_view_pack = self.CrCoaApStCo.main_view_pack

        self.main_page()
        self.main_view_pack()
        self.tadvin()
        self.confirm()
        self.approval()
        self.control()
        self.last_bar()
        #self.tadvin_conf()
        self.tad_config()
        self.conf_config()
        self.app_config()
        self.cont_config()
        self.last_bar_config()
        #self.approval_conf()
        self.bindings()

        Main.main_view = self.CrCoaApStCo.main_view

    def change_to_documents(self):
        Main.main_view.pack_forget()

        documents = Documents(self)
        self.main_page = documents.main_page
        self.column = documents.column
        self.column_conf = documents.column_conf

        self.category = documents.category
        self.category_conf = documents.category_conf
        
        self.title = documents.title
        self.title_conf = documents.title_conf

        self.groups = documents.groups
        self.groups_conf = documents.groups_conf
        
        self.rearangement = documents.rearangement
        self.rearangment_conf = documents.rearangment_conf

        self.code_part = documents.code_part
        self.code_conf = documents.code_conf

        self.accountant = documents.accountant
        self.accountant_conf = documents.accountant_conf

        self.answerer = documents.answerer
        self.answerer_conf = documents.answerer_conf

        self.responder = documents.responder
        self.responder_conf = documents.responder_conf

        self.creater = documents.creater
        self.creater_conf = documents.creater_conf

        self.confirm = documents.confirm
        self.confirm_conf = documents.confirm_conf

        self.approve = documents.approve
        self.approve_conf = documents.approve_conf

        self.status = documents.status
        self.status_conf = documents.status_conf

        self.last = documents.last
        self.last_conf = documents.last_conf

        self.main_view_pack = documents.main_view_pack

        self.bindings = documents.bindings

        #run
        self.main_page()
        self.main_view_pack()
        self.column()
        self.column_conf()
        
        self.category()
        self.category_conf()
        self.title()
        self.title_conf()

        self.groups()
        self.groups_conf()
        
        self.rearangement()
        self.rearangment_conf()

        self.code_part()
        self.code_conf()
        

        self.accountant()
        self.accountant_conf()

        self.answerer()
        self.answerer_conf()

        self.responder()
        self.responder_conf()

        self.creater()
        self.creater_conf()

        self.confirm()
        self.confirm_conf()

        self.approve()
        self.approve_conf()

        self.status()
        self.status_conf()

        self.last()
        self.last_conf()
        self.bindings()

        Main.main_view = documents.main_view

        Main.LASTSIDE.configure(
            fg_color="transparent"
        )
        self.making_documents.configure(
            fg_color="#442f7a",
        )
        Main.LASTSIDE = self.making_documents
        

    def change_to_register(self):
        Main.main_view.pack_forget()

        self.register_ = RegisterPersonel(self)
        self.main_page = self.register_.main_page
        self.register_form = self.register_.register_form
        self.register_configure = self.register_.register_configure
        self.main_view_pack = self.register_.main_view_pack
        
        self.main_page()
        self.main_view_pack()
        self.register_form()
        self.register_configure()

        Main.main_view = self.register_.main_view


    def change_to_poster(self):
        Main.main_view.pack_forget()

        self.poster = Poster(self)
        self.main_page = self.poster.main_page
        self.half_fields = self.poster.half_fields
        self.half_fields_conf = self.poster.half_fields_conf
        self.main_view_pack = self.poster.main_view_pack
        self.bindings = self.poster.bindings

        self.main_view = self.poster.main_view

        #self.sidebar()
        self.main_page()
        self.main_view_pack()
        self.half_fields()
        self.half_fields_conf()
        self.configurations()
        self.last_bar()
        self.last_bar_config()

        Main.main_view = self.poster.main_view

        Main.LASTSIDE.configure(
            fg_color="transparent"
        )
        self.make_poster_btn.configure(
            fg_color="#442f7a",
        )
        Main.LASTSIDE = self.make_poster_btn

    def dashboard_run(self):
        self.dash = Dashboard(self)
        self.main_page = self.dash.main_page
        self.dashboard_ = self.dash.dashboard_
        self.dashboard_conf = self.dash.dashboard_conf
        self.main_view_pack = self.dash.main_view_pack
        Main.main_page = self.dash.main_page

        #Setting to register pannel
        #self.register_1_btn = self.dash.create_btn
        #self.register_2_btn = self.dash.edit_btn
        if Main.PREVIOUS:
            Main.main_view.pack_forget()
            self.main_page()
            self.dashboard_()
            self.dashboard_conf()
            self.main_view_pack()
        else:
            Main.main_view = self.dash.main_view
            Main.PREVIOUS = True

            self.sidebar()
            self.main_page()
            self.dashboard_()
            self.dashboard_conf()
            self.configurations()
            self.main_view_pack()

        Main.main_view = self.dash.main_view 
        self.dash.create_btn.configure(command=self.change_to_register)
        self.dash.edit_btn.configure(command=self.change_to_register)
        self.dash.continue_btn.configure(command=self.change_to_CrCoApStCo)

        if Main.LASTSIDE == None:
            Main.LASTSIDE = self.dashboard
        else:
            Main.LASTSIDE.configure(
                fg_color="transparent"
            )
            self.dashboard.configure(
                fg_color="#442f7a",
            )
            Main.LASTSIDE = self.dashboard
        

    def sidebar(self):
        self.main_view_1 = CTkFrame(
            master=self,
            fg_color="#d6d4ce",
            width=1200, 
            height=1080, 
            corner_radius=0
        )

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

        self.logo_lbl = CTkLabel(
            master=self.sidebar_frame, 
            text="", 
            image=logo_img
            )
        self.sidebar_horizontal_separator_1 = ctk.CTkFrame(
            self.sidebar_frame, 
            fg_color="black", 
            height=2, 
            width=100
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
            fg_color="#442f7a", 
            font=("Arial Bold", 14),
            text_color="#fff",
            hover_color="#207244", 
            anchor="w",
            command=self.dashboard_run,
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
            anchor="w",
            command=self.change_to_documents
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
        
        plus_img = Image.open("./img/plus.png")
        plus_img = CTkImage(
            dark_image=plus_img,
            light_image=plus_img,
        )

        self.make_poster_btn = CTkButton(
            self.sidebar_frame,
            text="Create Poster",
            image=plus_img,
            compound="left",
            fg_color="transparent", 
            font=("Arial Bold", 14), 
            hover_color="#207244", 
            anchor="w",
            command=self.change_to_poster
        )

        settings_img_data = Image.open("./img/settings_icon.png")
        settings_img = CTkImage(
            dark_image=settings_img_data, 
            light_image=settings_img_data)
        
        self.settings = CTkButton(
            master=self.sidebar_frame, 
            image=settings_img, 
            text="Settings", 
            fg_color="transparent", 
            font=("Arial Bold", 14), 
            hover_color="#207244", 
            anchor="w"
            )

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
        self.main_view_1.pack(
            side='right',
        )

        self.logo_lbl.pack(
            pady=(38, 0), 
            anchor="center"
        )
        self.sidebar_horizontal_separator_1.pack(
            anchor='center',
            padx=5,
            pady=(8,0),
        )
        self.dashboard.pack(
            anchor="w", 
            ipady=5, 
            pady=(60, 0),
            padx=5,
        )

        self.making_documents.pack(
            anchor="w", 
            ipady=5, 
            pady=(16, 0),
            padx=5,
        )

        self.make_poster_btn.pack(
            anchor='w',
            ipady=5,
            pady=(16,0),
            padx=5,
        )

        self.document_history.pack(
            anchor="w", 
            ipady=5, 
            pady=(16, 0),
            padx=5,
        )

        self.settings.pack(
            anchor="w", 
            ipady=5, 
            pady=(16, 0),
            padx=5,
        )
        
        self.account.pack(
            anchor="w", 
            ipady=5, 
            pady=(160, 0),
            padx=5,
        )

        #self.main_view.pack_propagate(0)

    def last_bar(self):
        self.lower_2_frm = CTkFrame(
            self.main_view,
            fg_color='#177cff',
        )

        vroad = Image.open("./img/vroad.jpg")
        vroad = CTkImage(
            dark_image=vroad,
            light_image=vroad,
            size=(327,50)
        )

        self.footnote_8_1_lbl = CTkLabel(
            self.lower_2_frm,
            text="",
            fg_color='transparent',
            image=vroad,
            compound="left",
        )

    def last_bar_config(self):
        self.lower_2_frm.pack(
            anchor='n',
            side='top',
            padx=5,
            pady=(25,20)
        )

        self.footnote_8_1_lbl.pack(
            anchor='n',
        )


def main():
    """ configurations of root window.
    title, icon, main loop """
    global window
        
    window = Login()
    window.title("VEye. Business Management")
    
    window.mainloop()

if __name__ == "__main__":
    main()
