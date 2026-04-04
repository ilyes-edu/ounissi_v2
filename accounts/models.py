from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    pass
    # additional fields will be added here

    def __str__(self):
        return self.username

class Rank(models.Model):
    value = models.PositiveSmallIntegerField(unique=True)
    label = models.CharField(max_length=50)

    def __str__(self):
        return self.label

class Employee(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    salary_items = models.ManyToManyField("ounissi_app.SalaryItem", blank=True)
    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True, default='')
    birth_date = models.DateField(blank=True, default=None, null=True)
    recruiting_date = models.DateField(blank=True, default=None, null=True)
    social_number = models.CharField(max_length=20, null=True, blank=True)
    bank_account = models.CharField(max_length=40, null=True, blank=True)
    address = models.CharField(max_length=200, null=True, blank=True)
    position = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    zk_id = models.CharField(max_length=50, null=True, blank=True)
    xp_id = models.CharField(max_length=50, null=True, blank=True)
    rank = models.ForeignKey(Rank, on_delete=models.SET_NULL, null=True, blank=True, default=4)

    def __str__(self):
        return f" {self.first_name}"

class Team(models.Model):
    name = models.CharField(max_length=50)
    employees = models.ManyToManyField(Employee, related_name='teams')
    leader = models.OneToOneField(Employee, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name
