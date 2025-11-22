class Billing:

    def __init__(self):
        self.current_billing = 0
        self.transaction_history = []

    def buy(self, current_price, puissance, n = 1):
        montant = -(current_price * puissance * n)
        self.current_billing += montant
        self.transaction_history.append({
            "type": "buy",
            "price": current_price,
            "amount": montant,
            "balance": self.current_billing
        })
        return self.transaction_history[-1]  # last 

    def sell(self, current_price, puissance, n = 1):
        montant = current_price * puissance * n
        self.current_billing += montant
        self.transaction_history.append({
            "type": "sell",
            "price": current_price,
            "amount": montant,
            "balance": self.current_billing
        })
        return self.transaction_history[-1]  # last 

    def get_history(self):
        return self.transaction_history