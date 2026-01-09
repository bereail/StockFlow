from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    # TONER #
    path("toner/", views.toner_page, name="toner_page"),
    path("toner/lista/", views.toner_list, name="toner_list"),  
    path("toner/entrega/", views.toner_entrega, name="toner_entrega"),
    path("toner/nuevo/", views.toner_create, name="toner_create"),
    path("toner/<int:pk>/editar/", views.toner_edit, name="toner_edit"),
    path("toner/<int:pk>/toggle/", views.toner_toggle, name="toner_toggle"),
    path("toner/historial/", views.toner_historial, name="toner_historial"),

    path("toner/backup/entregas.csv", views.backup_entregas_csv, name="backup_entregas_csv"),

    # ARTICULOS # 
    path("articulos/", views.articulos_page, name="articulos_page"),
    path("articulos/", views.articulos_page, name="articulos_page"),
    path("articulos/nuevo/", views.articulo_create, name="articulo_create"),
    path("articulos/<int:pk>/editar/", views.articulo_edit, name="articulo_edit"),
    path("articulos/<int:pk>/toggle/", views.articulo_toggle, name="articulo_toggle"),
    path("articulos/entrega/", views.articulo_entrega, name="articulo_entrega"),
    path("articulos/historial/", views.articulos_historial, name="articulos_historial"),
    path("articulos/backup/entregas.csv", views.backup_articulos_csv, name="backup_articulos_csv"),


    path("pcs/", views.pcs_page, name="pcs_page"),
    path("servicios/", views.servicios_page, name="servicios_page"),
]

