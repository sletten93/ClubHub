from whitenoise.storage import CompressedManifestStaticFilesStorage


class StaticStorage(CompressedManifestStaticFilesStorage):
    """Manifest storage with gzip/brotli precompression and hashed filenames.

    Falls back to the plain, unhashed URL whenever a name can't be resolved
    from the manifest — dev server and tests never run collectstatic, so the
    manifest simply doesn't exist there. After `collectstatic` every lookup
    resolves to a hashed, immutable URL; a missing entry then degrades to the
    unhashed URL instead of 500-ing the page (same defensive posture as
    clubs.utils.build_theme).
    """

    manifest_strict = False

    def stored_name(self, name):
        try:
            return super().stored_name(name)
        except ValueError:
            return name
