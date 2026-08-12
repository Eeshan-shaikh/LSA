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

class LSASearchQuerySerializer(serializers.Serializer):
    skill = serializers.CharField(required=False, allow_blank=True)
    start_time = serializers.DateTimeField(required=False)
    end_time = serializers.DateTimeField(required=False)
    
    def validate(self, data):
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        if (start_time and not end_time) or (end_time and not start_time):
            raise serializers.ValidationError({"error": "start_time and end_time must be provided together."})
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError({"error": "start_time must be before end_time."})
        return data

class BookingRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking_Request
        fields = ['id', 'parent', 'lsa', 'start_time', 'end_time', 'status']
        read_only_fields = ['status']
        
    def validate(self, data):
        """
        Validate that the booking start time is before the end time.
        """
        start_time = data['start_time']
        end_time = data['end_time']

        if start_time >= end_time:
            raise serializers.ValidationError({"error": "start_time must be before end_time"})
            
        return data
