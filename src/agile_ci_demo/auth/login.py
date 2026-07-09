def test_login_page_renders(client: TestClient) -> None:
    r = client.get("/auth/login")
    assert r.status_code == 200