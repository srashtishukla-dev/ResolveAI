from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers


User = get_user_model()


class CustomerRegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, trim_whitespace=True)
    email = serializers.EmailField(max_length=254)
    username = serializers.CharField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(write_only=True, min_length=1)
    password_confirmation = serializers.CharField(write_only=True, min_length=1)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('A user with this username already exists.')
        return value

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirmation']:
            raise serializers.ValidationError({
                'password_confirmation': 'Passwords do not match.',
            })

        password_user = User(
            username=attrs['username'],
            email=attrs['email'],
            first_name=attrs['name'],
        )
        try:
            validate_password(attrs['password'], user=password_user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({
                'password': exc.messages,
            }) from exc
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirmation')
        try:
            with transaction.atomic():
                return User.objects.create_user(
                    username=validated_data['username'],
                    email=validated_data['email'],
                    first_name=validated_data['name'],
                    password=validated_data['password'],
                    is_staff=False,
                    is_superuser=False,
                )
        except IntegrityError as exc:
            raise serializers.ValidationError({
                'detail': 'The account could not be created because the username is already in use.',
            }) from exc
