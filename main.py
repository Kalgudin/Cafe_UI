# main.py — клиент кафе
import os
import threading
from datetime import datetime, timedelta

from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.properties import (
    ListProperty, StringProperty, BooleanProperty, NumericProperty
)

from api_client import ApiClient, ApiError

api = ApiClient()
HERE = os.path.dirname(os.path.abspath(__file__))
KV_PATH = os.path.join(HERE, "ui.kv")
print(f">>> Loading KV from: {KV_PATH}")
Builder.load_file(KV_PATH)
print(">>> KV loaded")


# =====================================================================
#  ПОПАПЫ
# =====================================================================
def show_popup(title, message):
    box = BoxLayout(orientation="vertical", padding=10, spacing=10)
    box.add_widget(Label(text=message, halign="center", valign="middle"))
    btn = Button(text="OK", size_hint_y=None, height=45)
    box.add_widget(btn)
    popup = Popup(title=title, content=box, size_hint=(0.85, 0.4))
    btn.bind(on_release=popup.dismiss)
    popup.open()


def confirm_popup(title, message, on_confirm):
    box = BoxLayout(orientation="vertical", padding=10, spacing=10)
    box.add_widget(Label(text=message, halign="center", valign="middle"))
    row = BoxLayout(size_hint_y=None, height=45, spacing=10)
    no = Button(text="Отмена")
    yes = Button(text="Удалить")
    row.add_widget(no)
    row.add_widget(yes)
    box.add_widget(row)
    popup = Popup(title=title, content=box, size_hint=(0.85, 0.4),
                  auto_dismiss=False)

    def _yes(*_):
        popup.dismiss()
        on_confirm()

    no.bind(on_release=popup.dismiss)
    yes.bind(on_release=_yes)
    popup.open()


