"""Only extract facts present in structured data or explicitly supported HTML."""
import json
import math
import re
from html import unescape
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
import extruct
from lxml import etree

from .urls import clean_url, platform, UnsafeURL

FIELDS = ("title", "ingredients", "servings", "yield_text", "prep_minutes", "cook_minutes", "total_minutes", "category", "tags", "instructions")


def text(value):
    if value is None:
        return None
    value = str(value)
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True) if "<" in value else unescape(value).strip()


def strings(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [s for x in value for s in strings(x)]
    if isinstance(value, dict):
        return strings(value.get("itemListElement") or value.get("text") or value.get("name") or value.get("@value") or value.get("@id"))
    return [text(value)] if text(value) else []


def minutes(value):
    if isinstance(value, (list, dict)):
        value = " ".join(strings(value))
    if not isinstance(value, str):
        return None
    m = re.fullmatch(r"P(?:(\d+(?:\.\d+)?)D)?(?:T(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?)?", value)
    if not m or not any(m.groups()):
        return None
    d, h, mins, sec = [float(x or 0) for x in m.groups()]
    result = d * 1440 + h * 60 + mins + sec / 60
    return result if math.isfinite(result) else None


def servings(value):
    # Do not interpret "12 cookies", "2–4" or "one loaf" as people/servings.
    s = " ".join(strings(value))
    m = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(?:Portion(?:en)?|Person(?:en)?|servings?)?\s*", s, re.I)
    number = float(m[1].replace(",", ".")) if m else 0
    return number if number > 0 and math.isfinite(number) else None


def recipe_nodes(value):
    if isinstance(value, list):
        for x in value:
            yield from recipe_nodes(x)
    elif isinstance(value, dict):
        types = value.get("@type", value.get("type", []))
        types = [types] if isinstance(types, str) else types if isinstance(types, list) else []
        if any(re.split(r"[/#]", str(t))[-1] == "Recipe" for t in types or []):
            yield value.get("properties", value)
        for key in ("@graph", "mainEntity", "itemListElement"):
            yield from recipe_nodes(value.get(key))


def expand_schema(value):
    """Resolve only references inside this document, never remote JSON-LD contexts."""
    nodes = {}
    def collect(v):
        if isinstance(v, dict):
            if isinstance(v.get("@id"), str) and len(v) > 1:
                nodes[v["@id"]] = v
            for child in v.values():
                collect(child)
        elif isinstance(v, list):
            for child in v:
                collect(child)
    collect(value)
    def expand(v, seen=frozenset()):
        if isinstance(v, list):
            return [expand(x, seen) for x in v]
        if isinstance(v, dict):
            identity = v.get("@id")
            if isinstance(identity, str) and identity in nodes and identity not in seen:
                v = nodes[identity]
                seen = seen | {identity}
            return {(re.sub(r"^https?://schema\.org/", "", k)): expand(x, seen)
                    for k, x in v.items() if k != "@context"}
        return v
    return expand(value)


def empty_data():
    return {key: [] if key in {"ingredients", "tags", "instructions"} else None for key in FIELDS}


def from_schema(node):
    data = empty_data()
    data.update(title=next(iter(strings(node.get("name"))), None),
                ingredients=strings(node.get("recipeIngredient")),
                yield_text=" ".join(strings(node.get("recipeYield"))) or None,
                servings=servings(node.get("recipeYield")),
                prep_minutes=minutes(node.get("prepTime")),
                cook_minutes=minutes(node.get("cookTime")),
                total_minutes=minutes(node.get("totalTime")),
                category=", ".join(strings(node.get("recipeCategory"))) or None,
                instructions=strings(node.get("recipeInstructions")))
    tags = strings(node.get("keywords")) + strings(node.get("recipeCuisine")) + strings(node.get("suitableForDiet"))
    data["tags"] = sorted(set(t.strip() for v in tags for t in v.split(",") if t.strip()))
    return data


def extract(html, url):
    soup = BeautifulSoup(html, "html.parser")
    result = {"data": empty_data(), "method": "metadata", "issues": [], "links": []}
    # Our Bring! pages deliberately describe whole weekly shopping lists as Recipe.
    p = urlsplit(url)
    if p.hostname == "rauchmat.github.io" and p.path.startswith("/mealplan/bring/"):
        result["issues"] = ["weekly_shopping_list"]
        return result
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if re.search(r"^(?:log in|login|anmelden|access denied|just a moment|verify you are human|captcha|sign in)(?:\b|[ |–-])", title, re.I) or soup.select_one('input[type="password"]'):
        result["issues"] = ["access_page"]
        return result
    candidates = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            candidates.extend(("jsonld", node) for node in recipe_nodes(expand_schema(json.loads(script.string or script.get_text()))))
        except (ValueError, TypeError, RecursionError):
            result["issues"].append("invalid_jsonld")
    if not candidates:
        try:
            structured = extruct.extract(html, base_url=url, syntaxes=["microdata", "rdfa"], uniform=True)
            for kind in ("microdata", "rdfa"):
                candidates.extend((kind, node) for node in recipe_nodes(expand_schema(structured.get(kind))))
        except (ValueError, TypeError, RecursionError, etree.LxmlError):
            result["issues"].append("invalid_structured_data")
    unique = {}
    for method, node in candidates:
        data = from_schema(node)
        unique.setdefault(json.dumps(data, sort_keys=True, ensure_ascii=False), (method, data))
    if len(unique) > 1:
        result["issues"].append("multiple_recipes")
        return result
    if unique:
        result["method"], result["data"] = next(iter(unique.values()))
        return result
    if p.hostname == "rauchmat.github.io" and p.path.startswith("/mealplan/recipes/"):
        heading = soup.select_one("h1")
        facts = soup.select_one(".recipe-facts")
        result["method"] = "house_html"
        result["data"].update(title=heading.get_text(" ", strip=True).rstrip(" .") if heading else None,
                                 ingredients=[li.get_text(" ", strip=True) for li in soup.select(".ingredient-list li")],
                                 instructions=[li.get_text(" ", strip=True) for li in soup.select(".recipe-steps li")])
        if facts:
            content = facts.get_text(" ", strip=True)
            portion = re.search(r"(\d+) Portionen", content)
            duration = re.search(r"(\d+) Minuten", content)
            pill = facts.select_one(".pill")
            result["data"].update(servings=float(portion[1]) if portion else None,
                                     yield_text=portion[0] if portion else None,
                                     total_minutes=float(duration[1]) if duration else None,
                                     category=pill.get_text(strip=True) if pill else None)
        return result
    result["data"]["title"] = title or None
    result["issues"].append("no_recipe_data")
    if platform(url) in {"instagram", "tiktok"}:
        result["method"] = "public_caption"
        # Captions are not saved verbatim. Only explicitly labelled recipe fields.
        captions = [m.get("content", "") for m in soup.select('meta[property="og:description"], meta[name="description"]')]
        for script in soup.select('script[type="application/json"]'):
            try:
                def descriptions(v):
                    if isinstance(v, dict):
                        for k, x in v.items():
                            if k in {"desc", "caption"} and isinstance(x, str):
                                yield x
                            elif isinstance(x, (dict, list)):
                                yield from descriptions(x)
                    elif isinstance(v, list):
                        for x in v:
                            yield from descriptions(x)
                captions.extend(descriptions(json.loads(script.string or script.get_text())))
            except (ValueError, RecursionError):
                result["issues"].append("invalid_social_data")
        # Multiple captions may belong to recommendations, so accept only one unique text.
        captions = list(dict.fromkeys(c.strip() for c in captions if c.strip()))
        if len(captions) == 1:
            caption = captions[0]
            section = re.search(r"(?:^|\n)(?:Zutaten|Ingredients)\s*:\s*\n(.*?)(?=\n(?:Zubereitung|Instructions|Preparation)\s*:|$)", caption, re.I | re.S)
            if section:
                result["data"]["ingredients"] = [line.strip(" -•\t") for line in section[1].splitlines() if line.strip() and not line.lstrip().startswith("#") and "http" not in line]
            steps = re.search(r"(?:^|\n)(?:Zubereitung|Instructions|Preparation)\s*:\s*\n(.*)", caption, re.I | re.S)
            if steps:
                result["data"]["instructions"] = [line.strip() for line in steps[1].splitlines() if line.strip() and not line.lstrip().startswith("#") and "http" not in line]
            portion = re.search(r"(?:^|\n)(\d+) (?:Portionen|servings)\b", caption, re.I)
            if portion:
                result["data"].update(servings=float(portion[1]), yield_text=portion[0].strip())
            for raw in re.findall(r"https?://[^\s<>\"]+", caption):
                try:
                    link = clean_url(raw.rstrip(".,)"))
                    if platform(link) == "website":
                        result["links"].append(link)
                except UnsafeURL:
                    pass
            if result["data"]["ingredients"]:
                result["issues"] = [i for i in result["issues"] if i != "no_recipe_data"]
                result["issues"].append("caption_requires_review")
        elif len(captions) > 1:
            result["issues"].append("ambiguous_captions")
    return result
