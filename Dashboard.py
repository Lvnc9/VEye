import customtkinter as ctk
from customtkinter import *
from CTkTable import CTkTable
from PIL import Image
#from main import change_to_register

class Dashboard:

    def __init__(self, parent):
        self.parent = parent
        #self.login()
        #self.sidebar()
        self.main_page()
        self.dashboard_()
        #self.dashboard_conf()
        #self.configurations()
        #self.main_view_pack()

    def run():
        pass

    def sidebar(self):
        self.sidebar_frame = CTkFrame(
            master=self.parent, 
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
        self.user_lbl.pack(
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
            text="Managment Dashboard",
            text_color='#fff',
            font=("Arial Bold", 14),
        )

        self.user_lbl = CTkLabel(
            master=self.title_frame,
            text="Access: CEO",
            text_color='#fff',
            font=("Arial Bold", 14),
        )

    def dashboard_(self):
        logitics_img_data = Image.open("./img/edit1.png")
        logistics_img = CTkImage(
            light_image=logitics_img_data, 
            dark_image=logitics_img_data, 
            size=(43, 43)
        )

        self.system_info = CTkFrame(
            master=self.main_view, 
            height=450,
            fg_color="#F0F0F0"
        )
        
        self.metrics_frame = CTkFrame(
            master=self.system_info, 
            fg_color="transparent"
            )

        self.orders_metric = CTkFrame(
            master=self.metrics_frame, 
            fg_color="#2A8C55", 
            width=250, 
            height=70
            )

        self.firstItem = CTkLabel(
            master=self.orders_metric, 
            image=logistics_img, 
            text=""
        )
        
        self.second_item = CTkLabel(
            master=self.orders_metric,
            text="System Information:", 
            text_color="#fff", 
            font=("Arial Black", 15))
        
        self.third_item = CTkLabel(
            master=self.orders_metric, 
            text="share holders - personnel - levels", 
            text_color="#fff",
            font=("Arial Black", 9), 
            justify="left"
            )

        
        self.info_system_lbl = CTkLabel(
            master=self.system_info,
            text="System Information:",
            font=("Arial Black", 15),
            justify="left"
        )

        logitics_img_data = Image.open("./img/edit1.png")
        logistics_img = CTkImage(
            light_image=logitics_img_data, 
            dark_image=logitics_img_data, 
            size=(43, 43)
        )
        
        edit_img_data = Image.open("./img/table1.png")
        edit_img = CTkImage(
            light_image=logitics_img_data, 
            dark_image=logitics_img_data, 
            size=(43, 43)
        )
        self.create_btn = CTkButton(
            master=self.system_info,    
            text="Create Personnel Profile",
            hover_color="#207244", 
            #anchor="w",
            #image=logistics_img,
            #command=change_to_register
        )


        self.edit_btn = CTkButton(
            master=self.system_info,
            text="Edit Personnel Profile",
            hover_color="#207244", 
            anchor='center',
            width=50,
            #command=change_to_register
            #image=edit_img,
        )

        self.continue_btn = CTkButton(
            master=self.system_info,
            text="continue",
            hover_color="#207244", 
            anchor='center',
        )
        table_data = [
            ["Kind of Letter", "Pish Nevis", "Waiting for Confirmation", "Wating for Approval", "Under Control", "demode"],
            ['Poster', '2', '2', '4', '4', '3'],
            ['Implementation', '3', '1', '2', '7', '2'],
            ['instructions', '1', '2', '4', '2', '4'],
            ['Form', '3', '3', '2', '15', '17'],
        ]

        self.titles_ = CTkFrame(
            master=self.main_view, 
            height=50, 
            fg_color="#F0F0F0"
            )
        

        self.documentCtrl_lbl = CTkLabel(
            master=self.titles_, 
            text="Control Documents",
            text_color="#000000",
            )

        self.continue_btn = CTkButton(
            master=self.titles_, 
            border_color="#2f3dde", 
            text="Continue"
            )
        
        self.table_frame = CTkScrollableFrame(
            master=self.main_view, 
            fg_color="transparent",
        )
        
        self.table = CTkTable(
            master=self.table_frame, 
            values=table_data,
            text_color="#000000",
            colors=["#E6E6E6", "#EEEEEE"], 
            header_color="#2A8C55", 
            hover_color="#B4B4B4", 
            )
            
        self.table.edit_row(
            0, 
            text_color="#fff", 
            hover_color="#2A8C55"
        )
        self.table.edit_column(
            0, 
            text_color="#fff", 
            fg_color="#2A8C55"
        )
        baravord = Image.open("./img/vroad.png")
        baravord = CTkImage(
            dark_image=baravord,
            light_image=baravord,
            size=(600,180)
        )
        self.explain_8_2_frm = CTkFrame(
            self.main_view,
            fg_color="#000000",
        )
        self.footnote_8_1_lbl = CTkLabel(
            self.explain_8_2_frm,
            text="",
            image=baravord,
            compound="left",
        )
    def dashboard_conf(self):
        self.title_frame.pack(
            anchor="n", 
            fill="x",  
            padx=27, 
            pady=(29, 0)
            )
        self.system_info.pack(
            fill="x", 
            pady=(45, 0), 
            padx=27
        )

        self.metrics_frame.pack(
            anchor="n", 
            fill="x", 
            padx=15, 
            pady=(10, 0)
            )
        self.orders_metric.grid_propagate(0)
        self.orders_metric.pack(side="left")

        self.firstItem.grid(
            row=0, 
            column=0, 
            rowspan=2, 
            padx=(12,5), 
            pady=10
            )

        self.second_item.grid(
            row=0, 
            column=1, 
            sticky="sw"
        )

        self.third_item.grid(
            row=1, 
            column=1, 
            sticky="nw", 
            pady=(0,10)
        )


        self.create_btn.pack(
            side="left", 
            padx=(13, 0), 
            pady=30,
            anchor="w"
            )

        self.edit_btn.pack(
            side="left", 
            padx=(13, 0), 
            pady=8,
            anchor="w"
            )

        self.continue_btn.pack(
            side="left", 
            padx=(13, 0), 
            pady=8,
            anchor="w"
        )
        self.titles_.pack(
            fill="x", 
            pady=(45, 0), 
            padx=27
            )
        
        self.documentCtrl_lbl.pack(
            side="left", 
            padx=(13, 0), 
            pady=8,
            anchor="w"
            )
        self.continue_btn.pack(
            side='right',
            padx=10,
            pady=8,
            anchor='e'
        )
        self.table_frame.pack(
            expand=True, 
            fill="both", 
            padx=27, 
            pady=20
            )
        self.table.pack(
            expand=True, 
            side='left',
            anchor='s'
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
        self.main_view.pack(
            side="right"
            )


        self.title_frame.pack(
            anchor="w",
            fill="x",
            expand=True,
            padx=27, 
            )
        #self.title_lbl.pack(
        #    anchor="n", 
        #    side="top",
        #    fill='x',
        #    pady=(35,10),
        #    padx=(27, 40),
        #)
        self.title_lbl.grid(
            row=0,
            column=1,
            #pady=(35,10),
            padx=(27, 40),
        )

        self.center_titles_frm.grid(
            row=0,
            column=0,
            pady=(70,10),
            padx=5
        )
        
        #self.section_lbl.pack(
        #    anchor='w',
        #    side='right',
        #    pady=(35,10),
        #    padx=(27, 40),
        #)
        self.section_lbl.grid(
            row=0,
            column=2,
            pady=(70,10),
            padx=(27, 40),
        )
        self.title_lbl.pack(
            anchor='w',
            side='right',
        )
        #self.user_lbl.pack(
        #    anchor='w',
        #    
        #)

def main():
    """ configurations of root window.
    title, icon, main loop """
    global window 

    #root = tb.Window(
    #    themename="vapor"
    #)

    window = Dashboard()
    window.geometry("1080x645")
    window.mainloop()

if __name__ == "__main__":
    main()
