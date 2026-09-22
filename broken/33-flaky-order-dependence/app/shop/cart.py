from . import catalog, pricing


class Cart:
    def __init__(self, notes=[]):
        self.lines = {}          # sku -> qty
        self.notes = notes       # free-text notes shown to the packer

    def add(self, sku, qty=1):
        self.lines[sku] = self.lines.get(sku, 0) + qty

    def note(self, text):
        self.notes.append(text)

    def subtotal(self):
        return sum(pricing.PRICES[sku] * qty for sku, qty in self.lines.items())

    def checkout(self):
        """Reserve stock for every line and return (total_with_tax_cents, currency)."""
        for sku, qty in self.lines.items():
            catalog.reserve(sku, qty)
        return pricing.with_tax(self.subtotal()), pricing.currency()
