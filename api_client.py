# api_client.py
import requests

# Для Android-эмулятора с локальным API: http://10.0.2.2:8000
# Для реального телефона в той же Wi-Fi: http://192.168.x.x:8000
# BASE_URL = "https://cafe-api-wmag.onrender.com"
BASE_URL = "http://127.0.0.1:8000"


class ApiError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.message = message
        self.status = status


class ApiClient:
    def __init__(self, base_url=BASE_URL):
        self.base = base_url.rstrip("/")
        self.session = requests.Session()

    def _req(self, method, path, **kw):
        url = f"{self.base}{path}"
        try:
            r = self.session.request(method, url, timeout=20, **kw)
        except requests.RequestException as e:
            raise ApiError(f"Нет соединения с сервером: {e}")

        if r.status_code == 204:
            return None

        try:
            data = r.json() if r.text else {}
        except ValueError:
            data = {"detail": r.text}

        if r.status_code >= 400:
            detail = data.get("detail") if isinstance(data, dict) else str(data)
            if isinstance(detail, list):
                detail = "; ".join(
                    f"{'.'.join(map(str, e.get('loc', [])))}: {e.get('msg', '')}"
                    for e in detail
                )
            raise ApiError(str(detail), r.status_code)
        return data

    # ---------- AUTH ----------
    def register(self, name, phone, password):
        return self._req("POST", "/users",
                         json={"name": name, "phone": phone, "password": password})

    def login(self, phone, password):
        return self._req("POST", "/login",
                         json={"phone": phone, "password": password})

    # ---------- USERS ----------
    def get_users(self):
        return self._req("GET", "/users")

    def get_user(self, uid):
        return self._req("GET", f"/users/{uid}")

    def update_user(self, uid, **fields):
        return self._req("PATCH", f"/users/{uid}", json=fields)

    def delete_user(self, uid):
        return self._req("DELETE", f"/users/{uid}")

    # ---------- MENU ----------
    def get_menu(self):
        return self._req("GET", "/menu")

    def get_menu_item(self, iid):
        return self._req("GET", f"/menu/{iid}")

    def create_menu_item(self, **f):
        return self._req("POST", "/menu", json=f)

    def update_menu_item(self, iid, **f):
        return self._req("PATCH", f"/menu/{iid}", json=f)

    def delete_menu_item(self, iid):
        return self._req("DELETE", f"/menu/{iid}")

    # ---------- ORDERS ----------
    def get_orders(self):
        return self._req("GET", "/orders")

    def get_order(self, oid):
        return self._req("GET", f"/orders/{oid}")

    def create_order(self, payload):
        return self._req("POST", "/orders", json=payload)

    def update_status(self, oid, status):
        return self._req("PATCH", f"/orders/{oid}/status",
                         json={"status": status})

    def delete_order(self, oid):
        return self._req("DELETE", f"/orders/{oid}")

    # ---------- FAVORITES ----------
    def add_favorite(self, uid, iid):
        return self._req("POST", "/favorites",
                         json={"user_id": uid, "menu_item_id": iid})

    def get_favorites(self, uid):
        return self._req("GET", f"/favorites/{uid}")

    def delete_favorite(self, fid):
        return self._req("DELETE", f"/favorites/{fid}")

    # ---------- PROMOTIONS ----------
    def get_promotions(self, uid):
        return self._req("GET", f"/promotions/{uid}")

    def create_promotion(self, **f):
        return self._req("POST", "/promotions", json=f)

    def delete_promotion(self, pid):
        return self._req("DELETE", f"/promotions/{pid}")

    # ---------- LOYALTY ----------
    def get_loyalty(self, uid):
        return self._req("GET", f"/loyalty/{uid}")

    def create_loyalty(self, **f):
        return self._req("POST", "/loyalty", json=f)