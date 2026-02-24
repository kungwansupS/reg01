from fastapi import HTTPException, Request


LOCAL_HOSTS = {
    "localhost",
    "::1",
    "127.0.0.1",
    "testclient",  # for automated tests via FastAPI TestClient
}


def is_local_host(host: str | None) -> bool:
    if not host:
        return False
    host_l = host.strip().lower()
    if host_l in LOCAL_HOSTS:
        return True
    if host_l.startswith("127."):
        return True
    if host_l.startswith("::ffff:127."):
        return True
    # Allow Docker internal / private networks (dev is already token-protected)
    if host_l.startswith("172.") or host_l.startswith("10.") or host_l.startswith("192.168."):
        return True
    if host_l.startswith("::ffff:172.") or host_l.startswith("::ffff:10.") or host_l.startswith("::ffff:192.168."):
        return True
    return False


def ensure_local_request(request: Request) -> None:
    client_host = request.client.host if request.client else None
    if not is_local_host(client_host):
        raise HTTPException(
            status_code=403,
            detail="Dev access is allowed only from localhost.",
        )

