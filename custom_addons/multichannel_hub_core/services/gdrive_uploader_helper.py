"""Thin helper around GdriveUploader for catalog Excel fetching.

Spec 010 P-HUB-XLS-GDRIVE-FETCHER. Avoids importing GdriveUploader at
module-load time so its googleapiclient dependency doesn't block other
mhc imports if the GDrive lib is missing in the deploy.
"""


def fetch_gdrive_bytes(env, file_id):
    """Download a GDrive file's bytes via the existing GdriveUploader.

    Lazy-imports to keep this module load-cheap.

    Raises whatever GdriveUploader raises (HttpError, auth errors, etc.) —
    the caller wraps in try/except for cron survivability.
    """
    from .gdrive_uploader import GdriveUploader
    uploader = GdriveUploader(env)
    return uploader.download_file(file_id)
