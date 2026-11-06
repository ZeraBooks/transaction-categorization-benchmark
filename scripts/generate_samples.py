"""Build the benchmark in data/.

    python3 scripts/generate_samples.py

Writes:
  data/chart-of-accounts.csv   the 41 accounts every label comes from
  data/businesses.csv          12 fictional businesses: industry, entity, sales tax
  data/transactions.csv        the inputs a tool sees (no labels)
  data/labels.csv              the answer key, with the reason and difficulty
  data/splits.csv              warm and cold dev/test splits (see README)

Bank descriptions are written the way banks print them (card purchases
wrapped and cut short in three bank styles), and use real
merchant names (Shell, Costco, Gusto) because that is what a tool has to
read. The businesses, people, amounts and dates are fictional. Seeded, so
the files are the same on every run.
"""
import csv
import datetime as dt
import os
import random
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

CHART = [
    ("1000", "Transfer between own accounts", "transfer", "Money moving between the business's own bank, savings or card accounts. Not income or expense."),
    ("1500", "Equipment and fixed assets", "asset", "Items over the capitalization threshold ($2,500 in this benchmark, the IRS de minimis safe harbor amount without an audited financial statement)."),
    ("2100", "Credit card payment", "liability", "Paying the business credit card bill from the bank account. The charges were already expensed on the card."),
    ("2300", "Sales tax payment", "liability", "Remitting sales tax collected from customers."),
    ("2700", "Loan payment", "liability", "A payment on a loan or equipment financing. Needs a split between principal and interest."),
    ("3000", "Owner contribution", "equity", "Money the owner puts into the business."),
    ("3100", "Owner draw or distribution", "equity", "Money the owner takes out, including personal estimated tax payments made from a pass-through business account."),
    ("4000", "Revenue", "revenue", "Sales and service income, including card processor and marketplace payouts and insurance reimbursements."),
    ("4900", "Refunds to customers", "revenue", "Money returned to customers. A contra-revenue account."),
    ("5000", "Cost of goods and materials", "cost_of_sales", "Inventory, ingredients, materials and supplies used to make what is sold."),
    ("5100", "Subcontractors", "cost_of_sales", "Outside workers paid per job."),
    ("5200", "Fuel (cost of revenue)", "cost_of_sales", "Fuel for a business whose revenue is moving things: trucking and freight."),
    ("6000", "Wages", "expense", "Employee net pay."),
    ("6010", "Payroll taxes and fees", "expense", "Payroll tax debits and payroll service fees."),
    ("6100", "Rent", "expense", "Rent for premises."),
    ("6110", "Utilities", "expense", "Power, gas, water, trash."),
    ("6120", "Phone and internet", "expense", ""),
    ("6200", "Software and subscriptions", "expense", ""),
    ("6210", "Advertising and marketing", "expense", ""),
    ("6220", "Meals", "expense", "Business meals. Deductibility limits are applied at tax time, not here."),
    ("6230", "Travel", "expense", "Airfare, hotels, rideshare and car rental while traveling."),
    ("6240", "Vehicle and fuel", "expense", "Fuel and vehicle costs for a business that isn't in transport."),
    ("6250", "Office supplies", "expense", ""),
    ("6260", "Repairs and maintenance", "expense", ""),
    ("6270", "Insurance", "expense", ""),
    ("6280", "Professional fees", "expense", "Accounting, legal and consulting."),
    ("6290", "Bank and merchant fees", "expense", ""),
    ("6300", "Shipping and postage", "expense", ""),
    ("6310", "Dues and memberships", "expense", ""),
    ("6320", "Training and education", "expense", ""),
    ("6350", "Taxes and licenses", "expense", "Business licenses, registrations and non-income business taxes."),
    ("6360", "Lab and clinical supplies", "expense", "Clinical supplies for a healthcare practice that are consumed rather than resold."),
    ("8000", "Interest income", "other_income", ""),
    ("9999", "Ask the client", "review", "The bank line alone can't say what this is (a Venmo or Zelle to a person, a cash withdrawal). The right answer is to ask."),
]

