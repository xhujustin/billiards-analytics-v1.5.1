"""API package marker.

Do not import routers here. Cloud Run mobile-lite imports only selected API
modules and must not load replay/camera dependencies such as OpenCV.
"""

__all__: list[str] = []
