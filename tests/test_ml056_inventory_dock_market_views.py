from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class InventoryDockMarketViewTests(unittest.TestCase):
    def test_inventory_uses_label_value_facts_and_preserves_filters_and_instance_details(self):
        template = read("app/templates/inventory/index.html")
        self.assertIn('class="inventory-facts"', template)
        self.assertIn("<dt>Quantidade</dt><dd>{{ inventory_item.quantity }}</dd>", template)
        self.assertIn("<dt>Refino</dt><dd>+{{ item.upgrade_level }}</dd>", template)
        self.assertIn("<dt>Estado</dt><dd>", template)
        self.assertIn("<dt>{{ label }}</dt><dd>+{{ value }}</dd>", template)
        self.assertIn('name="category"', template)
        self.assertIn('name="rarity"', template)
        self.assertIn('name="max_level"', template)
        self.assertIn("data-bonus-dialog-open", template)
        self.assertIn("Equipado em <a href=\"/mercenaries/{{ item.equipped_to_mercenary.id }}\"", template)
        self.assertNotIn("x{{ inventory_item.quantity }}", template)
        self.assertNotIn("Refino +{{ item.upgrade_level }}", template)

    def test_dock_offer_shows_rotation_merchant_stock_price_total_and_consult_only_equipment_details(self):
        template = read("app/templates/docks/index.html")
        route = read("app/routes/dock_routes.py")
        main = read("app/static/js/main.js")
        self.assertIn("Ofertas até", template)
        self.assertIn("clean_generated_name(visit.merchant.name)", template)
        self.assertIn("merchant_type_labels.get(visit.merchant.merchant_type", template)
        self.assertIn("<dt>Estoque</dt><dd>{{ offer.remaining_stock }}</dd>", template)
        self.assertIn("<dt>Preço por unidade</dt><dd>{{ offer.unit_price }} ouro</dd>", template)
        self.assertIn('data-dock-buy-form data-unit-price="{{ offer.unit_price }}"', template)
        self.assertIn("data-dock-total role=\"status\" aria-live=\"polite\"", template)
        self.assertIn("get_equipment_slot_label(offer.item_template.equipment_slot)", template)
        self.assertIn("<strong>{{ label }}</strong><span>+{{ value }} base</span>", template)
        details = template.split('<section class="equipment-details" id="{{ details_id }}"', 1)[1].split("</section>", 1)[0]
        self.assertNotIn("<form", details)
        self.assertIn("data-equipment-details-trigger", template)
        self.assertIn('action="/docks/offers/{{ offer.id }}/buy"', template)
        self.assertIn('"get_equipment_slot_label": get_equipment_slot_label', route)
        self.assertIn("initializeDockPurchaseEstimates(currentMain);", main)
        self.assertIn("data-dock-quantity", main)

    def test_market_sale_quantity_total_and_deadline_stay_together_and_actions_remain_distinct(self):
        template = read("app/templates/market/index.html")
        main = read("app/static/js/main.js")
        self.assertIn('class="market-sale-facts"', template)
        self.assertIn("<dt>Quantidade anunciada</dt><dd>{{ sale.quantity }} · {{ sale.unit_value }} ouro/un.</dd>", template)
        self.assertIn("<dt>Valor total</dt><dd>{{ sale.total_value }} ouro</dd>", template)
        self.assertIn("<dt>Prazo até (UTC)</dt>", template)
        self.assertIn('action="/market/{{ sale.id }}/collect"', template)
        self.assertIn('action="/market/{{ sale.id }}/cancel"', template)
        self.assertIn("required aria-label=\"Quantidade para anunciar", template)
        self.assertIn("Number.isInteger(parsed)", main)
        self.assertIn("marketServerDisabled", main)

    def test_workshop_and_salvage_status_never_claim_an_invalid_or_unaffordable_batch(self):
        workshop = read("app/templates/workshops/index.html")
        blacksmith = read("app/templates/blacksmith/index.html")
        main = read("app/static/js/main.js")
        css = read("app/static/css/main.css")
        desktop_css = read("app/static/css/desktop-theme.css")
        self.assertIn('step="1"', workshop)
        self.assertIn("data-workshop-submit", workshop)
        self.assertIn("data-gold-known=", blacksmith)
        self.assertIn("Saldo de ouro não informado", main)
        self.assertIn("Faltam ${totalCost - goldBalance} ouro", main)
        self.assertIn("data-salvage-status", blacksmith)
        self.assertIn(".supply-preparation-progress a.secondary-button", css)
        self.assertIn("min-height: 40px", css.split(".supply-preparation-progress a.secondary-button", 1)[1].split("}", 1)[0])
        self.assertIn(".blacksmith-craft-action > button:focus-visible { outline: 3px solid var(--gold-2); outline-offset: 3px; }", desktop_css)


if __name__ == "__main__":
    unittest.main()
