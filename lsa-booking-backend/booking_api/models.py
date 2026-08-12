from django.db import models
from django.utils import timezone

class Parent(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.name

class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class LSA_Profile(models.Model):
    name = models.CharField(max_length=255)
    skills = models.ManyToManyField(Skill, related_name='lsas')
    
    def __str__(self):
        return self.name

class Booking_Request(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
    ]

    parent = models.ForeignKey(Parent, on_delete=models.CASCADE, related_name='bookings')
    lsa = models.ForeignKey(LSA_Profile, on_delete=models.CASCADE, related_name='bookings')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    class Meta:
        indexes = [
            models.Index(fields=['lsa', 'status', 'start_time', 'end_time']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(start_time__lt=models.F('end_time')),
                name='check_start_time_before_end_time'
            )
        ]

    def __str__(self):
        return f"{self.parent.name} booked {self.lsa.name} from {self.start_time} to {self.end_time}"

class Payment(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]
    booking = models.OneToOneField(Booking_Request, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Payment for booking {self.booking.id} - {self.status}"
