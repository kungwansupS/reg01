"""REG-01 Backend entrypoint."""

from .core.app_factory import create_asgi_app

asgi_app, app, sio, runtime = create_asgi_app()
