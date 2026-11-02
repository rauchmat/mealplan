"""Offline compatibility checks of the existing weekly shopping contract."""
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("servings", [2, 3, 4])
def test_bring_contract(servings):
    week = json.loads((ROOT / "data/2026-W45.json").read_text())
    soup = BeautifulSoup((ROOT / f"bring/2026-W45-{servings}.html").read_text(), "html.parser")
    recipe = json.loads(soup.select_one('script[type="application/ld+json"]').string)
    assert recipe["@type"] == "Recipe"
    assert recipe["recipeYield"] == f"{servings} Portionen pro Gericht"
    assert soup.select_one('script[src="https://platform.getbring.com/widgets/import.js"]')
    assert soup.select_one("[data-bring-import]")
    link = soup.select_one('a[href^="https://api.getbring.com/rest/bringrecipes/deeplink"]')["href"]
    assert parse_qs(urlsplit(link).query)["url"] == [recipe["url"]]
    displayed = [li.get_text() for li in soup.select(".ingredient-list li")]
    assert displayed == recipe["recipeIngredient"]
    assert len(displayed) == len(week["ingredients"])
    for line, (_, name, amount, unit) in zip(displayed, week["ingredients"]):
        if amount is None:
            assert line == name
        else:
            match = re.match(r"([\d\s\u00a0.,]+) " + re.escape(unit + " " + name) + r"$", line)
            assert match
            number = float(re.sub(r"[\s\u00a0]", "", match[1]).replace(",", "."))
            assert number == pytest.approx(amount * servings / 3, abs=.051)


def test_week_links_and_existing_data_contract():
    settings = json.loads((ROOT / "data/settings.json").read_text())
    index = json.loads((ROOT / "data/weeks.json").read_text())
    for item in index:
        week = json.loads((ROOT / "data" / (item["id"] + ".json")).read_text())
        assert len(week["meals"]) == 5
        assert [m[0] for m in week["meals"]] == settings["days"]
        assert sum(m[2] in {"Vegetarisch", "Vegan"} for m in week["meals"]) >= settings["minVegetarianMeals"]
        page = ROOT / item["url"]
        assert page.exists()
        soup = BeautifulSoup(page.read_text(), "html.parser")
        assert (page.parent / soup.select_one("#bring")["href"]).exists()
        for portions in range(settings["minServings"], settings["maxServings"] + 1):
            assert (ROOT / "bring" / f'{item["id"]}-{portions}.html').exists()
