from django.contrib.auth.models import User
from django.test import TestCase
from . import models as m


class SkillCategoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_superuser("boss", "b@x.test", "Str0ng-pass-123")

    def setUp(self):
        self.client.login(username="boss", password="Str0ng-pass-123")

    def test_custom_category_and_grouping(self):
        self.client.post("/cms/skills/new/", {"name": "Figma", "category": "Design"})
        self.client.post(
            "/cms/skills/new/", {"name": "Sketch", "category": "  design "}
        )  # same group, different case/space
        r = self.client.post(
            "/cms/skills/new/", {"name": "Go", "category": ""}
        )  # category is required
        self.assertEqual(r.status_code, 200)
        cats = list(m.Skill.objects.order_by("id").values_list("category", flat=True))
        self.assertEqual(cats, ["Design", "Design"])
        home = self.client.get("/").content.decode()
        self.assertEqual(home.count("<h3>Design</h3>"), 1)
        self.assertIn("Figma", home)
        self.assertIn("Sketch", home)

    def test_form_offers_existing_and_preset_categories(self):
        m.Skill.objects.create(name="Figma", category="Design")
        page = self.client.get("/cms/skills/new/").content.decode()
        self.assertIn('id="category-options"', page)
        self.assertIn('<option value="Design">', page)
        self.assertIn('<option value="Backend">', page)

    def test_list_filter_and_search_by_category(self):
        m.Skill.objects.create(name="Figma", category="Design")
        m.Skill.objects.create(name="Go", category="Backend")
        page = self.client.get("/cms/skills/?f=Design").content.decode()
        self.assertIn("Figma", page)
        self.assertNotIn(">Go<", page)
        self.assertIn("Figma", self.client.get("/cms/skills/?q=desig").content.decode())
