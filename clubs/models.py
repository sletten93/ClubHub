from django.conf import settings
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models

HEX_COLOR_VALIDATOR = RegexValidator(
    regex=r"^#[0-9a-fA-F]{6}$", message="Enter a color as #RRGGBB."
)

IMAGE_EXTENSION_VALIDATOR = FileExtensionValidator(["png", "jpg", "jpeg", "webp"])


class Club(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100, unique=True)
    organisation_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    street_address = models.CharField(max_length=200, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)
    city = models.CharField(max_length=100, blank=True)
    primary_color = models.CharField(
        max_length=7, default="#0d6efd", validators=[HEX_COLOR_VALIDATOR]
    )
    secondary_color = models.CharField(
        max_length=7, default="#212529", validators=[HEX_COLOR_VALIDATOR]
    )
    logo = models.ImageField(
        upload_to="club_logos/", null=True, blank=True, validators=[IMAGE_EXTENSION_VALIDATOR]
    )
    background_image = models.ImageField(
        upload_to="club_backgrounds/",
        null=True,
        blank=True,
        validators=[IMAGE_EXTENSION_VALIDATOR],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """Per-login-account preferences (clubs belong to persons, but settings
    like language follow the User, which may exist without a Person)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    # Empty means "use the system default" (settings.CLUBHUB_LANGUAGE).
    language = models.CharField(max_length=10, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.get_username()
