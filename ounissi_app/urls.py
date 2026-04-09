from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import TemplateView
from . import views
import accounts.views

urlpatterns = [
    # path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path('home/', views.testconn, name='homeold'),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    # Timesheet URLs
    path('attendance-logs/', views.attendance_logs, name='attendance_logs'),
    path('attendance-logs/save-data/', views.save_data, name='save_data'),
    path('timesheets/', views.timesheet_list, name='timesheet_list'),
    # path('timesheets/create/', views.timesheet_create, name='timesheet_form'),
    path('timesheets/update_timesheet/<int:pk>/', views.timesheet_update, name='update_timesheet'),
    # path('timesheets/delete/<int:pk>/', views.timesheet_delete, name='timesheet_delete'),
    # Salary Item URLs
    path('salary_items/', views.salary_item_list, name='salary_item_list'),
    path('salary/add-update-salary/', views.add_update_salary, name='add_update_salary'),
    # path('salary_items/create/', views.salary_item_create, name='salary_item_create'),
    # path('salary_items/update/<int:pk>/', views.salary_item_update, name='salary_item_update'),
    # path('salary_items/delete/<int:pk>/', views.salary_item_delete, name='salary_item_delete'),

    # Salaries URLs
    path('salaries/', views.salary_list, name='salary_list'),
    path('get_salary_details/<int:salary_id>/', views.get_salary_details, name='get_salary_details'),
    # path('calculate_amount/', views.calculate_amount, name='calculate_amount'),
    path('save_salary_details/', views.save_salary_details, name='save_salary_details'),

    # Schedules URLs
        #Schedule Detail1 Followup
    path('schedule/', views.schedule_details, name='schedule_details'),
    path('schedule/actual/', views.actual_schedule_details, name='actual_schedule_details'),
    path('update_schedule_now/<int:schedule_id>', views.update_schedule_now, name='update_schedule_now'),
    path('schedule/<int:schedule_id>/', views.schedule_details, name='schedule_details_selected'),
    path('schedule/scheduleItem_update/<int:pk>', views.scheduleItem_update, name='scheduleItem_update'),
    path('schedule/create_schedule/', views.create_schedule, name='create_schedule'),
    path('finalize_schedule/<int:schedule_id>/', views.finalize_schedule, name='finalize_schedule'),
    path('unfinished_tasks/<int:schedule_id>/', views.handle_unfinished_tasks, name='unfinished_tasks'),
    path('import_tasks/', views.import_tasks, name='import_tasks'),

    #Schedule Detail2 Planning
    path('schedule/plan', views.schedule_details2, name='schedule_details2'),
    path('schedule/plan/<int:schedule_id>/', views.schedule_details2, name='schedule_details_with_id'),

    # path('schedule/select_schedule/', views.schedule_select_view, name='select_schedule'),
    path('schedule/schedule_items/<int:schedule_id>/', views.schedule_items_for_schedule, name='schedule_items'),
    path('schedule/add_or_edit_schedule_item', views.add_or_edit_schedule_item, name='add_or_edit_schedule_item'),

    # Employees URLs
    path('employees/', accounts.views.employee_list, name='employee_list'),

    #Tasks URLs
    path('tasks/', views.tasks_list, name='task_list'),
    path('tasks/task_create/', views.create_task, name='create_task'),
    # path('tasks/task_performance/', views.TaskPerformanceView.as_view(), name='task_performance'),
    # path ('tasks/distribute_tasks/', views.distribute_tasks, name = 'distribute_tasks'),
    path('get_filtered_employees/', views.get_filtered_employees, name='get_filtered_employees'),
    path('get_model_form', views.get_model_form, name='get_model_form'),
    # path('tasks/create_reception/', views.reception_view, name='create_reception'),
    path('submit_form/<str:form_class_name>/', views.generic_form_submission_view, name='generic_form_submission'),

    # Special Forms
    path('get_special_form', views.get_special_form, name='get_special_form'),
    path('form_saisie', views.special_form_saisie, name='form_saisie'),
    path('form_reception_produit', views.special_form_produit, name='form_reception_produit'),
    path('form_reception_vignette', views.special_form_vignette, name='form_reception_vignette'),
    path('form_reception_placement', views.special_form_placement, name='form_reception_placement'),

    #Queries URLs
    path('queries/', views.test_queries, name='test_queries'),

    # path('queries/', views.queries_list, name='queries_list'),
    path('queries/create_query/', views.create_query, name='create_query'),
    path('queries/test_query_submission/', views.test_query_submission, name='test_query_submission'),
    path('queries/execute_query/', views.execute_query, name='execute_query'),
    path('get_query_details/<int:query_id>/', views.get_query_details, name='get_query_details'),
    # users URLs
    path('', views.schedule_current, name='home'),
    path('history/schedules', views.user_schedules_history, name='user_schedule_history'),

    #Stock URLs
    path('stock/', views.get_stock, name='etat_stocks'),
    path('stock/emplacements/', views.get_emplacements, name='emplacements'),
    path('stock/assign_stock/', views.assign_stock, name='assign_stock'),
    path('stock/assign_stock/delete_assignment/<int:assignment_Id>/', views.delete_assignment, name='delete_assignment'),

]