BUSINESSES = [
    ("B01", "Juniper Lane Bakery LLC", "bakery", "single-member LLC", "yes"),
    ("B02", "Okafor Family Dental PC", "dental", "professional corporation", "no"),
    ("B03", "Brightwater Landscaping Inc", "landscaping", "S corporation", "no"),
    ("B04", "Redline Freight Co", "trucking", "single-member LLC", "no"),
    ("B05", "Marisol Vega CPA", "cpa_firm", "sole proprietor", "no"),
    ("B06", "Copperline Electric LLC", "electrical", "multi-member LLC", "no"),
    ("B07", "Fernhill Goods", "ecommerce", "single-member LLC", "yes"),
    ("B08", "Northpaw Creative Studio", "agency", "S corporation", "no"),
    ("B09", "Daybreak Coffee Bar", "coffee_shop", "single-member LLC", "yes"),
    ("B10", "Ironwood Property Management", "property_mgmt", "multi-member LLC", "no"),
    ("B11", "Quiet Harbor Counseling", "therapy", "professional LLC", "no"),
    ("B12", "Tan & Ruiz Law Group", "law_firm", "partnership", "no"),
]
GOODS = {"bakery", "coffee_shop", "ecommerce"}
TRADES = {"landscaping", "electrical"}

# description template, amount range (negative = money out), default account, {industry: account}, difficulty, reason, who
M = [
    # money in
    ("SQUARE INC DEPOSIT {d4} {date}", (180, 2600), "4000", {}, "easy", "Card sales paid out by Square.", GOODS | {"therapy"}),
    ("STRIPE TRANSFER ST-{a8}", (400, 9000), "4000", {}, "easy", "Customer payments paid out by Stripe.", {"ecommerce", "agency", "cpa_firm", "therapy"}),
    ("SHOPIFY PAYMENTS PAYOUT {d6}", (300, 7000), "4000", {}, "easy", "Store sales paid out by Shopify.", {"ecommerce"}),
    ("AMAZON.COM SERVICES PAYOUT", (800, 12000), "4000", {}, "easy", "Marketplace sales paid out by Amazon.", {"ecommerce"}),
    ("DELTA DENTAL INS PAYMENT {d6}", (600, 8000), "4000", {}, "easy", "Insurance reimbursement for patient care.", {"dental"}),
    ("ACH CREDIT {client} PAYMENT", (900, 15000), "4000", {}, "easy", "A customer paying an invoice by ACH.", {"landscaping", "trucking", "cpa_firm", "electrical", "agency", "law_firm", "property_mgmt"}),
    ("MOBILE CHECK DEPOSIT {d4}", (250, 6000), "4000", {}, "judgment", "Check deposits are usually customer payments, but could be a loan or the owner's money. Labelled revenue because the business's invoices show these customers.", None),
    ("ONLINE TRANSFER FROM SAV ...{d4}", (1000, 10000), "1000", {}, "easy", "From the business's own savings account.", None),
    ("INTEREST PAYMENT", (1, 60), "8000", {}, "easy", "Interest earned on the account.", None),
    ("DEPOSIT FROM {owner} PERSONAL CHK", (2000, 15000), "3000", {}, "needs_context", "The owner moving personal money in. Not revenue.", None),
    ("RTP CREDIT DAT FACTORING {d6}", (3000, 14000), "4000", {}, "needs_context", "A factoring company advancing freight invoices. Revenue on the invoices, recorded when the factor pays.", {"trucking"}),
    ("ACH CREDIT TENANT RENT POOL {d4}", (4000, 30000), "4000", {"property_mgmt": "4000"}, "needs_context", "Rent collected for owners flows through; here the management company's fee share. Labelled revenue for this benchmark.", {"property_mgmt"}),
    # payroll
    ("GUSTO NET {d6} {co}", (-18000, -3000), "6000", {}, "easy", "Employee net pay through Gusto.", None),
    ("GUSTO TAX {d6} {co}", (-6000, -900), "6010", {}, "easy", "Payroll taxes collected by Gusto.", None),
    ("ADP WAGE PAY {d6}", (-16000, -3000), "6000", {}, "easy", "Employee net pay through ADP.", None),
    ("ADP TAX {d6}", (-5000, -800), "6010", {}, "easy", "Payroll taxes collected by ADP.", None),
    # occupancy and utilities
    ("RENT {landlord} LLC ACH", (-6500, -1800), "6100", {}, "easy", "Monthly rent.", None),
    ("PGANDE WEB ONLINE {d6}", (-900, -120), "6110", {}, "easy", "Power and gas.", None),
    ("CITY OF FAIRHAVEN UTILITIES", (-400, -60), "6110", {}, "easy", "Water, sewer, trash.", None),
    ("COMCAST BUSINESS {d6}", (-260, -110), "6120", {}, "easy", "Internet.", None),
    ("VERIZON WIRELESS PAYMENTS", (-480, -90), "6120", {}, "easy", "Phones.", None),
    # software
    ("GOOGLE *GSUITE_{dom}", (-120, -14), "6200", {}, "easy", "Google Workspace.", None),
    ("MICROSOFT*365 BUSINESS", (-90, -12), "6200", {}, "easy", "Microsoft 365.", None),
    ("ADOBE *CREATIVE CLOUD", (-90, -60), "6200", {}, "easy", "Adobe subscription.", None),
    ("ZOOM.US 888-799-9666", (-30, -15), "6200", {}, "easy", "Zoom.", None),
    ("CANVA* {a8}", (-15, -12), "6200", {}, "easy", "Canva.", None),
    ("CLIO SUBSCRIPTION", (-400, -89), "6200", {}, "easy", "Law practice software.", {"law_firm"}),
    ("DAT SOLUTIONS LLC", (-200, -45), "6200", {}, "easy", "Load board subscription.", {"trucking"}),
    ("SIMPLEPRACTICE {d6}", (-120, -49), "6200", {}, "easy", "Practice management software.", {"therapy"}),
    ("DENTRIX ASCEND", (-600, -300), "6200", {}, "easy", "Practice management software.", {"dental"}),
    # marketing
    ("FACEBK *{a8}", (-800, -25), "6210", {}, "easy", "Meta ads.", None),
    ("GOOGLE *ADS{d6}", (-1500, -50), "6210", {}, "easy", "Google Ads.", None),
    ("YELP INC ADS", (-400, -150), "6210", {}, "easy", "Yelp ads.", {"bakery", "coffee_shop", "dental", "landscaping", "electrical", "therapy"}),
    # meals, travel, vehicles
    ("DOORDASH*{rest}", (-120, -18), "6220", {}, "judgment", "Food delivery. Labelled meals; for a personal order it would be a draw.", None),
    ("STARBUCKS STORE {d5}", (-40, -5), "6220", {}, "judgment", "Coffee with a client or staff. Labelled meals.", None),
    ("UNITED AIRLINES {d10}", (-900, -180), "6230", {}, "easy", "Airfare.", None),
    ("MARRIOTT {city} {d4}", (-700, -150), "6230", {}, "easy", "Hotel.", None),
    ("UBER *TRIP {a8}", (-90, -9), "6230", {}, "easy", "Rideshare.", None),
    ("SHELL OIL {d8}", (-140, -30), "6240", {"trucking": "5200"}, "needs_context", "Fuel. Cost of revenue for a carrier; vehicle expense for everyone else.", None),
    ("CHEVRON {d6}", (-140, -30), "6240", {"trucking": "5200"}, "needs_context", "Fuel. Cost of revenue for a carrier; vehicle expense for everyone else.", None),
    ("PILOT_{d5} {city}", (-1400, -400), "5200", {}, "easy", "Diesel at a truck stop.", {"trucking"}),
    ("LOVES #{d4} {city}", (-1300, -400), "5200", {}, "easy", "Diesel at a truck stop.", {"trucking"}),
    ("TA TRUCK SERVICE {d4}", (-3000, -300), "6260", {}, "easy", "Truck repair.", {"trucking"}),
    ("PAY.GOV 2290 HVUT", (-550, -550), "6350", {}, "needs_context", "Heavy vehicle use tax.", {"trucking"}),
    # cost of goods and materials
    ("COSTCO WHSE #{d4}", (-900, -60), "6250", {"bakery": "5000", "coffee_shop": "5000"}, "needs_context", "Ingredients for a bakery or cafe; office supplies for everyone else.", None),
    ("RESTAURANT DEPOT {d4}", (-1600, -200), "5000", {}, "easy", "Ingredients.", {"bakery", "coffee_shop"}),
    ("SYSCO {d6}", (-2400, -300), "5000", {}, "easy", "Food service supplier.", {"bakery", "coffee_shop"}),
    ("HOME DEPOT #{d4}", (-1200, -30), "6260", {"landscaping": "5000", "electrical": "5000"}, "needs_context", "Job materials for a trade; repairs for everyone else.", None),
    ("THE HOME DEPOT PRO {d4}", (-4000, -200), "5000", {}, "easy", "Job materials.", TRADES),
    ("CED ELECTRICAL SUPPLY {d4}", (-5000, -200), "5000", {}, "easy", "Electrical materials.", {"electrical"}),
    ("SITEONE LANDSCAPE SUPPLY", (-4000, -150), "5000", {}, "easy", "Plants and landscape materials.", {"landscaping"}),
    ("HENRY SCHEIN INC {d6}", (-3500, -150), "6360", {}, "easy", "Dental supplies.", {"dental"}),
    ("ALIBABA.COM {d8}", (-6000, -400), "5000", {}, "easy", "Inventory from a supplier.", {"ecommerce"}),
    ("AMZN MKTP US*{a8}", (-300, -12), "6250", {"ecommerce": "5000"}, "judgment", "Usually office supplies; for the online store these are packaging and inventory.", None),
    ("STAPLES {d5}", (-250, -10), "6250", {}, "easy", "Office supplies.", None),
    ("ZELLE TO {person} {d6}", (-2500, -200), "9999", {"landscaping": "5100", "electrical": "5100"}, "needs_context", "A trade business paying a crew member per job (subcontractor). Anyone else: ask.", None),
    # shipping, insurance, professional, fees
    ("USPS PO {d10}", (-180, -8), "6300", {}, "easy", "Postage.", None),
    ("UPS* {d10}", (-400, -12), "6300", {}, "easy", "Shipping.", None),
    ("SHIPPO* {a8}", (-600, -40), "6300", {}, "easy", "Shipping labels.", {"ecommerce"}),
    ("NEXT INSUR*{a8}", (-400, -60), "6270", {}, "easy", "Business insurance.", None),
    ("STATE FARM RO 27 {d6}", (-900, -120), "6270", {}, "easy", "Insurance.", None),
    ("PROGRESSIVE *INSURANCE", (-2400, -600), "6270", {}, "easy", "Truck insurance.", {"trucking"}),
    ("LEGALZOOM.COM", (-300, -80), "6280", {}, "easy", "Legal filings.", None),
    ("KESSLER & PARK CPAS", (-2500, -400), "6280", {}, "easy", "Accountant's fee.", None),
    ("MONTHLY SERVICE FEE", (-35, -15), "6290", {}, "easy", "Bank fee.", None),
    ("OUTGOING WIRE FEE", (-35, -25), "6290", {}, "easy", "Bank fee.", None),
    ("STRIPE BILLING FEE", (-60, -5), "6290", {}, "easy", "Processor fee.", {"ecommerce", "agency", "cpa_firm", "therapy"}),
    ("AICPA MEMBERSHIP DUES", (-600, -300), "6310", {}, "easy", "Professional dues.", {"cpa_firm"}),
    ("STATE BAR OF CALIFORNIA", (-600, -400), "6310", {}, "easy", "Bar dues.", {"law_firm"}),
    ("BECKER PROFESSIONAL EDU", (-900, -150), "6320", {}, "easy", "CPE courses.", {"cpa_firm"}),
    ("SECRETARY OF STATE FILING", (-150, -20), "6350", {}, "easy", "Annual report fee.", None),
    # balance sheet
    ("CHASE CREDIT CRD AUTOPAY", (-6000, -300), "2100", {}, "easy", "Paying the business credit card.", None),
    ("AMEX EPAYMENT ACH PMT", (-8000, -400), "2100", {}, "easy", "Paying the business card.", None),
    ("ONLINE TRANSFER TO SAV ...{d4}", (-8000, -500), "1000", {}, "easy", "To the business's own savings account.", None),
    ("SBA EIDL LOAN PMT {d6}", (-900, -731), "2700", {}, "needs_context", "SBA loan payment. Split principal and interest from the loan statement.", None),
    ("KUBOTA CREDIT CORP", (-1100, -700), "2700", {}, "needs_context", "Equipment financing payment.", {"landscaping"}),
    ("DAIMLER TRUCK FIN SVC", (-3200, -2400), "2700", {}, "needs_context", "Truck loan payment.", {"trucking"}),
    ("CA DEPT TAX FEE CDTFA", (-3000, -300), "2300", {}, "easy", "Remitting sales tax.", {"bakery", "coffee_shop", "ecommerce"}),
    ("IRS USATAXPYMT {d10}", (-6000, -1000), "3100", {}, "needs_context", "Owner's personal estimated tax paid from a pass-through business account: a draw, not an expense.", {"bakery", "trucking", "cpa_firm", "ecommerce", "coffee_shop"}),
    ("ONLINE TRANSFER TO {owner} PERSONAL", (-6000, -500), "3100", {}, "needs_context", "Owner taking money out.", None),
    ("APPLE STORE R{d3}", (-3800, -2600), "1500", {}, "judgment", "A computer over $2,500: equipment, not supplies.", None),
    ("APPLE.COM/BILL", (-15, -1), "6200", {}, "easy", "App or iCloud subscription.", None),
    ("DELL MARKETING L.P.", (-2400, -600), "6250", {}, "judgment", "Under the $2,500 threshold, so expensed.", None),
    ("REFUND {client}", (-900, -40), "4900", {}, "easy", "Money returned to a customer.", {"ecommerce", "agency", "landscaping", "electrical", "dental"}),
    ("SQ *BLUE BOTTLE COFFEE", (-45, -6), "6220", {}, "judgment", "A Square merchant: a coffee shop. Meals.", None),
    ("SQ *JOES TREE SERVICE", (-1800, -250), "6260", {"landscaping": "5100"}, "needs_context", "A Square merchant doing tree work: a subcontractor for a landscaper, a repair for anyone else.", None),
    ("SQ *FAIRHAVEN FARMERS MKT", (-300, -25), "9999", {"bakery": "5000", "coffee_shop": "5000"}, "needs_context", "Produce: ingredients for a bakery or cafe. For anyone else, ask.", None),
    ("TST* {rest}", (-140, -14), "6220", {}, "judgment", "A Toast restaurant. Meals.", None),
    ("UBER *EATS {a8}", (-90, -15), "6220", {}, "judgment", "Food delivery, not a ride. Meals.", None),
    ("PAYPAL *UPWORK {d6}", (-2500, -150), "6280", {"agency": "5100"}, "needs_context", "A freelancer: a subcontractor for an agency that resells the work, a professional fee for anyone else.", None),
    ("PAYPAL *NAMECHEAP", (-60, -9), "6200", {}, "easy", "Domain renewal.", None),
    ("PAYPAL *ETSY {a8}", (-400, -20), "6250", {"ecommerce": "5000"}, "needs_context", "Supplies from an Etsy seller: inventory for the online store, office supplies for anyone else.", None),
    ("WALMART SUPERCENTER #{d4}", (-400, -20), "6250", {"bakery": "5000", "coffee_shop": "5000"}, "needs_context", "Ingredients for a bakery or cafe; supplies for everyone else.", None),
    ("LOWES #{d5}", (-1500, -25), "6260", {"landscaping": "5000", "electrical": "5000"}, "needs_context", "Job materials for a trade; repairs for everyone else.", None),
    ("CHECK {d4}", (-4000, -100), "9999", {}, "needs_context", "A paper check with no payee on the statement. Look up the check image or ask.", None),
    ("VENMO PAYMENT {d10}", (-600, -20), "9999", {}, "needs_context", "A Venmo to a person: could be a contractor, a refund or personal. Ask.", None),
    ("ATM WITHDRAWAL {d6} {city}", (-400, -60), "9999", {}, "needs_context", "Cash out. Ask what it was spent on.", None),
]
RECURRING = {"RENT {landlord} LLC ACH", "PGANDE WEB ONLINE {d6}", "COMCAST BUSINESS {d6}", "VERIZON WIRELESS PAYMENTS", "GOOGLE *GSUITE_{dom}",
             "MONTHLY SERVICE FEE", "INTEREST PAYMENT", "NEXT INSUR*{a8}", "SBA EIDL LOAN PMT {d6}", "KUBOTA CREDIT CORP", "DAIMLER TRUCK FIN SVC",
             "CLIO SUBSCRIPTION", "DAT SOLUTIONS LLC", "SIMPLEPRACTICE {d6}", "DENTRIX ASCEND", "PROGRESSIVE *INSURANCE", "CITY OF FAIRHAVEN UTILITIES"}
