import reflex as rx

import json
import os
from urllib.parse import unquote, urlsplit


def safe_https_url(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 8192:
        return ""
    decoded = unquote(value)
    if any(ord(c) < 32 or ord(c) == 127 for c in decoded) or "\\" in decoded:
        return ""
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            return ""
        return value
    except ValueError:
        return ""


PRODUCT_IDS: dict[str, str] = {
    "starter": "starter",
    "yearly": "pro",
    "growth": "shortforge_growth_3months",
}
EXPECTED_TERMS: dict[str, tuple[int, int, str]] = {
    "starter": (19_990_000, 1, "month"),
    "growth": (49_990_000, 3, "month"),
    "yearly": (149_990_000, 1, "year"),
}


def product_ids() -> dict[str, str]:
    return {
        tier: os.getenv(f"REVENUECAT_{tier.upper()}_PRODUCT_ID", "").strip()
        or product
        for tier, product in PRODUCT_IDS.items()
    }


def public_sdk_key() -> str:
    key = (
        os.getenv("VITE_REVENUECAT_API_KEY", "").strip()
        or os.getenv("REVENUECAT_WEB_PUBLIC_API_KEY", "").strip()
    )
    return key if key.startswith(("test_", "rcb_")) and len(key) > 5 else ""


def catalogue_config() -> dict[str, str]:
    key = public_sdk_key()
    products = product_ids()
    if not key or len(set(products.values())) != 3:
        return {}
    return {"key": key, "products": json.dumps(products)}


def checkout_config(tier: str) -> dict[str, str]:
    config = catalogue_config()
    if (
        tier not in PRODUCT_IDS
        or not config
        or not os.getenv("REVENUECAT_SECRET_API_KEY", "").strip()
    ):
        return {}
    return {
        **config,
        "product": product_ids()[tier],
        "package": os.getenv(
            f"REVENUECAT_{tier.upper()}_PACKAGE_ID", ""
        ).strip(),
        "tier": tier,
    }


def validate_catalogue(result: str) -> dict[str, str]:
    messages = {
        "missing_key": "Catalogue unavailable: a valid public SDK key is missing.",
        "missing_default": "Catalogue unavailable: the Default offering is missing or ambiguous.",
        "mapping": "Catalogue mismatch: one or more products, packages, USD prices or billing periods are missing or malformed.",
        "sdk": "Catalogue SDK error: billing could not load. Check your connection or content blocker.",
        "network": "Catalogue network error: RevenueCat could not be reached. Please retry.",
        "failed": "Catalogue SDK/provider error: RevenueCat could not load the offering. Please retry.",
    }
    if not isinstance(result, str) or len(result) > 16384:
        raise ValueError(messages["mapping"])
    if result in messages:
        raise ValueError(messages[result])
    try:
        payload = json.loads(result)
    except (ValueError, TypeError) as e:
        raise ValueError(messages["mapping"]) from e
    if (
        not isinstance(payload, dict)
        or set(payload) != {"products"}
        or not isinstance(payload["products"], list)
        or len(payload["products"]) != 3
    ):
        raise ValueError(messages["mapping"])
    products = product_ids()
    prices: dict[str, str] = {}
    for row in payload["products"]:
        if not isinstance(row, dict):
            raise ValueError(messages["mapping"])
        tier = next(
            (
                tier
                for tier, product in products.items()
                if row.get("productId") == product
            ),
            "",
        )
        if not tier or tier in prices:
            raise ValueError(messages["mapping"])
        price, period, packages = (
            row.get("price"),
            row.get("period"),
            row.get("packages"),
        )
        micros, number, unit = EXPECTED_TERMS[tier]
        override = os.getenv(
            f"REVENUECAT_{tier.upper()}_PACKAGE_ID", ""
        ).strip()
        if (
            not isinstance(price, dict)
            or not isinstance(period, dict)
            or price.get("currency") != "USD"
            or type(price.get("amountMicros")) is not int
            or price["amountMicros"] != micros
            or type(period.get("number")) is not int
            or period["number"] != number
            or period.get("unit") != unit
            or not isinstance(price.get("formattedPrice"), str)
            or not price["formattedPrice"].strip()
            or len(price["formattedPrice"]) > 128
            or any(ord(c) < 32 for c in price["formattedPrice"])
            or not isinstance(packages, list)
            or not packages
            or not all(
                isinstance(p, str) and p and len(p) <= 256 for p in packages
            )
            or len(set(packages)) != len(packages)
            or (
                packages.count(override) != 1
                if override
                else len(packages) != 1
            )
        ):
            raise ValueError(
                f"Catalogue mismatch for {tier}: expected USD {micros / 1_000_000:.2f}, {number} {unit}(s), and an exact package. Target prices remain unverified."
            )
        prices[tier] = price["formattedPrice"]
    return prices


def web_operation(config: dict[str, str], operation: str) -> str:
    if operation not in ("offerings", "purchase", "restore"):
        raise ValueError("Unsupported billing operation")
    allowed = {
        name: config[name]
        for name in ("key", "subject", "products", "product", "package", "tier")
        if name in config
    }
    if not allowed.get("key", "").startswith(("test_", "rcb_")):
        return "Promise.resolve('missing_key')"
    encoded = json.dumps(allowed).replace("<", "\\u003c")
    mode = json.dumps(operation)
    finish = "return JSON.stringify({products: rows});"
    if operation == "purchase":
        finish = """
            const matches = packages.filter(pkg =>
                productOf(pkg)?.identifier === config.product &&
                (!config.package || pkg.identifier === config.package));
            if (matches.length !== 1) return 'mapping';
            const pkg = matches[0], product = productOf(pkg);
            const expected = {
                starter: {amountMicros: 19990000, number: 1, unit: 'month'},
                growth: {amountMicros: 49990000, number: 3, unit: 'month'},
                yearly: {amountMicros: 149990000, number: 1, unit: 'year'}
            }[config.tier];
            const price = product.price, period = product.period;
            if (!expected || price.currency !== 'USD' || price.amountMicros !== expected.amountMicros ||
                !Number.isSafeInteger(price.amountMicros) || period.number !== expected.number ||
                normalizeUnit(period.unit) !== expected.unit) return 'mapping';
            await purchases.purchase({rcPackage: pkg});
            await purchases.getCustomerInfo();
            return 'ok';
        """
    if operation == "restore":
        finish = "return 'ok';"
    return f"""(async () => {{
        const config = {encoded};
        const mode = {mode};
        let Purchases, purchases;
        try {{
            const sdk = await Promise.race([
                import('https://esm.sh/@revenuecat/purchases-js@1.67.1'),
                new Promise((_, reject) => setTimeout(() => reject(new Error('sdk_timeout')), 20000))
            ]);
            Purchases = sdk.Purchases;
            if (!Purchases) return 'sdk';
        }} catch (_) {{ return 'sdk'; }}
        try {{
            if (Purchases.isConfigured()) {{
                if (window.__shortforgeRevenueCatKey && window.__shortforgeRevenueCatKey !== config.key) return 'sdk';
                purchases = Purchases.getSharedInstance();
                await purchases.changeUser(config.subject);
            }} else {{
                purchases = Purchases.configure({{apiKey: config.key, appUserId: config.subject}});
                window.__shortforgeRevenueCatKey = config.key;
            }}
            if (mode === 'restore') {{
                await purchases.getCustomerInfo();
                return 'ok';
            }}
            const offerings = await Promise.race([
                purchases.getOfferings({{currency: 'USD'}}),
                new Promise((_, reject) => setTimeout(() => reject(new Error('network_timeout')), 20000))
            ]);
            const isDefault = value => typeof value === 'string' && value.toLowerCase() === 'default';
            const entries = Object.entries(offerings?.all || {{}}).filter(([id, value]) =>
                isDefault(value?.identifier || id));
            const offering = isDefault(offerings?.current?.identifier) ? offerings.current :
                (entries.length === 1 ? entries[0][1] : null);
            if (!offering) return 'missing_default';
            const packages = offering.availablePackages;
            if (!Array.isArray(packages)) return 'mapping';
            const productOf = pkg => pkg?.webBillingProduct ?? pkg?.product;
            const normalizeUnit = unit => typeof unit === 'string' ? unit.toLowerCase().replace(/s$/, '') : '';
            const ids = Object.values(JSON.parse(config.products || '{{}}'));
            if (ids.length !== 3 || new Set(ids).size !== 3) return 'mapping';
            const rows = [];
            for (const id of ids) {{
                const found = packages.filter(pkg => productOf(pkg)?.identifier === id);
                if (!found.length) return 'mapping';
                const product = productOf(found[0]), price = product?.price, period = product?.period;
                if (!price || typeof price.formattedPrice !== 'string' || !price.formattedPrice.trim() ||
                    typeof price.currency !== 'string' || !Number.isSafeInteger(price.amountMicros) ||
                    !period || !Number.isSafeInteger(period.number) || !normalizeUnit(period.unit) ||
                    found.some(pkg => typeof pkg.identifier !== 'string' || !pkg.identifier ||
                        productOf(pkg)?.price?.amountMicros !== price.amountMicros ||
                        productOf(pkg)?.price?.currency !== price.currency ||
                        productOf(pkg)?.period?.number !== period.number ||
                        normalizeUnit(productOf(pkg)?.period?.unit) !== normalizeUnit(period.unit))) return 'mapping';
                rows.push({{productId: id,
                    price: {{formattedPrice: price.formattedPrice, currency: price.currency, amountMicros: price.amountMicros}},
                    period: {{number: period.number, unit: normalizeUnit(period.unit)}},
                    packages: found.map(pkg => pkg.identifier)}});
            }}
            {finish}
        }} catch (error) {{
            const name = String(error?.name || '').toLowerCase();
            const code = error?.errorCode ?? error?.code;
            const detail = String(error?.message || '').toLowerCase();
            if (error?.userCancelled || code === 1 || detail.includes('cancel')) return 'cancelled';
            if (name.includes('network') || detail.includes('network') || detail.includes('fetch') || detail.includes('timeout')) return 'network';
            if (detail.includes('payment') || detail.includes('declin') || detail.includes('card')) return 'payment';
            return 'failed';
        }}
    }})()"""
