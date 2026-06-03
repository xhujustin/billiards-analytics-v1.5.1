import mimetypes
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


class SupabaseStorageError(RuntimeError):
    """Raised when Supabase Storage rejects or cannot complete an upload."""


@dataclass(frozen=True)
class SupabaseStorageConfig:
    url: str
    service_role_key: str
    bucket: str

    @classmethod
    def from_env(cls) -> "SupabaseStorageConfig | None":
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "community-uploads").strip()
        if not url or not service_role_key or not bucket:
            return None
        return cls(url=url, service_role_key=service_role_key, bucket=bucket)


class SupabaseStorageClient:
    def __init__(self, config: SupabaseStorageConfig):
        self.config = config

    def upload_public_object(
        self,
        object_path: str,
        content: bytes,
        mime_type: str,
        *,
        upsert: bool = False,
    ) -> str:
        safe_path = object_path.strip().lstrip("/")
        if not safe_path:
            raise SupabaseStorageError("Supabase object path is empty.")
        if not content:
            raise SupabaseStorageError("Supabase upload content is empty.")

        encoded_path = parse.quote(safe_path, safe="/")
        endpoint = f"{self.config.url}/storage/v1/object/{parse.quote(self.config.bucket, safe='')}/{encoded_path}"
        headers = self._auth_headers()
        headers.update({
            "Content-Type": mime_type or mimetypes.guess_type(safe_path)[0] or "application/octet-stream",
            "x-upsert": "true" if upsert else "false",
        })
        upload_request = request.Request(endpoint, data=content, headers=headers, method="POST")
        try:
            with request.urlopen(upload_request, timeout=20) as response:
                if response.status >= 400:
                    raise SupabaseStorageError(f"Supabase upload failed with HTTP {response.status}.")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise SupabaseStorageError(f"Supabase upload failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabaseStorageError(f"Supabase upload failed: {exc}") from exc

        return self.public_url(safe_path)

    def _auth_headers(self) -> dict[str, str]:
        key = self.config.service_role_key
        headers = {"apikey": key}
        if not key.startswith("sb_"):
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def public_url(self, object_path: str) -> str:
        encoded_path = parse.quote(object_path.strip().lstrip("/"), safe="/")
        encoded_bucket = parse.quote(self.config.bucket, safe="")
        return f"{self.config.url}/storage/v1/object/public/{encoded_bucket}/{encoded_path}"


def configured_supabase_storage_client() -> SupabaseStorageClient | None:
    config = SupabaseStorageConfig.from_env()
    return SupabaseStorageClient(config) if config else None


def supabase_storage_status() -> dict[str, Any]:
    config = SupabaseStorageConfig.from_env()
    return {
        "enabled": config is not None,
        "bucket": config.bucket if config else os.getenv("SUPABASE_STORAGE_BUCKET", "community-uploads"),
    }