CLIENTS = ["HARTWELL MFG", "BLUE RIDGE HOA", "SUMMIT OAKS LLC", "PINECREST SCHOOLS", "ORTEGA HOLDINGS", "LAKEVIEW CLINIC", "MERIDIAN FOODS", "KAPOOR FAMILY TRUST"]
LANDLORDS = ["MAPLE COURT PROPERTIES", "HARBORVIEW PLAZA", "OAKMONT CENTER", "RIVERSIDE COMMONS"]
PEOPLE = ["JOSE MARTINEZ", "KEVIN TRAN", "ANA LOPEZ", "MARCUS HILL", "PRIYA SHAH", "TOMAS RUIZ"]
CITIES = ["FAIRHAVEN", "BAKERSFIELD", "DENVER", "OKLAHOMA CI", "MEMPHIS", "BOISE", "RENO"]
RESTS = ["CHIPOTLE", "PANERA", "SWEETGREEN", "THAI BASIL", "LUIGIS PIZZA"]


def fill(rng, tpl, biz, day):
    return tpl.format(
        d3=rng.randint(100, 999), d4=rng.randint(1000, 9999), d5=rng.randint(10000, 99999), d6=rng.randint(100000, 999999),
        d8=rng.randint(10 ** 7, 10 ** 8 - 1), d10=rng.randint(10 ** 9, 10 ** 10 - 1),
        a8="".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8)),
        date=day.strftime("%m%d"), client=rng.choice(CLIENTS), landlord=LANDLORDS[int(biz[0][1:]) % len(LANDLORDS)],
        person=rng.choice(PEOPLE), owner=biz[1].split()[0].upper(), co=biz[1].split()[0].upper()[:10],
        city=rng.choice(CITIES), rest=rng.choice(RESTS), dom=biz[1].split()[0].lower() + ".com",
    )


