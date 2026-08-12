from rest_framework import serializers
from .models import Parent, Skill, LSA_Profile, Booking_Request, Payment

class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name']

class LSASerializer(serializers.ModelSerializer):
    skills = SkillSerializer(many=True, read_only=True)
    
    class Meta:
        model = LSA_Profile
        fields = ['id', 'name', 'skills']

class BookingRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking_Request
        fields = ['id', 'parent', 'lsa', 'start_time', 'end_time', 'status']
        read_only_fields = ['status']
        
    def validate(self, data):
        """
        Check that start is before end and prevent overlapping bookings.
        """
        start_time = data['start_time']
        end_time = data['end_time']
        lsa = data['lsa']

        if start_time >= end_time:
            raise serializers.ValidationError({"error": "start_time must be before end_time"})

        # Check for double-booking / overlapping bookings
        overlapping_bookings = Booking_Request.objects.filter(
            lsa=lsa,
            status__in=['PENDING', 'CONFIRMED'],
            start_time__lt=end_time,
            end_time__gt=start_time
        )
        
        if overlapping_bookings.exists():
            raise serializers.ValidationError({"error": "LSA is already booked for this time slot."})
            
        return data