# =====================================================================
#  БАЗОВЫЙ ЭКРАН
# =====================================================================
class BaseScreen(Screen):
    loading = BooleanProperty(False)
    error_text = StringProperty("")

    def run_async(self, fn, on_success, on_error=None):
        self.loading = True
        self.error_text = ""

        def worker():
            try:
                result = fn()
            except ApiError as err:
                # сохраняем err в локальную переменную, чтобы лямбда её видела
                error = err
                Clock.schedule_once(
                    lambda dt, error=error: self._done_err(error, on_error), 0)
                return
            except Exception as ex:
                error = ApiError(str(ex))
                Clock.schedule_once(
                    lambda dt, error=error: self._done_err(error, on_error), 0)
                return

            Clock.schedule_once(
                lambda dt, result=result: self._done_ok(result, on_success), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _done_ok(self, result, cb):
        self.loading = False
        if cb:
            cb(result)

    def _done_err(self, err, cb):
        self.loading = False
        self.error_text = err.message
        print(f">>> API error: {err.message}")
        if cb:
            cb(err)
        else:
            show_popup("Ошибка", err.message)

# =====================================================================
#  ЛОГИН
# =====================================================================
class LoginScreen(BaseScreen):
    def on_pre_enter(self):
        self.loading = False
        self.error_text = ""

    def do_login(self):
        print(">>> do_login called")
        phone = self.ids.phone.text.strip()
        password = self.ids.password.text.strip()
        print(f">>> phone={phone!r} pwd_len={len(password)}")

        if not phone:
            self.error_text = "Введите телефон"
            print(">>> empty phone")
            return
        if not phone.replace("+", "").isdigit():
            self.error_text = "Телефон — только цифры"
            return
        if len(phone) < 5:
            self.error_text = "Телефон слишком короткий"
            return
        if len(password) < 4:
            self.error_text = "Пароль минимум 4 символа"
            return

        def ok(user):
            print(">>> login OK:", user)
            app = App.get_running_app()
            app.user = user
            app.is_staff = bool(user.get("is_staff", False))
            self.error_text = ""
            app.root.current = "home"

        self.run_async(
            lambda: api.login(phone, password),
            ok,
            lambda e: setattr(self, "error_text", e.message),
        )

    def go_register(self):
        App.get_running_app().root.current = "register"


# =====================================================================
#  РЕГИСТРАЦИЯ
# =====================================================================
class RegisterScreen(BaseScreen):
    def on_pre_enter(self):
        self.loading = False
        self.error_text = ""

    def do_register(self):
        name = self.ids.name.text.strip()
        phone = self.ids.phone.text.strip()
        password = self.ids.password.text.strip()

        if not name:
            self.error_text = "Введите имя"
            return
        if not phone or not phone.replace("+", "").isdigit():
            self.error_text = "Телефон — только цифры"
            return
        if len(phone) < 5:
            self.error_text = "Телефон слишком короткий"
            return
        if len(password) < 4:
            self.error_text = "Пароль минимум 4 символа"
            return

        def ok(_):
            show_popup("Готово", "Аккаунт создан. Войдите.")
            App.get_running_app().root.current = "login"

        self.run_async(
            lambda: api.register(name, phone, password),
            ok,
            lambda e: setattr(self, "error_text", e.message),
        )

    def go_back(self):
        App.get_running_app().root.current = "login"


# =====================================================================
#  ГЛАВНОЕ МЕНЮ
# =====================================================================
class HomeScreen(BaseScreen):
    user_name = StringProperty("")
    user_balance = StringProperty("")

    def on_pre_enter(self):
        app = App.get_running_app()
        u = app.user or {}
        self.user_name = u.get("name", "")
        self.user_balance = str(u.get("balance_points", 0))
        if u.get("id"):
            self.run_async(
                lambda: api.get_user(u["id"]),
                self._update_user,
                lambda e: None,
            )

    def _update_user(self, fresh):
        app = App.get_running_app()
        app.user = fresh
        app.is_staff = bool(fresh.get("is_staff", False))
        self.user_name = fresh.get("name", "")
        self.user_balance = str(fresh.get("balance_points", 0))

    def go(self, name):
        App.get_running_app().root.current = name

    def logout(self):
        confirm_popup("Выход", "Выйти из аккаунта?", self._do_logout)

    def _do_logout(self):
        app = App.get_running_app()
        app.user = None
        app.cart = []
        app.is_staff = False
        app.root.current = "login"


# =====================================================================
#  ПРОФИЛЬ
# =====================================================================
class ProfileScreen(BaseScreen):
    name = StringProperty("")
    phone = StringProperty("")
    balance = StringProperty("")
    reg_date = StringProperty("")
    user_id = NumericProperty(0)

    def on_pre_enter(self):
        u = App.get_running_app().user or {}
        self.user_id = u.get("id", 0)
        self.name = u.get("name", "")
        self.phone = u.get("phone", "")
        self.balance = str(u.get("balance_points", 0))
        self.reg_date = str(u.get("registration_date", ""))[:10]

    def save(self):
        name = self.ids.name_input.text.strip()
        phone = self.ids.phone_input.text.strip()

        if not name:
            show_popup("Ошибка", "Имя не может быть пустым")
            return
        if not phone or not phone.replace("+", "").isdigit():
            show_popup("Ошибка", "Телефон — только цифры")
            return

        fields = {}
        if name != self.name:
            fields["name"] = name
        if phone != self.phone:
            fields["phone"] = phone
        if not fields:
            show_popup("Инфо", "Изменений нет")
            return

        def ok(fresh):
            App.get_running_app().user = fresh
            self.name = fresh.get("name", "")
            self.phone = fresh.get("phone", "")
            show_popup("Готово", "Профиль обновлён")

        self.run_async(lambda: api.update_user(self.user_id, **fields), ok)

    def delete_account(self):
        confirm_popup("Удаление аккаунта",
                      "Все данные будут удалены. Продолжить?",
                      self._do_delete)

    def _do_delete(self):
        def ok(_):
            App.get_running_app().user = None
            App.get_running_app().is_staff = False
            show_popup("Готово", "Аккаунт удалён")
            App.get_running_app().root.current = "login"

        self.run_async(lambda: api.delete_user(self.user_id), ok)

    def go_back(self):
        App.get_running_app().root.current = "home"


# =====================================================================
#  МЕНЮ (список)
# =====================================================================
class MenuScreen(BaseScreen):
    rv_data = ListProperty([])
    is_staff = BooleanProperty(False)

    def on_pre_enter(self):
        app = App.get_running_app()
        self.is_staff = bool(app.is_staff)
        self.load_menu()

    def load_menu(self):
        def ok(items):
            self.rv_data.clear()
            if isinstance(items, list):
                self.rv_data.extend({"item": m} for m in items)
        self.run_async(api.get_menu, ok)

    def add_to_cart(self, item):
        if not item:
            return
        if not item.get("is_available", True):
            show_popup("Недоступно", f"'{item['name']}' сейчас недоступно")
            return
        app = App.get_running_app()
        for c in app.cart:
            if c["id"] == item["id"]:
                c["qty"] += 1
                break
        else:
            app.cart.append({
                "id": item["id"],
                "name": item["name"],
                "price": item["price"],
                "qty": 1,
            })
        show_popup("Добавлено", f"'{item['name']}' в корзине")

    def open_item(self, item):
        if not App.get_running_app().is_staff:
            return
        app = App.get_running_app()
        app.selected_item = item
        app.root.current = "menu_item"

    def create_item(self):
        if not App.get_running_app().is_staff:
            return
        App.get_running_app().selected_item = None
        App.get_running_app().root.current = "menu_item"

    def go_cart(self):
        App.get_running_app().root.current = "cart"

    def go_back(self):
        App.get_running_app().root.current = "home"


# =====================================================================
#  КАРТОЧКА БЛЮДА
# =====================================================================
class MenuItemScreen(BaseScreen):
    title = StringProperty("Блюдо")

    def on_pre_enter(self):
        app = App.get_running_app()
        item = getattr(app, "selected_item", None)
        if item:
            self.title = "Редактирование"
            self.ids.name_input.text = item.get("name", "")
            self.ids.desc_input.text = item.get("description", "")
            self.ids.price_input.text = str(item.get("price", ""))
            self.ids.category_input.text = item.get("category", "")
            self.ids.available.active = bool(item.get("is_available", True))
            self.ids.delete_btn.disabled = False
        else:
            self.title = "Новое блюдо"
            self.ids.name_input.text = ""
            self.ids.desc_input.text = ""
            self.ids.price_input.text = ""
            self.ids.category_input.text = ""
            self.ids.available.active = True
            self.ids.delete_btn.disabled = True

    def save(self):
        if not App.get_running_app().is_staff:
            show_popup("Доступ", "Только персонал может менять меню")
            return

        app = App.get_running_app()
        item = getattr(app, "selected_item", None)

        name = self.ids.name_input.text.strip()
        desc = self.ids.desc_input.text.strip()
        price_s = self.ids.price_input.text.strip()
        category = self.ids.category_input.text.strip()

        if not name:
            show_popup("Ошибка", "Введите название")
            return
        if not category:
            show_popup("Ошибка", "Введите категорию")
            return
        try:
            price = float(price_s.replace(",", "."))
            if price <= 0:
                raise ValueError
        except ValueError:
            show_popup("Ошибка", "Цена должна быть числом > 0")
            return

        payload = {
            "name": name,
            "description": desc,
            "price": price,
            "category": category,
            "is_available": self.ids.available.active,
        }

        if item:
            def ok(_):
                show_popup("Готово", "Блюдо обновлено")
                App.get_running_app().root.current = "menu"
            self.run_async(
                lambda: api.update_menu_item(item["id"], **payload), ok)
        else:
            def ok(_):
                show_popup("Готово", "Блюдо создано")
                App.get_running_app().root.current = "menu"
            self.run_async(lambda: api.create_menu_item(**payload), ok)

    def delete(self):
        if not App.get_running_app().is_staff:
            show_popup("Доступ", "Только персонал может менять меню")
            return
        item = getattr(App.get_running_app(), "selected_item", None)
        if not item:
            return
        confirm_popup("Удаление", f"Удалить '{item['name']}'?",
                      self._do_delete)

    def _do_delete(self):
        item = getattr(App.get_running_app(), "selected_item", None)
        if not item:
            return

        def ok(_):
            show_popup("Готово", "Блюдо удалено")
            App.get_running_app().root.current = "menu"

        self.run_async(lambda: api.delete_menu_item(item["id"]), ok)

    def go_back(self):
        App.get_running_app().root.current = "menu"


# =====================================================================
#  КОРЗИНА
# =====================================================================
class CartScreen(BaseScreen):
    rv_data = ListProperty([])
    total_text = StringProperty("0₽")
    delivery = StringProperty("pickup")

    def on_pre_enter(self):
        self.refresh()

    def refresh(self):
        app = App.get_running_app()
        self.rv_data.clear()
        self.rv_data.extend({"item": c} for c in app.cart)
        total = sum(c["price"] * c["qty"] for c in app.cart)
        self.total_text = f"{total}₽"

    def change_qty(self, cart_item, delta):
        app = App.get_running_app()
        cart_item["qty"] += delta
        if cart_item["qty"] <= 0:
            app.cart.remove(cart_item)
        self.refresh()

    def place_order(self):
        app = App.get_running_app()
        if not app.user or not app.cart:
            show_popup("Пусто", "Добавьте блюда в корзину")
            return

        items = [{
            "menu_item_id": c["id"],
            "quantity": c["qty"],
            "drink_options": "",
        } for c in app.cart]

        payload = {
            "user_id": app.user["id"],
            "delivery_method": self.delivery,
            "items": items,
        }

        def ok(res):
            if isinstance(res, dict) and res.get("id"):
                bonus = int(res.get("total", 0) * 0.05)
                if bonus > 0:
                    try:
                        api.create_loyalty(
                            user_id=app.user["id"],
                            points=bonus,
                            operation_type="accrual",
                            order_id=res["id"],
                        )
                    except ApiError as e:
                        print(">>> loyalty error:", e.message)
            app.cart = []
            show_popup("Готово", "Заказ оформлен")
            app.root.current = "orders"

        self.run_async(lambda: api.create_order(payload), ok)

    def go_back(self):
        App.get_running_app().root.current = "menu"


# =====================================================================
#  ЗАКАЗЫ
# =====================================================================
class OrdersScreen(BaseScreen):
    rv_data = ListProperty([])
    only_mine = BooleanProperty(True)

    def on_pre_enter(self):
        self.load_orders()

    def load_orders(self):
        app = App.get_running_app()
        uid = (app.user or {}).get("id")

        def ok(items):
            self.rv_data.clear()
            if not isinstance(items, list):
                return
            if self.only_mine and uid:
                items = [o for o in items if o.get("user_id") == uid]
            self.rv_data.extend({"item": o} for o in items)

        self.run_async(api.get_orders, ok)

    def toggle_scope(self):
        self.only_mine = not self.only_mine
        self.load_orders()

    def open_order(self, order):
        if not order:
            return
        App.get_running_app().selected_order = order
        App.get_running_app().root.current = "order"

    def go_back(self):
        App.get_running_app().root.current = "home"


# =====================================================================
#  КАРТОЧКА ЗАКАЗА
# =====================================================================
class OrderScreen(BaseScreen):
    title = StringProperty("Заказ")
    total = StringProperty("")
    status = StringProperty("")
    statuses = ListProperty(
        ["new", "cooking", "delivering", "done", "cancelled"])
    order_id = NumericProperty(0)

    def on_pre_enter(self):
        order = getattr(App.get_running_app(), "selected_order", None)
        if not order:
            return
        self.order_id = order["id"]
        self.title = f"Заказ #{order['id']}"
        self.total = f"{order.get('total', 0)}₽"
        self.status = order.get("status", "new")
        self.load_details()

    def load_details(self):
        def ok(full):
            if not isinstance(full, dict):
                return
            self.total = f"{full.get('total', 0)}₽"
            self.status = full.get("status", self.status)
            items = full.get("items", [])
            self.ids.items_box.clear_widgets()
            if not items:
                self.ids.items_box.add_widget(
                    Label(text="Нет позиций", size_hint_y=None, height=30))
            for it in items:
                self.ids.items_box.add_widget(Label(
                    text=f"Блюдо {it['menu_item_id']} × "
                         f"{it['quantity']} = {it['price']}₽",
                    size_hint_y=None, height=30,
                ))
        self.run_async(lambda: api.get_order(self.order_id), ok)

    def change_status(self, new_status):
        def ok(_):
            self.status = new_status
            show_popup("Готово", f"Статус: {new_status}")
        self.run_async(
            lambda: api.update_status(self.order_id, new_status), ok)

    def delete(self):
        confirm_popup("Удаление", f"Удалить заказ #{self.order_id}?",
                      self._do_delete)

    def _do_delete(self):
        def ok(_):
            show_popup("Готово", "Заказ удалён")
            App.get_running_app().root.current = "orders"
        self.run_async(lambda: api.delete_order(self.order_id), ok)

    def go_back(self):
        App.get_running_app().root.current = "orders"


# =====================================================================
#  ИЗБРАННОЕ
# =====================================================================
class FavoritesScreen(BaseScreen):
    rv_data = ListProperty([])

    def on_pre_enter(self):
        self.load_favorites()

    def load_favorites(self):
        uid = (App.get_running_app().user or {}).get("id")
        if not uid:
            return

        def ok(items):
            self.rv_data.clear()
            if isinstance(items, list):
                self.rv_data.extend({"item": f} for f in items)
        self.run_async(lambda: api.get_favorites(uid), ok)

    def delete_fav(self, fav):
        if not fav:
            return

        def do_delete():
            def ok(_):
                self.load_favorites()
            self.run_async(lambda: api.delete_favorite(fav["id"]), ok)

        confirm_popup("Удаление",
                      f"Удалить блюдо {fav['menu_item_id']} из избранного?",
                      do_delete)

    def go_back(self):
        App.get_running_app().root.current = "home"


# =====================================================================
#  АКЦИИ
# =====================================================================
class PromotionsScreen(BaseScreen):
    rv_data = ListProperty([])

    def on_pre_enter(self):
        self.load_promotions()

    def load_promotions(self):
        uid = (App.get_running_app().user or {}).get("id")
        if not uid:
            return

        def ok(items):
            self.rv_data.clear()
            if isinstance(items, list):
                self.rv_data.extend({"item": p} for p in items)
        self.run_async(lambda: api.get_promotions(uid), ok)

    def create(self):
        self.open_form()

    def open_form(self):
        box = GridLayout(cols=2, padding=10, spacing=10)
        fields = {}
        for label, key, default in (
            ("Описание", "description", ""),
            ("Скидка %", "discount", "10"),
            ("Дней", "days", "7"),
        ):
            box.add_widget(Label(text=label))
            ti = TextInput(text=default, multiline=False)
            fields[key] = ti
            box.add_widget(ti)

        actions = BoxLayout(size_hint_y=None, height=45, spacing=10)
        cancel = Button(text="Отмена")
        ok_btn = Button(text="Создать")
        actions.add_widget(cancel)
        actions.add_widget(ok_btn)

        root = BoxLayout(orientation="vertical", padding=10, spacing=10)
        root.add_widget(box)
        root.add_widget(actions)
        popup = Popup(title="Новая акция", content=root, size_hint=(0.9, 0.6))
        cancel.bind(on_release=popup.dismiss)

        def submit(*_):
            desc = fields["description"].text.strip()
            try:
                discount = float(fields["discount"].text.replace(",", "."))
                days = int(fields["days"].text)
            except ValueError:
                show_popup("Ошибка", "Скидка и дни — числа")
                return
            if not desc:
                show_popup("Ошибка", "Введите описание")
                return
            if not (0 < discount <= 100):
                show_popup("Ошибка", "Скидка должна быть 0–100")
                return
            if days <= 0:
                show_popup("Ошибка", "Дней > 0")
                return

            uid = (App.get_running_app().user or {}).get("id")
            now = datetime.utcnow()
            payload = {
                "user_id": uid,
                "description": desc,
                "discount": discount,
                "start_date": now.isoformat(),
                "end_date": (now + timedelta(days=days)).isoformat(),
            }

            def ok(_):
                popup.dismiss()
                self.load_promotions()
                show_popup("Готово", "Акция создана")

            self.run_async(lambda: api.create_promotion(**payload), ok)

        ok_btn.bind(on_release=submit)
        popup.open()

    def delete_promo(self, promo):
        if not promo:
            return

        def do_delete():
            def ok(_):
                self.load_promotions()
            self.run_async(lambda: api.delete_promotion(promo["id"]), ok)

        confirm_popup("Удаление",
                      f"Удалить акцию '{promo['description']}'?", do_delete)

    def go_back(self):
        App.get_running_app().root.current = "home"


# =====================================================================
#  БОНУСЫ
# =====================================================================
class LoyaltyScreen(BaseScreen):
    rv_data = ListProperty([])

    def on_pre_enter(self):
        self.load_loyalty()

    def load_loyalty(self):
        uid = (App.get_running_app().user or {}).get("id")
        if not uid:
            return

        def ok(items):
            self.rv_data.clear()
            if isinstance(items, list):
                self.rv_data.extend({"item": l} for l in items)
        self.run_async(lambda: api.get_loyalty(uid), ok)

    def go_back(self):
        App.get_running_app().root.current = "home"


# =====================================================================
#  ПРИЛОЖЕНИЕ
# =====================================================================
class CafeApp(App):
    user = None
    selected_item = None
    selected_order = None
    cart = []
    is_staff = False

    def build(self):
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(RegisterScreen(name="register"))
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(ProfileScreen(name="profile"))
        sm.add_widget(MenuScreen(name="menu"))
        sm.add_widget(MenuItemScreen(name="menu_item"))
        sm.add_widget(CartScreen(name="cart"))
        sm.add_widget(OrdersScreen(name="orders"))
        sm.add_widget(OrderScreen(name="order"))
        sm.add_widget(FavoritesScreen(name="favorites"))
        sm.add_widget(PromotionsScreen(name="promotions"))
        sm.add_widget(LoyaltyScreen(name="loyalty"))
        return sm


if __name__ == "__main__":
    CafeApp().run()