POS = ("COSTCO", "HOME DEPOT", "THE HOME DEPOT", "STAPLES", "STARBUCKS", "DOORDASH", "UBER", "UNITED", "MARRIOTT", "SHELL", "CHEVRON",
       "PILOT_", "LOVES", "AMZN", "APPLE STORE", "RESTAURANT DEPOT", "CED ", "SITEONE", "USPS", "UPS*", "SHIPPO", "CANVA", "ADOBE", "ZOOM",
       "GOOGLE", "FACEBK", "MICROSOFT", "TA TRUCK", "DELL", "ALIBABA", "LEGALZOOM", "BECKER", "SQ *", "TST*", "PAYPAL", "WALMART", "LOWES",
       "SYSCO", "HENRY SCHEIN")
BANK_STYLE = {"B01": "chase", "B02": "bofa", "B03": "wells", "B04": "plain", "B05": "chase", "B06": "wells",
              "B07": "bofa", "B08": "plain", "B09": "wells", "B10": "chase", "B11": "bofa", "B12": "plain"}


def bank_format(rng, bid, desc, day, card4):
    """Wrap a card purchase the way the business's bank prints it."""
    if not desc.startswith(POS):
        return desc
    style = BANK_STYLE[bid]
    if style == "chase":
        return f"CARD PURCHASE {day:%m/%d} {desc} CARD {card4}"
    if style == "bofa":
        return f"CHECKCARD {day:%m%d} {desc} {rng.randint(10 ** 10, 10 ** 11 - 1)}"
    if style == "wells":
        # Wells-style lines run long and the export cuts them at 45 characters.
        return f"PURCHASE AUTHORIZED ON {day:%m/%d} {desc} S{rng.randint(10 ** 9, 10 ** 10 - 1)} CARD {card4}"[:45]
    return desc


def main():
    rng = random.Random(20261105)
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "chart-of-accounts.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(["account", "name", "group", "what_goes_here"])
        w.writerows(CHART)
    with open(os.path.join(DATA, "businesses.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(["business_id", "name", "industry", "entity_type", "collects_sales_tax"])
        w.writerows(BUSINESSES)
    valid = {c[0] for c in CHART}
    txns, labels = [], []
    n = 0
    for biz in BUSINESSES:
        bid, name, ind, ent, tax = biz
        menu = [m for m in M if m[6] is None or ind in m[6]]
        if ent in ("professional corporation", "S corporation", "partnership", "multi-member LLC", "professional LLC"):
            menu = [m for m in menu if not m[0].startswith("IRS USATAXPYMT")]
        for month in range(4, 10):  # April to September 2026
            start = dt.date(2026, month, 1)
            provider = "GUSTO" if int(bid[1:]) % 2 else "ADP"
            payroll = [m for m in menu if m[2] in ("6000", "6010") and m[0].startswith(provider)]
            revenue = [m for m in menu if m[2] == "4000"]
            picks = [m for m in menu if m[0] in RECURRING]
            picks += payroll * 2
            picks += [rng.choice(revenue) for _ in range(rng.randint(8, 14))]
            others = [m for m in menu if m[0] not in RECURRING and m[2] not in ("6000", "6010", "4000")]
            picks += [rng.choice(others) for _ in range(rng.randint(14, 22))]
            for m in picks:
                tpl, (lo, hi), acct, over, diff, why, _ = m
                day = start + dt.timedelta(days=rng.randint(0, 27))
                amount = Decimal(rng.randint(int(lo * 100), int(hi * 100))) / 100 if lo != hi else Decimal(lo)
                label = over.get(ind, acct)
                assert label in valid, label
                n += 1
                tid = f"T{n:05d}"
                card4 = f"{(int(bid[1:]) * 7919) % 9000 + 1000}"
                txns.append([tid, bid, day.isoformat(), bank_format(rng, bid, fill(rng, tpl, biz, day), day, card4), f"{amount:.2f}"])
                labels.append([tid, label, diff, why])
    order = sorted(range(len(txns)), key=lambda i: (txns[i][1], txns[i][2], txns[i][0]))
    txns = [txns[i] for i in order]
    labels = [labels[i] for i in order]
    with open(os.path.join(DATA, "transactions.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(["txn_id", "business_id", "date", "description", "amount"])
        w.writerows(txns)
    with open(os.path.join(DATA, "labels.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(["txn_id", "account", "difficulty", "reason"])
        w.writerows(labels)
    # warm: a random 30/70 split, as if the tool already knows these clients.
    # cold: whole businesses held out, as if each test business is a new client
    # in an industry the tool hasn't seen labels for.
    cold_dev = {"B02", "B05", "B08", "B11"}
    srng = random.Random(42)
    with open(os.path.join(DATA, "splits.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(["txn_id", "warm", "cold"])
        for t in txns:
            w.writerow([t[0], "dev" if srng.random() < 0.3 else "test", "dev" if t[1] in cold_dev else "test"])
    print(f"{len(txns)} transactions, {len(BUSINESSES)} businesses")


if __name__ == "__main__":
    main()
